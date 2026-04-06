"""
Vyuha AI — SQLite Database Layer
Async SQLite storage for incidents, proposals, and evolutionary learnings.
"""

import aiosqlite
import json
import os
import logging
from pathlib import Path

from control_plane.models import (
    Incident, IncidentSeverity, IncidentStatus,
    AgentProposal, FormationChange, FormationAction,
    Learning,
)

logger = logging.getLogger("vyuha-db")

DB_PATH = Path(os.getenv("VYUHA_DB_PATH", "/app/vyuha.db"))


async def get_db() -> aiosqlite.Connection:
    # Ensure parent directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    """Create tables if they don't exist."""
    # Ensure parent directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'detected',
                description TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_node TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                proposed_config TEXT NOT NULL,
                confidence REAL NOT NULL,
                agent_reasoning TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                created_at TEXT NOT NULL,
                FOREIGN KEY (incident_id) REFERENCES incidents(id)
            );

            CREATE TABLE IF NOT EXISTS learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                proposal_id INTEGER NOT NULL,
                was_approved INTEGER NOT NULL,
                human_feedback TEXT NOT NULL,
                agent_reflection TEXT NOT NULL,
                lesson_learned TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (incident_id) REFERENCES incidents(id),
                FOREIGN KEY (proposal_id) REFERENCES proposals(id)
            );
        """)
        await db.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    finally:
        await db.close()


# --- Incident CRUD ---

async def create_incident(incident: Incident) -> Incident:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO incidents (node_name, severity, status, description, detected_at)
               VALUES (?, ?, ?, ?, ?)""",
            (incident.node_name, incident.severity.value, incident.status.value,
             incident.description, incident.detected_at),
        )
        await db.commit()
        incident.id = cursor.lastrowid
        return incident
    finally:
        await db.close()


async def update_incident_status(incident_id: int, status: IncidentStatus, resolved_at: str | None = None) -> None:
    db = await get_db()
    try:
        if resolved_at:
            await db.execute(
                "UPDATE incidents SET status=?, resolved_at=? WHERE id=?",
                (status.value, resolved_at, incident_id),
            )
        else:
            await db.execute(
                "UPDATE incidents SET status=? WHERE id=?",
                (status.value, incident_id),
            )
        await db.commit()
    finally:
        await db.close()


async def get_active_incidents() -> list[Incident]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM incidents WHERE status NOT IN ('applied', 'reflected') ORDER BY id DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_incident(r) for r in rows]
    finally:
        await db.close()


async def get_incident(incident_id: int) -> Incident | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,))
        row = await cursor.fetchone()
        return _row_to_incident(row) if row else None
    finally:
        await db.close()


def _row_to_incident(row) -> Incident:
    return Incident(
        id=row["id"],
        node_name=row["node_name"],
        severity=IncidentSeverity(row["severity"]),
        status=IncidentStatus(row["status"]),
        description=row["description"],
        detected_at=row["detected_at"],
        resolved_at=row["resolved_at"],
    )


# --- Proposal CRUD ---

async def create_proposal(proposal: AgentProposal) -> AgentProposal:
    db = await get_db()
    try:
        fc = proposal.formation_change
        cursor = await db.execute(
            """INSERT INTO proposals
               (incident_id, action, target_node, reasoning, proposed_config,
                confidence, agent_reasoning, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fc.incident_id, fc.action.value, fc.target_node, fc.reasoning,
             json.dumps(fc.proposed_config), fc.confidence,
             proposal.agent_reasoning, proposal.status.value, proposal.created_at),
        )
        await db.commit()
        proposal.id = cursor.lastrowid
        return proposal
    finally:
        await db.close()


async def update_proposal_status(proposal_id: int, status: IncidentStatus) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE proposals SET status=? WHERE id=?",
            (status.value, proposal_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_pending_proposals() -> list[AgentProposal]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM proposals WHERE status='proposed' ORDER BY id DESC"
        )
        rows = await cursor.fetchall()
        return [_row_to_proposal(r) for r in rows]
    finally:
        await db.close()


async def get_proposal(proposal_id: int) -> AgentProposal | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,))
        row = await cursor.fetchone()
        return _row_to_proposal(row) if row else None
    finally:
        await db.close()


async def get_proposals_for_incident(incident_id: int) -> list[AgentProposal]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM proposals WHERE incident_id=? ORDER BY id DESC",
            (incident_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_proposal(r) for r in rows]
    finally:
        await db.close()


def _row_to_proposal(row) -> AgentProposal:
    return AgentProposal(
        id=row["id"],
        incident_id=row["incident_id"],
        formation_change=FormationChange(
            incident_id=row["incident_id"],
            action=FormationAction(row["action"]),
            target_node=row["target_node"],
            reasoning=row["reasoning"],
            proposed_config=json.loads(row["proposed_config"]),
            confidence=row["confidence"],
        ),
        agent_reasoning=row["agent_reasoning"],
        status=IncidentStatus(row["status"]),
        created_at=row["created_at"],
    )


# --- Learning CRUD ---

async def create_learning(learning: Learning) -> Learning:
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO learnings
               (incident_id, proposal_id, was_approved, human_feedback,
                agent_reflection, lesson_learned, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (learning.incident_id, learning.proposal_id,
             1 if learning.was_approved else 0, learning.human_feedback,
             learning.agent_reflection, learning.lesson_learned, learning.created_at),
        )
        await db.commit()
        learning.id = cursor.lastrowid
        return learning
    finally:
        await db.close()


async def get_all_learnings() -> list[Learning]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM learnings ORDER BY id DESC")
        rows = await cursor.fetchall()
        return [_row_to_learning(r) for r in rows]
    finally:
        await db.close()


async def get_learnings_for_incident(incident_id: int) -> list[Learning]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM learnings WHERE incident_id=? ORDER BY id DESC",
            (incident_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_learning(r) for r in rows]
    finally:
        await db.close()


def _row_to_learning(row) -> Learning:
    return Learning(
        id=row["id"],
        incident_id=row["incident_id"],
        proposal_id=row["proposal_id"],
        was_approved=bool(row["was_approved"]),
        human_feedback=row["human_feedback"],
        agent_reflection=row["agent_reflection"],
        lesson_learned=row["lesson_learned"],
        created_at=row["created_at"],
    )
