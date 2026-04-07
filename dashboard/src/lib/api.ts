import axios from "axios";

// Support both local development (rewrites) and production (absolute URL)
export const baseURL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "/orchestrator-api";

const API = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

export interface NodeState {
  node_name: string;
  state: "HEALTHY" | "DEAD" | "DEGRADED" | "HIGH_LATENCY" | "FLAKY" | "UNKNOWN";
  checked_at: string;
  response_time_ms?: number;
  error?: string;
}

export interface MonitorStatus {
  orchestrator_uptime: number;
  monitoring_active: boolean;
  node_states: NodeState[];
  active_incidents: any[];
  pending_proposals: any[];
  circuit_breaker_active: boolean;
  consecutive_agent_failures: number;
}

export const fetchStatus = async (): Promise<MonitorStatus> => {
  const { data } = await API.get("/monitor/status");
  return data;
};

export const fetchProposals = async () => {
  const { data } = await API.get("/proposals");
  return data.proposals || [];
};

export const fetchLearnings = async () => {
  const { data } = await API.get("/learnings");
  return data.learnings || [];
};

export const approveProposal = async (proposalId: number, feedback: string) => {
  const { data } = await API.post("/approve", {
    proposal_id: proposalId,
    feedback,
  });
  return data;
};

export const rejectProposal = async (proposalId: number, feedback: string) => {
  const { data } = await API.post("/reject", {
    proposal_id: proposalId,
    feedback,
  });
  return data;
};

export const triggerTriage = async () => {
  const { data } = await API.post("/trigger-triage");
  return data;
};

export const interrogateAgent = async (message: string) => {
  const { data } = await API.post("/chat", { message });
  return data.reply;
};

export const injectChaos = async (nodeName: string, state: string, reason: string) => {
  const { data } = await API.post(`/chaos/${nodeName}/fail`, { state, reason });
  return data;
};

export const recoverNode = async (nodeName: string) => {
  const { data } = await API.post(`/chaos/${nodeName}/recover`);
  return data;
};

export const checkProxyPulse = async () => {
  const { data } = await API.get("/monitor/check-proxy");
  return data;
};

export const checkLLMHealth = async () => {
  const { data } = await API.get("/monitor/check-llm");
  return data;
};

export const checkNodeHealthProxy = async (nodeName: string) => {
  const { data } = await API.get(`/chaos/${nodeName}/health`);
  return data;
};
