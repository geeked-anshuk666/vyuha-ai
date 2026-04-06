"""
Tests for Shadow Validator
"""

import pytest
from unittest.mock import patch, AsyncMock
from control_plane.validator import shadow_validator
from control_plane.models import AgentProposal, FormationChange, FormationAction

@pytest.fixture
def base_proposal():
    fc = FormationChange(
        incident_id=1,
        action=FormationAction.REROUTE,
        target_node="node-a",
        reasoning="Test reasoning",
        proposed_config={
            "formation": "failover-node-b",
            "routes": [
                {"name": "node-b", "url": "http://node-b:8000", "weight": 100, "active": True},
                {"name": "node-a", "url": "http://node-a:8000", "weight": 0, "active": False}
            ]
        },
        confidence=0.9
    )
    return AgentProposal(
        incident_id=1,
        formation_change=fc,
        agent_reasoning="Test agent reasoning"
    )

@pytest.mark.anyio
async def test_validator_passes_valid_config(base_proposal):
    with patch.object(shadow_validator, '_check_liveness', new_callable=AsyncMock) as mock_liveness:
        with patch.object(shadow_validator, '_check_idempotency', new_callable=AsyncMock) as mock_idempotency:
            result = await shadow_validator.validate(base_proposal)
            assert result.passed is True
            assert len(result.errors) == 0

@pytest.mark.anyio
async def test_validator_fails_invalid_schema(base_proposal):
    del base_proposal.formation_change.proposed_config["routes"]
    result = await shadow_validator.validate(base_proposal)
    assert result.passed is False
    assert any("Missing 'routes' key" in e for e in result.errors)

@pytest.mark.anyio
async def test_validator_fails_unknown_node(base_proposal):
    base_proposal.formation_change.proposed_config["routes"][0]["name"] = "unknown-node"
    with patch.object(shadow_validator, '_check_liveness', new_callable=AsyncMock):
        with patch.object(shadow_validator, '_check_idempotency', new_callable=AsyncMock):
            result = await shadow_validator.validate(base_proposal)
            assert result.passed is False
            assert any("Unknown nodes referenced" in e for e in result.errors)

@pytest.mark.anyio
async def test_validator_fails_zero_weight(base_proposal):
    base_proposal.formation_change.proposed_config["routes"][0]["weight"] = 0
    with patch.object(shadow_validator, '_check_liveness', new_callable=AsyncMock):
        with patch.object(shadow_validator, '_check_idempotency', new_callable=AsyncMock):
            result = await shadow_validator.validate(base_proposal)
            assert result.passed is False
            assert any("All active routes have zero weight" in e for e in result.errors)

@pytest.mark.anyio
async def test_validator_fails_no_active_routes(base_proposal):
    base_proposal.formation_change.proposed_config["routes"][0]["active"] = False
    with patch.object(shadow_validator, '_check_liveness', new_callable=AsyncMock):
        with patch.object(shadow_validator, '_check_idempotency', new_callable=AsyncMock):
            result = await shadow_validator.validate(base_proposal)
            assert result.passed is False
            assert any("No active routes" in e for e in result.errors)
