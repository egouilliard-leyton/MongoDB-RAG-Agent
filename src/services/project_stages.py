"""
Project stage state machine.

This module is intentionally small and self-contained so the stage logic has a
single source of truth shared by API + UI.

Stages can be loaded from a MongoDB workflow template via `get_stage_definitions()`,
with `FALLBACK_STAGES` used when MongoDB is unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    is_terminal: bool = False


# Stage catalog (key -> Stage) — used as hardcoded fallback
STAGES: Dict[str, Stage] = {
    "prep_docs": Stage("prep_docs", "Prepare documents"),
    "submit_first_instance": Stage("submit_first_instance", "Submit (1st instance)"),
    "await_response": Stage("await_response", "Await response"),
    "inquiry_check": Stage("inquiry_check", "Inquiry check"),
    "prepare_answers": Stage("prepare_answers", "Prepare answers"),
    "first_instance_outcome": Stage("first_instance_outcome", "1st instance outcome"),
    "appeal_second_instance": Stage("appeal_second_instance", "Appeal (2nd instance)"),
    "second_instance_decision": Stage("second_instance_decision", "2nd instance decision"),
    "complaint_wsa": Stage("complaint_wsa", "Complaint to WSA"),
    "wsa_decision": Stage("wsa_decision", "WSA decision"),
    "complaint_nsa": Stage("complaint_nsa", "Complaint to NSA"),
    "nsa_decision": Stage("nsa_decision", "NSA decision"),
    # Terminal-ish
    "end_refund": Stage("end_refund", "End: refund", is_terminal=True),
    "end_no_appeal": Stage("end_no_appeal", "End: no appeal", is_terminal=True),
    "return_reconsideration": Stage("return_reconsideration", "Return for reconsideration"),
}


# Transition table: (from_stage, event) -> to_stage
# We keep event strings for UI buttons and stage history.
TRANSITIONS: Dict[Tuple[str, str], str] = {
    ("prep_docs", "next"): "submit_first_instance",
    ("submit_first_instance", "next"): "await_response",
    ("await_response", "next"): "inquiry_check",
    ("inquiry_check", "yes"): "prepare_answers",
    ("prepare_answers", "next"): "await_response",
    ("inquiry_check", "no"): "first_instance_outcome",
    ("first_instance_outcome", "positive"): "end_refund",
    ("first_instance_outcome", "negative"): "appeal_second_instance",
    ("appeal_second_instance", "no"): "end_no_appeal",
    ("appeal_second_instance", "yes"): "second_instance_decision",
    ("second_instance_decision", "negative"): "complaint_wsa",
    ("second_instance_decision", "successful"): "return_reconsideration",
    ("return_reconsideration", "next"): "submit_first_instance",
    ("complaint_wsa", "no"): "end_no_appeal",
    ("complaint_wsa", "yes"): "wsa_decision",
    ("wsa_decision", "negative"): "complaint_nsa",
    ("wsa_decision", "successful"): "return_reconsideration",
    ("complaint_nsa", "no"): "end_no_appeal",
    ("complaint_nsa", "yes"): "nsa_decision",
    ("nsa_decision", "negative_final"): "end_no_appeal",
    ("nsa_decision", "successful"): "return_reconsideration",
}


def is_valid_stage_key(stage_key: str) -> bool:
    return stage_key in STAGES


def get_stage_label(stage_key: str) -> str:
    if stage_key in STAGES:
        return STAGES[stage_key].label
    return stage_key


def allowed_transitions(from_stage: str) -> List[Dict[str, str]]:
    """Return list of allowed actions from a stage: [{event, to, to_label}]"""
    actions: List[Dict[str, str]] = []
    for (src, event), dst in TRANSITIONS.items():
        if src != from_stage:
            continue
        actions.append(
            {
                "event": event,
                "to": dst,
                "to_label": get_stage_label(dst),
            }
        )
    # Stable ordering: event then to
    actions.sort(key=lambda a: (a["event"], a["to"]))
    return actions


def resolve_transition(from_stage: str, event: str) -> Optional[str]:
    return TRANSITIONS.get((from_stage, event))


def validate_transition(from_stage: str, event: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate a transition event from a stage.

    Returns (ok, to_stage, error_message).
    """
    if not is_valid_stage_key(from_stage):
        return False, None, f"Unknown from_stage '{from_stage}'"
    to_stage = resolve_transition(from_stage, event)
    if not to_stage:
        return False, None, f"Event '{event}' is not allowed from stage '{from_stage}'"
    if not is_valid_stage_key(to_stage):
        return False, None, f"Transition resolved to unknown stage '{to_stage}'"
    return True, to_stage, None


# Alias for callers that need the hardcoded fallback explicitly
FALLBACK_STAGES: Dict[str, str] = {key: stage.label for key, stage in STAGES.items()}


async def get_stage_definitions(
    db: Any, workflow_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Get stage definitions from a MongoDB workflow template.

    Falls back to FALLBACK_STAGES if MongoDB is unavailable or the workflow is
    not found.

    Args:
        db: Motor database instance.
        workflow_id: Specific workflow template ID. If None, uses the default template.

    Returns:
        Dict mapping stage_id -> stage_label.
    """
    try:
        from bson import ObjectId

        collection = db["workflow_templates"]

        if workflow_id:
            doc = await collection.find_one({"_id": ObjectId(workflow_id)})
        else:
            doc = await collection.find_one({"is_default": True})

        if doc and doc.get("stages"):
            return {
                stage["id"]: stage["label"]
                for stage in doc["stages"]
                if "id" in stage and "label" in stage
            }
    except Exception as exc:
        logger.warning(
            f"Failed to load stage definitions from MongoDB: {exc}. "
            "Falling back to hardcoded stages."
        )

    return FALLBACK_STAGES


