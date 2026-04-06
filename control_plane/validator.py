"""
Vyuha AI — Shadow Validator
Validates agent-proposed formation changes before they hit production.
Runs the proposed config through a series of deterministic safety checks
to prevent the agent from breaking the routing layer.
"""

import json
import logging
from copy import deepcopy

import httpx

from control_plane.models import (
    FormationChange, FormationAction, AgentProposal,
    NodeHealthSnapshot, NodeState,
)
from control_plane.tools import NODE_URLS, PROXY_URL

logger = logging.getLogger("vyuha-validator")


class ValidationResult:
    """Encapsulates the outcome of a shadow validation run."""

    def __init__(self, passed: bool, checks: list[dict], errors: list[str] | None = None):
        self.passed = passed
        self.checks = checks
        self.errors = errors or []

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "errors": self.errors,
        }


class ShadowValidator:
    """
    Validates proposed formation changes through deterministic safety checks.

    Instead of spinning up a full Docker container (which would require
    Docker-in-Docker), we perform a rigorous series of structural and
    reachability validations against the proposed config.

    Validation pipeline:
    1. Schema validation — Is the proposed config structurally valid?
    2. Route integrity — Do all routes reference known nodes?
    3. Weight sanity — Do weights sum to reasonable values?
    4. Liveness probe — Are the "healthy" nodes actually reachable right now?
    5. Formation safety — Does the config leave at least 1 active route?
    6. Idempotency check — Is this change actually different from current config?
    """

    def __init__(self):
        self.node_urls = NODE_URLS
        self.proxy_url = PROXY_URL

    async def validate(self, proposal: AgentProposal) -> ValidationResult:
        """Run the full validation pipeline on a proposed formation change."""
        checks: list[dict] = []
        errors: list[str] = []

        config = proposal.formation_change.proposed_config

        # 1. Schema validation
        schema_ok = self._check_schema(config, checks, errors)
        if not schema_ok:
            return ValidationResult(passed=False, checks=checks, errors=errors)

        # 2. Route integrity
        self._check_route_integrity(config, checks, errors)

        # 3. Weight sanity
        self._check_weight_sanity(config, checks, errors)

        # 4. Formation safety (at least 1 active route)
        self._check_formation_safety(config, checks, errors)

        # 5. Liveness probe — verify "active" nodes are actually reachable
        await self._check_liveness(config, checks, errors)

        # 6. Idempotency check
        await self._check_idempotency(config, checks, errors)

        passed = len(errors) == 0
        return ValidationResult(passed=passed, checks=checks, errors=errors)

    def _check_schema(self, config: dict, checks: list, errors: list) -> bool:
        """Verify the proposed config has the required structure."""
        check = {"name": "schema_validation", "passed": True, "detail": ""}

        if "formation" not in config:
            check["passed"] = False
            check["detail"] = "Missing 'formation' key"
            errors.append(check["detail"])
            checks.append(check)
            return False

        if "routes" not in config:
            check["passed"] = False
            check["detail"] = "Missing 'routes' key"
            errors.append(check["detail"])
            checks.append(check)
            return False

        if not isinstance(config["routes"], list):
            check["passed"] = False
            check["detail"] = "'routes' must be a list"
            errors.append(check["detail"])
            checks.append(check)
            return False

        for i, route in enumerate(config["routes"]):
            required_keys = {"name", "url", "weight", "active"}
            missing = required_keys - set(route.keys())
            if missing:
                check["passed"] = False
                check["detail"] = f"Route {i} missing keys: {missing}"
                errors.append(check["detail"])
                checks.append(check)
                return False

        check["detail"] = f"Valid schema: {len(config['routes'])} routes"
        checks.append(check)
        return True

    def _check_route_integrity(self, config: dict, checks: list, errors: list) -> None:
        """Verify all route names reference known nodes."""
        check = {"name": "route_integrity", "passed": True, "detail": ""}
        unknown = []

        for route in config["routes"]:
            if route["name"] not in self.node_urls:
                unknown.append(route["name"])

        if unknown:
            check["passed"] = False
            check["detail"] = f"Unknown nodes referenced: {unknown}"
            errors.append(check["detail"])
        else:
            check["detail"] = "All routes reference known nodes"

        checks.append(check)

    def _check_weight_sanity(self, config: dict, checks: list, errors: list) -> None:
        """Verify weights are within acceptable bounds."""
        check = {"name": "weight_sanity", "passed": True, "detail": ""}
        active_routes = [r for r in config["routes"] if r.get("active", False)]

        if not active_routes:
            check["detail"] = "No active routes — weight check skipped"
            checks.append(check)
            return

        total_weight = sum(r.get("weight", 0) for r in active_routes)

        if total_weight == 0:
            check["passed"] = False
            check["detail"] = "All active routes have zero weight"
            errors.append(check["detail"])
        elif total_weight > 200:
            check["passed"] = False
            check["detail"] = f"Total active weight {total_weight} exceeds maximum (200)"
            errors.append(check["detail"])
        else:
            check["detail"] = f"Total active weight: {total_weight}"

        checks.append(check)

    def _check_formation_safety(self, config: dict, checks: list, errors: list) -> None:
        """Ensure at least one active route exists (no total blackout)."""
        check = {"name": "formation_safety", "passed": True, "detail": ""}
        active_count = sum(1 for r in config["routes"] if r.get("active", False))

        emergency_formation = "emergency" in config.get("formation", "").lower()

        if active_count == 0 and not emergency_formation:
            check["passed"] = False
            check["detail"] = "No active routes — formation would cause total traffic blackout"
            errors.append(check["detail"])
        elif active_count == 0 and emergency_formation:
            check["detail"] = "Emergency formation with 0 active routes (acknowledged)"
        else:
            check["detail"] = f"{active_count} active route(s)"

        checks.append(check)

    async def _check_liveness(self, config: dict, checks: list, errors: list) -> None:
        """Probe nodes marked as 'active' to verify they're actually reachable."""
        check = {"name": "liveness_probe", "passed": True, "detail": ""}
        unreachable = []

        active_routes = [r for r in config["routes"] if r.get("active", False)]

        for route in active_routes:
            url = route.get("url", "")
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{url}/health")
                    if resp.status_code != 200:
                        unreachable.append(f"{route['name']} (HTTP {resp.status_code})")
            except (httpx.ConnectError, httpx.TimeoutException):
                unreachable.append(f"{route['name']} (unreachable)")

        if unreachable:
            check["passed"] = False
            check["detail"] = f"Active nodes failed liveness: {unreachable}"
            errors.append(check["detail"])
        else:
            probed = [r["name"] for r in active_routes]
            check["detail"] = f"All active nodes reachable: {probed}"

        checks.append(check)

    async def _check_idempotency(self, config: dict, checks: list, errors: list) -> None:
        """Check if the proposed config is identical to the current one (no-op guard)."""
        check = {"name": "idempotency", "passed": True, "detail": ""}

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.proxy_url}/proxy/status")
                if resp.status_code == 200:
                    current = resp.json()
                    current_formation = current.get("formation", "")
                    proposed_formation = config.get("formation", "")

                    if current_formation == proposed_formation:
                        check["detail"] = (
                            f"Warning: proposed formation '{proposed_formation}' "
                            f"matches current — this may be a no-op"
                        )
                    else:
                        check["detail"] = (
                            f"Formation change: '{current_formation}' → '{proposed_formation}'"
                        )
                else:
                    check["detail"] = "Could not fetch current config for comparison"
        except (httpx.ConnectError, httpx.TimeoutException):
            check["detail"] = "Proxy unreachable — skipping idempotency check"

        checks.append(check)


# Module-level singleton
shadow_validator = ShadowValidator()
