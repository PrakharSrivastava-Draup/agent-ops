from __future__ import annotations

from typing import Any, Dict, List

from app.models.schemas import PlanStep


class PlanValidationError(Exception):
    """Raised when the planner returns an invalid or unsafe plan."""


ALLOWED_ACTIONS: Dict[str, Dict[str, Dict[str, tuple[type, bool]]]] = {
    "GithubAgent": {
        "get_pr": {"owner": (str, True), "repo": (str, True), "number": (int, True)},
        "list_recent_commits": {
            "owner": (str, True),
            "repo": (str, True),
            "branch": (str, True),
            "limit": (int, False),
        },
        "get_file": {"owner": (str, True), "repo": (str, True), "path": (str, True), "ref": (str, True)},
    },
    "AWSAgent": {
        "list_s3_buckets": {},
        "describe_ec2_instances": {"region": (str, True)},
        "get_s3_object_head": {"bucket": (str, True), "key": (str, True)},
    },
    "JiraAgent": {
        "get_issue": {"issue_key": (str, True)},
        "search_issues": {"jql": (str, True), "limit": (int, False)},
    },
    "JenkinsAgent": {
        "trigger_provide_access": {
            "user_email": (str, True),
            "services": (list, True),
            "cc_email": (str, False),
            "aws_iam_user_group": (str, False),
            "github_team": (str, False),
            "env_name": (str, False),
        },
    },
}


class PlanValidator:
    """Validate planner output against a whitelist of allowed actions."""

    def __init__(self) -> None:
        self.allowed_actions = ALLOWED_ACTIONS

    def validate(self, plan_steps: List[dict[str, Any]]) -> List[PlanStep]:
        validated_steps: List[PlanStep] = []
        seen_ids: set[int] = set()

        for raw_step in plan_steps:
            step = PlanStep(**raw_step)
            if step.step_id in seen_ids:
                raise PlanValidationError(f"Duplicate step_id detected: {step.step_id}")
            seen_ids.add(step.step_id)

            allowed = self.allowed_actions.get(step.agent)
            if allowed is None:
                raise PlanValidationError(f"Agent `{step.agent}` is not allowed.")

            action_requirements = allowed.get(step.action)
            if action_requirements is None:
                raise PlanValidationError(f"Action `{step.action}` is not permitted for `{step.agent}`.")

            self._validate_args(step.action, step.args, action_requirements)
            
            # Custom validation for JenkinsAgent
            if step.agent == "JenkinsAgent" and step.action == "trigger_provide_access":
                self._validate_jenkins_services(step.args)
            
            validated_steps.append(step)
        return validated_steps

    def _validate_args(
        self,
        action: str,
        provided_args: dict[str, Any],
        requirements: Dict[str, tuple[type, bool]],
    ) -> None:
        for key, (expected_type, required) in requirements.items():
            if key not in provided_args:
                if required:
                    raise PlanValidationError(f"Missing required argument `{key}` for action `{action}`.")
                continue
            value = provided_args[key]
            if not isinstance(value, expected_type):
                # allow ints provided as floats if they are integer valued? prefer convert.
                if expected_type is int and isinstance(value, float) and value.is_integer():
                    provided_args[key] = int(value)
                else:
                    raise PlanValidationError(
                        f"Argument `{key}` for action `{action}` must be of type {expected_type.__name__}."
                    )

        # Remove unexpected arguments to reduce risk.
        allowed_keys = set(requirements.keys())
        extraneous = set(provided_args.keys()) - allowed_keys
        for key in list(extraneous):
            provided_args.pop(key)

    def _validate_jenkins_services(self, args: dict[str, Any]) -> None:
        """Validate that services list contains only valid service names."""
        VALID_SERVICES = {"AWS", "GitHub", "Confluence", "Database"}
        
        if "services" not in args:
            return  # Already validated as required
        
        services = args["services"]
        if not isinstance(services, list):
            raise PlanValidationError("Argument `services` must be a list.")
        
        if not services:
            raise PlanValidationError("Argument `services` must contain at least one service.")
        
        services_set = {str(s).strip() for s in services if s}
        invalid_services = services_set - VALID_SERVICES
        if invalid_services:
            raise PlanValidationError(
                f"Invalid services in list: {sorted(invalid_services)}. "
                f"Valid services are: {sorted(VALID_SERVICES)}"
            )
        
        # Normalize services list
        args["services"] = sorted(list(services_set))

