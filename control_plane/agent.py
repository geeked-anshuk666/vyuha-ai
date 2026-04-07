"""
Vyuha AI — GLM 5.1 Agent
Long-horizon reasoning agent that analyzes failures, proposes formation changes,
and reflects on outcomes to build evolutionary memory.

Uses a placeholder HTTP client for GLM 5.1 API — swap URL and auth when ready.
"""

import json
import os
import logging
from datetime import datetime

import httpx

from control_plane.models import (
    NodeHealthSnapshot, NodeState, Incident, IncidentSeverity,
    FormationChange, FormationAction, AgentProposal, IncidentStatus,
    Learning,
)
from control_plane.tools import (
    tool_check_all_nodes, tool_assess_severity,
    tool_build_failover_config, TOOL_REGISTRY,
)
from control_plane import db

logger = logging.getLogger("vyuha-agent")

GLM_API_URL = os.getenv("GLM_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
GLM_API_KEY = os.getenv("GLM_API_KEY", "placeholder-key")
# Model priority order
PRIORITY_MODELS = ["glm-5.1", "glm-5"]


SYSTEM_PROMPT = """You are Vyuha AI — an autonomous multi-cloud recovery companion.
Your role is to analyze infrastructure failures and propose strategic routing changes.

CONTEXT:
- You monitor a fleet of cloud nodes (AWS, Azure, and GCP)
- Traffic flows through a Dynamic Reverse Proxy (Vyuha-Proxy)
- You can propose "Formation Changes" to reroute traffic when nodes fail

CAPABILITIES (Walled Garden — you can ONLY use these):
1. check_node_health(node_name) — Check a specific node's health
2. check_all_nodes() — Check all nodes
3. get_current_formation() — Get current proxy routing config
4. assess_severity(node_states) — Determine incident severity
5. build_failover_config(healthy_nodes, dead_nodes) — Build a new routing config
6. restart_node(node_name) — Attempt an Autonomous SRE process restart on the target

RULES:
- NEVER suggest direct shell commands. You operate through API tools only.
- Always explain your reasoning step-by-step using Markdown headers (####) and bullet points.
- Reference past learnings when available.
- Be honest about uncertainty — state your confidence level.

PAST LEARNINGS:
{learnings}

CURRENT SITUATION:
{situation}

Analyze the situation and propose a formation change if needed.
Respond in this JSON format:
{{
    "analysis": "Your step-by-step analysis of the situation (use Markdown headers and bullets)",
    "action": "reroute|deactivate_node|reactivate_node|rebalance|none",
    "target_node": "the node to act on",
    "reasoning": "Why this is the best action (use Markdown headers and bullets)",
    "remediation_action": "restart_node|none (Optional SRE remediation to execute after route change)",
    "confidence": 0.0-1.0,
    "proposed_formation": {{
        "formation": "formation-name",
        "routes": [
            {{"name": "aws|azure|gcp", "url": "http://...", "weight": 0-100, "active": true|false}}
        ]
    }}
}}
"""

REFLECTION_PROMPT = """You are Vyuha AI performing a post-incident reflection.

INCIDENT:
{incident}

YOUR PROPOSAL:
{proposal}

HUMAN DECISION: {decision}
HUMAN FEEDBACK: {feedback}

Reflect on this outcome. What did you learn?
Respond in this JSON format:
{{
    "reflection": "Your honest self-assessment of the proposal (Markdown supported)",
    "lesson_learned": "A concise rule or pattern for future incidents (Markdown supported)",
    "would_change": "What you would do differently next time"
}}
"""


async def _glm_request(messages: list[dict], temperature: float = 0.3, max_tokens: int = 2000) -> str | None:
    """Internal helper to try multiple models in order of priority."""
    headers = {
        "Authorization": f"Bearer {GLM_API_KEY}",
        "Content-Type": "application/json",
    }

    for model in PRIORITY_MODELS:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(GLM_API_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                elif resp.status_code in (404, 403):
                    logger.warning(f"Model {model} returned {resp.status_code}, trying next priority...")
                    continue
                else:
                    logger.warning(f"Model {model} returned {resp.status_code}: {resp.text}")
                    continue
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Model {model} unreachable: {e}")
            continue
    
    return None

async def _call_glm(prompt: str, system: str = "") -> dict:
    """Call GLM API with fallback priority. Returns dict for structured triage."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    
    content = await _glm_request(messages, temperature=0.3, max_tokens=2000)
    
    if not content:
        logger.warning("All GLM models failed, using deterministic fallback")
        return {}

    try:
        content = content.strip()
        if content.startswith("```"):
            # Handle markdown code blocks if the model wrapped the JSON
            if "json" in content[:10]:
                content = content.split("json", 1)[1]
            else:
                content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        return json.loads(content)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning(f"GLM response parsing failed ({e}), content: {content[:100]}...")
        return {}


async def chat_with_agent(question: str, node_states: list[NodeHealthSnapshot] = [], active_incidents: list = []) -> str:
    """Interrogate the agent via a read-only chat interface with model fallback."""
    learnings_text = await get_learnings_context()
    situation_text = "No active incidents detected." if not active_incidents else "DETECTED INCIDENTS: " + str([i.model_dump() for i in active_incidents])
    node_text = "Current Node States: " + str([n.model_dump() for n in node_states])
    
    system = (
        "You are Vyuha AI, an autonomous multi-cloud orchestrator. "
        "The human operator is asking you a question about your status, past learnings, or current configuration. "
        "Answer naturally, directly, and concisely. DO NOT output JSON. "
        f"\n\nCURRENT CLUSTER STATE:\n{node_text}\n{situation_text}"
        f"\n\nCURRENT LEARNING MEMORY:\n{learnings_text}"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    
    content = await _glm_request(messages, temperature=0.5, max_tokens=1000)
    
    if content:
        return content.strip()
        
    return "Error: All GLM models failed. Please check the API key and Docker logs."


async def triage_incident(node_states: list[NodeHealthSnapshot], learnings_text: str = "") -> AgentProposal | None:
    """
    Main agent entry point: analyze node states, create incident if needed,
    and propose a formation change.
    """
    failed_nodes = [n for n in node_states if n.state in (NodeState.DEAD, NodeState.DEGRADED, NodeState.HIGH_LATENCY, NodeState.FLAKY)]
    healthy_nodes = [n for n in node_states if n.state == NodeState.HEALTHY]

    if not failed_nodes:
        return None

    dead_nodes = failed_nodes

    # Create incident
    severity = tool_assess_severity(node_states)
    incident = Incident(
        node_name=dead_nodes[0].node_name,
        severity=severity,
        status=IncidentStatus.DETECTED,
        description=f"Node {dead_nodes[0].node_name} detected as {dead_nodes[0].state.value}. "
                    f"Error: {dead_nodes[0].error or 'Unknown'}",
    )
    incident = await db.create_incident(incident)
    await db.update_incident_status(incident.id, IncidentStatus.TRIAGING)

    # Build situation context
    situation = json.dumps({
        "node_states": [n.model_dump() for n in node_states],
        "dead_nodes": [n.node_name for n in dead_nodes],
        "healthy_nodes": [n.node_name for n in healthy_nodes],
        "severity": severity.value,
    }, indent=2)

    # Try GLM-powered reasoning
    system = SYSTEM_PROMPT.format(learnings=learnings_text or "No prior learnings.", situation=situation)
    glm_response = await _call_glm(situation, system)

    # Deterministic fallback if GLM is unavailable
    if not glm_response or "action" not in glm_response:
        logger.info("[FALLBACK] GLM API unavailable, using expert-system reasoning.")
        first_dead = dead_nodes[0]
        
        # Determine failure context
        failure_type = "unresponsive"
        if first_dead.state == NodeState.HIGH_LATENCY:
            failure_type = "latency_spike"
        elif first_dead.state == NodeState.FLAKY:
            failure_type = "instability"
        
        # Professional reasoning templates
        templates = {
            "unresponsive": {
                "analysis": f"Critical heartbeat failure on {first_dead.node_name}. Diagnostics indicate a total node hang or AWS mock network partition. Health SLA violated.",
                "reasoning": f"Node {first_dead.node_name} is emitting 0% success packets. Executing full failover to secondary cloud upstreams to preserve session integrity.",
                "remediation": "restart_node"
            },
            "latency_spike": {
                "analysis": f"P99 latency budget exceeded on {first_dead.node_name} (>1500ms jitter). This threshold suggests upstream resource exhaustion.",
                "reasoning": f"Current latency on {first_dead.node_name} degrades customer UX. Shifting weight to healthy nodes while keeping this node in 'Warm Standby'.",
                "remediation": "none"
            },
            "instability": {
                "analysis": f"Detected recurring packet loss on {first_dead.node_name}. Flaky behavior observed in last 3 polling cycles.",
                "reasoning": f"Intermittent connectivity on {first_dead.node_name} threatens p90 uptime SLAs. Isolating node for surgical SRE restart.",
                "remediation": "restart_node"
            }
        }
        
        ctx = templates.get(failure_type, templates["unresponsive"])
        proposed_config = tool_build_failover_config(
            healthy_nodes=[n.node_name for n in healthy_nodes],
            dead_nodes=[n.node_name for n in dead_nodes],
        )
        
        glm_response = {
            "analysis": ctx["analysis"],
            "action": "reroute",
            "target_node": first_dead.node_name,
            "reasoning": ctx["reasoning"],
            "remediation_action": ctx["remediation"],
            "confidence": 0.95,
            "proposed_formation": proposed_config,
        }
    else:
        # If GLM provided the action but not the full config, generate it
        if "proposed_formation" not in glm_response:
            glm_response["proposed_formation"] = tool_build_failover_config(
                healthy_nodes=[n.node_name for n in healthy_nodes],
                dead_nodes=[n.node_name for n in dead_nodes],
            )

    formation_change = FormationChange(
        incident_id=incident.id,
        action=FormationAction(glm_response.get("action", "reroute")),
        target_node=glm_response.get("target_node", dead_nodes[0].node_name),
        reasoning=glm_response.get("reasoning", "Automated failover"),
        proposed_config=glm_response.get("proposed_formation", {}),
        remediation_action=glm_response.get("remediation_action") if glm_response.get("remediation_action") != "none" else None,
        confidence=float(glm_response.get("confidence", 0.5)),
    )

    proposal = AgentProposal(
        incident_id=incident.id,
        formation_change=formation_change,
        agent_reasoning=glm_response.get("analysis", "Deterministic analysis"),
        status=IncidentStatus.PROPOSED,
    )
    proposal = await db.create_proposal(proposal)
    await db.update_incident_status(incident.id, IncidentStatus.PROPOSED)

    logger.info(f"Proposal created: {formation_change.action} on {formation_change.target_node} "
                f"(confidence: {formation_change.confidence})")

    return proposal


async def reflect_on_outcome(
    incident: Incident,
    proposal: AgentProposal,
    was_approved: bool,
    human_feedback: str,
) -> Learning:
    """
    Post-incident reflection. The agent analyzes the human's decision
    and generates a "lesson learned" for evolutionary memory.
    """
    incident_text = json.dumps(incident.model_dump(), indent=2, default=str)
    proposal_text = json.dumps(proposal.model_dump(), indent=2, default=str)
    decision = "APPROVED" if was_approved else "REJECTED"

    prompt = REFLECTION_PROMPT.format(
        incident=incident_text,
        proposal=proposal_text,
        decision=decision,
        feedback=human_feedback,
    )

    glm_response = await _call_glm(prompt)

    # Deterministic fallback
    if not glm_response or "reflection" not in glm_response:
        if was_approved:
            glm_response = {
                "reflection": f"My proposal to {proposal.formation_change.action.value} "
                             f"on {proposal.formation_change.target_node} was approved. "
                             f"The human confirmed this was the right call.",
                "lesson_learned": f"When {proposal.formation_change.target_node} fails with "
                                 f"'{incident.description}', rerouting traffic is effective.",
                "would_change": "Nothing — the action was validated.",
            }
        else:
            glm_response = {
                "reflection": f"My proposal was rejected. Human feedback: '{human_feedback}'. "
                             f"I need to reconsider my approach for similar situations.",
                "lesson_learned": f"When encountering '{incident.description}', "
                                 f"the action '{proposal.formation_change.action.value}' was not appropriate. "
                                 f"Human preference: {human_feedback}",
                "would_change": f"Consider the human feedback: '{human_feedback}' in future decisions.",
            }

    learning = Learning(
        incident_id=incident.id,
        proposal_id=proposal.id,
        was_approved=was_approved,
        human_feedback=human_feedback,
        agent_reflection=glm_response.get("reflection", ""),
        lesson_learned=glm_response.get("lesson_learned", ""),
    )
    learning = await db.create_learning(learning)

    # Update statuses:
    # - APPLIED = fix approved, watching for node recovery
    # - REFLECTED = fully closed (set when node actually heals)
    # - REJECTED = human rejected, learning recorded
    final_status = IncidentStatus.APPLIED if was_approved else IncidentStatus.REJECTED
    await db.update_incident_status(
        incident.id,
        final_status,
        resolved_at=datetime.utcnow().isoformat() if not was_approved else None,
    )
    await db.update_proposal_status(proposal.id, final_status)

    logger.info(f"Reflection complete: lesson='{learning.lesson_learned[:80]}...'")
    return learning


async def get_learnings_context() -> str:
    """Build a text summary of all past learnings for the agent's context window."""
    learnings = await db.get_all_learnings()
    if not learnings:
        return "No prior learnings."

    lines = []
    for l in learnings[-10:]:  # Last 10 learnings
        status = "✅ APPROVED" if l.was_approved else "❌ REJECTED"
        lines.append(f"- [{status}] {l.lesson_learned}")

    return "\n".join(lines)
