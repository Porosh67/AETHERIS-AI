"""
AETHERIS AI — Test Runner (Simulated)

Runs a bounded set of simulated unit/integration/regression tests
against a generated patch. Returns structured test results.

Tests are simulated for the demo but the pass/fail logic is deterministic
and feeds into the deterministic release gate.
"""
import asyncio
import logging
import random
from dataclasses import dataclass, field

logger = logging.getLogger("aetheris.test_runner")


@dataclass
class TestCase:
    name: str
    passed: bool
    duration_ms: float
    error: str | None = None


@dataclass
class TestRunResult:
    total: int
    passed: int
    failed: int
    pass_rate: float
    duration_ms: float
    test_cases: list[TestCase] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total":       self.total,
            "passed":      self.passed,
            "failed":      self.failed,
            "pass_rate":   self.pass_rate,
            "duration_ms": self.duration_ms,
            "test_cases": [
                {
                    "name":        t.name,
                    "passed":      t.passed,
                    "duration_ms": t.duration_ms,
                    "error":       t.error,
                }
                for t in self.test_cases
            ],
        }


_TEST_SUITE: dict[str, list[str]] = {
    "NULL_ERROR": [
        "test_null_guard_raises_value_error",
        "test_null_guard_with_valid_input_passes",
        "test_checkout_flow_end_to_end",
        "test_checkout_with_empty_user_id",
        "test_checkout_integration_mock",
    ],
    "SCHEMA_DRIFT": [
        "test_payment_payload_with_currency_code",
        "test_payment_payload_without_currency_code_uses_default",
        "test_backward_compatibility_v2_to_v1",
        "test_schema_validation_rejects_unknown_fields",
        "test_payment_processor_integration",
    ],
    "LATENCY_REGRESSION": [
        "test_stock_query_uses_index",
        "test_stock_query_latency_under_500ms",
        "test_bulk_query_pagination",
        "test_query_plan_contains_index_scan",
    ],
    "RATE_LIMIT_MISCONFIGURATION": [
        "test_rate_limit_config_loaded_correctly",
        "test_per_user_limit_not_exceeded",
        "test_429_response_on_limit_breach",
        "test_rate_limit_reset_after_window",
    ],
    "DEPENDENCY_FAILURE": [
        "test_circuit_breaker_triggers_on_failure",
        "test_retry_logic_on_connection_refused",
        "test_fallback_behavior_when_dependency_down",
        "test_health_check_updates_service_discovery",
    ],
    "RESOURCE_EXHAUSTION": [
        "test_batch_processor_memory_bound",
        "test_bulk_import_uses_streaming",
        "test_memory_usage_under_load",
        "test_oom_prevention_circuit",
    ],
}


async def run_tests(
    *,
    category: str,
    scenario: str = "pass",   # "pass" | "fail"
    patch_hash: str,
    seed: int | None = None,
) -> TestRunResult:
    """
    Run the appropriate test suite for the incident category.
    scenario="pass"  → all/most tests pass
    scenario="fail"  → some tests fail (simulates persistent bug)
    """
    test_names = _TEST_SUITE.get(category, ["test_generic_smoke"])
    rng = random.Random(seed or hash(patch_hash) % (2**31))

    test_cases: list[TestCase] = []
    total_duration = 0.0

    for name in test_names:
        await asyncio.sleep(0.05)  # simulate test execution time
        duration = round(rng.uniform(12, 340), 1)
        total_duration += duration

        if scenario == "pass":
            passed = True
            error  = None
        else:
            # Fail scenario: first test passes, rest have 70% fail rate
            passed = (name == test_names[0]) or (rng.random() > 0.70)
            error  = None if passed else f"AssertionError: expected behavior not met in {name}"

        test_cases.append(TestCase(name=name, passed=passed, duration_ms=duration, error=error))

    total  = len(test_cases)
    passed = sum(1 for t in test_cases if t.passed)
    failed = total - passed

    result = TestRunResult(
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=round(passed / total, 4) if total > 0 else 0.0,
        duration_ms=round(total_duration, 1),
        test_cases=test_cases,
    )

    logger.info(
        f"[TestRunner] category={category} scenario={scenario} "
        f"pass_rate={result.pass_rate:.2%} ({passed}/{total})"
    )
    return result
