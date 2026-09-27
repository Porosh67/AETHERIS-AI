"""
AETHERIS AI — Canary Validator (Simulated)

Simulates a canary deployment and health check.
Explicitly labeled as simulation — does NOT claim real production deployment.

Returns pass/fail based on deterministic thresholds against simulated metrics.
"""
import asyncio
import logging
import random
from dataclasses import dataclass

logger = logging.getLogger("aetheris.canary")

DEFAULT_CANARY_THRESHOLDS = {
    "error_rate_threshold":    0.02,    # 2% max error rate
    "latency_threshold_ms":    500,     # p99 max 500ms
    "health_check_passes":     3,       # number of health polls
    "poll_interval_seconds":   0.3,     # simulated poll interval (fast for demo)
    "min_traffic_percent":     5.0,     # canary traffic weight
}


@dataclass
class CanaryMetrics:
    error_rate:     float
    p99_latency_ms: float
    health_polls:   int
    healthy_polls:  int
    traffic_percent: float
    simulated:      bool = True


@dataclass
class CanaryResult:
    passed:   bool
    metrics:  CanaryMetrics
    reason:   str

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "simulated": True,
            "metrics": {
                "error_rate":      self.metrics.error_rate,
                "p99_latency_ms":  self.metrics.p99_latency_ms,
                "health_polls":    self.metrics.health_polls,
                "healthy_polls":   self.metrics.healthy_polls,
                "traffic_percent": self.metrics.traffic_percent,
            },
        }


class CanaryValidator:
    """
    Simulated canary deployment validator.
    Generates realistic canary metrics and evaluates against thresholds.

    SIMULATION NOTE: This does not perform real cloud deployment.
    It simulates the validation logic that would be applied during
    a real canary rollout to demonstrate the workflow correctly.
    """

    def __init__(self, thresholds: dict | None = None):
        self.thresholds = {**DEFAULT_CANARY_THRESHOLDS, **(thresholds or {})}

    async def run_canary(
        self,
        *,
        scenario: str = "pass",   # "pass" | "fail"
        service: str,
        patch_hash: str,
        seed: int | None = None,
    ) -> CanaryResult:
        """
        Run simulated canary health checks.
        scenario="pass"  → produces healthy metrics (within thresholds)
        scenario="fail"  → produces degraded metrics (outside thresholds)
        """
        logger.info(f"[Canary] Starting simulated canary for {service} (scenario={scenario})")

        rng = random.Random(seed or hash(patch_hash) % (2**31))
        polls = self.thresholds["health_check_passes"]
        healthy_polls = 0

        for i in range(polls):
            await asyncio.sleep(self.thresholds["poll_interval_seconds"])
            healthy = scenario == "pass" or (scenario == "fail" and i == 0 and rng.random() > 0.7)
            if healthy:
                healthy_polls += 1
            logger.info(f"[Canary] Poll {i+1}/{polls}: {'HEALTHY' if healthy else 'DEGRADED'}")

        if scenario == "pass":
            error_rate     = round(rng.uniform(0.001, 0.012), 4)
            p99_latency_ms = round(rng.uniform(80, 280), 1)
        else:
            error_rate     = round(rng.uniform(0.05, 0.25), 4)
            p99_latency_ms = round(rng.uniform(800, 3000), 1)

        metrics = CanaryMetrics(
            error_rate=error_rate,
            p99_latency_ms=p99_latency_ms,
            health_polls=polls,
            healthy_polls=healthy_polls,
            traffic_percent=self.thresholds["min_traffic_percent"],
        )

        # Deterministic threshold evaluation
        err_ok     = error_rate     <= self.thresholds["error_rate_threshold"]
        latency_ok = p99_latency_ms <= self.thresholds["latency_threshold_ms"]
        polls_ok   = healthy_polls  >= polls

        passed = err_ok and latency_ok and polls_ok

        if passed:
            reason = f"Canary healthy: error_rate={error_rate:.2%}, p99={p99_latency_ms:.0f}ms"
        else:
            failures = []
            if not err_ok:     failures.append(f"error_rate={error_rate:.2%} > threshold {self.thresholds['error_rate_threshold']:.2%}")
            if not latency_ok: failures.append(f"p99_latency={p99_latency_ms:.0f}ms > threshold {self.thresholds['latency_threshold_ms']}ms")
            if not polls_ok:   failures.append(f"only {healthy_polls}/{polls} health polls passed")
            reason = "Canary degraded: " + "; ".join(failures)

        logger.info(f"[Canary] Result: {'PASS' if passed else 'FAIL'} — {reason}")
        return CanaryResult(passed=passed, metrics=metrics, reason=reason)
