"""
AETHERIS AI — Incident State Machine

Implements the explicit FSM with all required states and transitions.
All transitions are validated — invalid moves raise InvalidTransitionError.
"""
from enum import Enum


class IncidentState(str, Enum):
    IDLE               = "IDLE"
    INCIDENT_RECEIVED  = "INCIDENT_RECEIVED"
    DIAGNOSING         = "DIAGNOSING"
    PATCH_GENERATED    = "PATCH_GENERATED"
    PATCH_TESTING      = "PATCH_TESTING"
    AUDITING           = "AUDITING"
    CANARY_PENDING     = "CANARY_PENDING"
    CANARY_RUNNING     = "CANARY_RUNNING"
    ROLLED_OUT         = "ROLLED_OUT"
    REPAIR_RETRY       = "REPAIR_RETRY"
    QUARANTINED        = "QUARANTINED"
    AUDIT_UNTRUSTED    = "AUDIT_UNTRUSTED"


# Valid transitions: from_state -> set of allowed to_states
VALID_TRANSITIONS: dict[IncidentState, set[IncidentState]] = {
    IncidentState.IDLE: {
        IncidentState.INCIDENT_RECEIVED,
    },
    IncidentState.INCIDENT_RECEIVED: {
        IncidentState.DIAGNOSING,
    },
    IncidentState.DIAGNOSING: {
        IncidentState.PATCH_GENERATED,
        IncidentState.QUARANTINED,  # diagnosis itself can fail fatally
    },
    IncidentState.PATCH_GENERATED: {
        IncidentState.PATCH_TESTING,
    },
    IncidentState.PATCH_TESTING: {
        IncidentState.AUDITING,
        IncidentState.REPAIR_RETRY,
    },
    IncidentState.AUDITING: {
        IncidentState.CANARY_PENDING,
        IncidentState.REPAIR_RETRY,
        IncidentState.AUDIT_UNTRUSTED,
    },
    IncidentState.AUDIT_UNTRUSTED: {
        IncidentState.REPAIR_RETRY,
        IncidentState.QUARANTINED,
    },
    IncidentState.CANARY_PENDING: {
        IncidentState.CANARY_RUNNING,
    },
    IncidentState.CANARY_RUNNING: {
        IncidentState.ROLLED_OUT,
        IncidentState.REPAIR_RETRY,
    },
    IncidentState.REPAIR_RETRY: {
        IncidentState.DIAGNOSING,   # retry → re-diagnose
        IncidentState.QUARANTINED,  # max attempts exceeded
    },
    IncidentState.ROLLED_OUT:    set(),  # terminal
    IncidentState.QUARANTINED:   set(),  # terminal
}


class InvalidTransitionError(Exception):
    def __init__(self, from_state: IncidentState, to_state: IncidentState):
        super().__init__(
            f"Invalid state transition: {from_state.value} → {to_state.value}"
        )
        self.from_state = from_state
        self.to_state   = to_state


def validate_transition(from_state: IncidentState, to_state: IncidentState) -> None:
    """
    Raise InvalidTransitionError if the transition is not allowed.
    Call this BEFORE persisting any state change.
    """
    allowed = VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise InvalidTransitionError(from_state, to_state)


def is_terminal(state: IncidentState) -> bool:
    return state in (IncidentState.ROLLED_OUT, IncidentState.QUARANTINED)


def is_retry_allowed(attempt_count: int, max_attempts: int) -> bool:
    """
    Returns True if another repair attempt is permitted.
    attempt_count is the number of attempts ALREADY made (1-indexed completion).
    """
    return attempt_count < max_attempts
