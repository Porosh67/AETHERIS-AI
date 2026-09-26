"""
AETHERIS AI — State Machine Tests
Tests valid transitions, invalid transitions, terminal states, retry logic.
"""
import pytest
from backend.app.core.state_machine import (
    IncidentState,
    validate_transition,
    is_terminal,
    is_retry_allowed,
    InvalidTransitionError,
)


class TestValidTransitions:
    def test_idle_to_incident_received(self):
        validate_transition(IncidentState.IDLE, IncidentState.INCIDENT_RECEIVED)

    def test_incident_received_to_diagnosing(self):
        validate_transition(IncidentState.INCIDENT_RECEIVED, IncidentState.DIAGNOSING)

    def test_diagnosing_to_patch_generated(self):
        validate_transition(IncidentState.DIAGNOSING, IncidentState.PATCH_GENERATED)

    def test_patch_generated_to_patch_testing(self):
        validate_transition(IncidentState.PATCH_GENERATED, IncidentState.PATCH_TESTING)

    def test_patch_testing_to_auditing(self):
        validate_transition(IncidentState.PATCH_TESTING, IncidentState.AUDITING)

    def test_patch_testing_to_repair_retry(self):
        validate_transition(IncidentState.PATCH_TESTING, IncidentState.REPAIR_RETRY)

    def test_auditing_to_canary_pending(self):
        validate_transition(IncidentState.AUDITING, IncidentState.CANARY_PENDING)

    def test_auditing_to_repair_retry(self):
        validate_transition(IncidentState.AUDITING, IncidentState.REPAIR_RETRY)

    def test_auditing_to_audit_untrusted(self):
        validate_transition(IncidentState.AUDITING, IncidentState.AUDIT_UNTRUSTED)

    def test_audit_untrusted_to_repair_retry(self):
        validate_transition(IncidentState.AUDIT_UNTRUSTED, IncidentState.REPAIR_RETRY)

    def test_audit_untrusted_to_quarantined(self):
        validate_transition(IncidentState.AUDIT_UNTRUSTED, IncidentState.QUARANTINED)

    def test_canary_pending_to_canary_running(self):
        validate_transition(IncidentState.CANARY_PENDING, IncidentState.CANARY_RUNNING)

    def test_canary_running_to_rolled_out(self):
        validate_transition(IncidentState.CANARY_RUNNING, IncidentState.ROLLED_OUT)

    def test_canary_running_to_repair_retry(self):
        validate_transition(IncidentState.CANARY_RUNNING, IncidentState.REPAIR_RETRY)

    def test_repair_retry_to_diagnosing(self):
        validate_transition(IncidentState.REPAIR_RETRY, IncidentState.DIAGNOSING)

    def test_repair_retry_to_quarantined(self):
        validate_transition(IncidentState.REPAIR_RETRY, IncidentState.QUARANTINED)


class TestInvalidTransitions:
    def test_idle_cannot_jump_to_rolled_out(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(IncidentState.IDLE, IncidentState.ROLLED_OUT)

    def test_idle_cannot_jump_to_diagnosing(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(IncidentState.IDLE, IncidentState.DIAGNOSING)

    def test_rolled_out_is_terminal(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(IncidentState.ROLLED_OUT, IncidentState.DIAGNOSING)

    def test_quarantined_is_terminal(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(IncidentState.QUARANTINED, IncidentState.DIAGNOSING)

    def test_patch_testing_cannot_skip_to_rolled_out(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(IncidentState.PATCH_TESTING, IncidentState.ROLLED_OUT)

    def test_diagnosing_cannot_go_to_canary(self):
        with pytest.raises(InvalidTransitionError):
            validate_transition(IncidentState.DIAGNOSING, IncidentState.CANARY_RUNNING)


class TestTerminalStates:
    def test_rolled_out_is_terminal(self):
        assert is_terminal(IncidentState.ROLLED_OUT) is True

    def test_quarantined_is_terminal(self):
        assert is_terminal(IncidentState.QUARANTINED) is True

    def test_idle_not_terminal(self):
        assert is_terminal(IncidentState.IDLE) is False

    def test_diagnosing_not_terminal(self):
        assert is_terminal(IncidentState.DIAGNOSING) is False


class TestAttemptLimit:
    def test_attempt_0_of_3_allows_retry(self):
        assert is_retry_allowed(0, 3) is True

    def test_attempt_1_of_3_allows_retry(self):
        assert is_retry_allowed(1, 3) is True

    def test_attempt_2_of_3_allows_retry(self):
        assert is_retry_allowed(2, 3) is True

    def test_attempt_3_of_3_blocks_retry(self):
        assert is_retry_allowed(3, 3) is False

    def test_attempt_4_of_3_blocks_retry(self):
        assert is_retry_allowed(4, 3) is False

    def test_zero_max_always_blocks(self):
        assert is_retry_allowed(0, 0) is False
