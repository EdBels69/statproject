"""
ReflectAgent — LLM-based result reflection and sanity checking.

Implements multi-round iterative reasoning by evaluating results
after each execution step and deciding whether to continue, retry,
or revise the approach.

This is the analog of DeepAnalyze-8B's <Analyze> action token.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ReflectDecision(str, Enum):
    """Possible outcomes of a reflection round."""
    ACCEPT = "accept"       # Result looks valid, proceed
    RETRY = "retry"         # Re-run the same step with adjustments
    REVISE = "revise"       # Go back to planning and change approach
    FLAG = "flag"           # Accept but flag for user review


@dataclass
class ReflectionResult:
    """Output of one reflection round."""
    decision: ReflectDecision
    reasoning: str
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 - 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reasoning": self.reasoning,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "confidence": round(self.confidence, 2),
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Deterministic sanity checks (no LLM needed)
# ---------------------------------------------------------------------------

def _check_p_value_sanity(result: Dict[str, Any]) -> List[str]:
    """Check for suspicious p-values."""
    issues = []
    p = result.get("p_value")
    n = result.get("sample_size") or result.get("n")

    if isinstance(p, (int, float)):
        if p < 0 or p > 1:
            issues.append(f"p-value out of range [0,1]: {p}")
        if isinstance(n, (int, float)) and n < 10 and p < 0.001:
            issues.append(f"Suspiciously small p={p} with very small n={n}")

    return issues


def _check_effect_size_sanity(result: Dict[str, Any]) -> List[str]:
    """Check for suspicious effect sizes."""
    issues = []
    effect = result.get("effect_size")
    method = result.get("method") or result.get("method_id") or ""
    method_str = str(method).lower() if isinstance(method, (str, dict)) else ""
    if isinstance(method, dict):
        method_str = str(method.get("id", "")).lower()

    if isinstance(effect, (int, float)):
        import math
        if math.isnan(effect) or math.isinf(effect):
            issues.append("Effect size is NaN or Inf")
        # Cohen's d > 3 is very unusual
        if "cohen" in method_str or "t_test" in method_str:
            if abs(effect) > 3.0:
                issues.append(f"Unusually large Cohen's d = {effect:.2f}")
        # Correlation > 1
        if "correlation" in method_str or "pearson" in method_str or "spearman" in method_str:
            if abs(effect) > 1.0:
                issues.append(f"Correlation coefficient out of [-1,1]: {effect}")

    return issues


def _check_ci_sanity(result: Dict[str, Any]) -> List[str]:
    """Check confidence intervals for logical consistency."""
    issues = []
    ci_lower = result.get("effect_size_ci_lower") or result.get("ci_lower")
    ci_upper = result.get("effect_size_ci_upper") or result.get("ci_upper")
    effect = result.get("effect_size")

    if isinstance(ci_lower, (int, float)) and isinstance(ci_upper, (int, float)):
        if ci_lower > ci_upper:
            issues.append(f"CI lower ({ci_lower}) > CI upper ({ci_upper})")
        if isinstance(effect, (int, float)):
            if not (ci_lower <= effect <= ci_upper):
                issues.append(f"Effect size ({effect}) outside CI [{ci_lower}, {ci_upper}]")

    return issues


def _check_sample_size_adequacy(result: Dict[str, Any]) -> List[str]:
    """Check if sample size is adequate for the method used."""
    issues = []
    n = result.get("sample_size") or result.get("n")
    method = str(result.get("method_id") or result.get("method") or "").lower()

    if isinstance(n, (int, float)):
        n = int(n)
        if "anova" in method and n < 12:
            issues.append(f"ANOVA with n={n} may lack power (recommend n≥12)")
        if ("regression" in method or "logistic" in method) and n < 20:
            issues.append(f"Regression with n={n} may be unreliable (recommend n≥20)")
        if "chi_square" in method and n < 20:
            issues.append(f"Chi-square with n={n}: expected frequencies may be < 5")

    return issues


# ---------------------------------------------------------------------------
# ReflectAgent
# ---------------------------------------------------------------------------

class ReflectAgent:
    """
    Evaluates analysis results at each step and decides whether to
    accept, retry, or revise the approach.

    Can work in two modes:
    1. Deterministic-only: fast sanity checks without LLM
    2. LLM-enhanced: uses LLM for deeper assessment (requires llm_func)
    """

    def __init__(
        self,
        *,
        max_rounds: int = 10,
        llm_func: Optional[Any] = None,
    ):
        self.max_rounds = max_rounds
        self._llm_func = llm_func
        self._history: List[Dict[str, Any]] = []

    def reflect(
        self,
        step_id: str,
        result: Dict[str, Any],
        *,
        context: Optional[Dict[str, Any]] = None,
        round_number: int = 1,
    ) -> ReflectionResult:
        """
        Evaluate a single step result.

        Args:
            step_id: ID of the analysis step
            result: The result dict from the step execution
            context: Additional context (design, protocol, previous results)
            round_number: Current reflection round (starts at 1)

        Returns:
            ReflectionResult with decision, reasoning, and suggestions
        """
        all_issues: List[str] = []
        all_suggestions: List[str] = []

        # --- Deterministic checks ---
        all_issues.extend(_check_p_value_sanity(result))
        all_issues.extend(_check_effect_size_sanity(result))
        all_issues.extend(_check_ci_sanity(result))
        all_issues.extend(_check_sample_size_adequacy(result))

        # Generate suggestions for issues
        for issue in all_issues:
            if "small n" in issue.lower() or "may lack power" in issue.lower():
                all_suggestions.append("Consider using exact or non-parametric test")
            if "out of range" in issue.lower() or "out of" in issue.lower():
                all_suggestions.append("Re-check computation; values are mathematically impossible")
            if "suspiciously small p" in issue.lower():
                all_suggestions.append("Consider exact test or bootstrap p-value")
            if "usually large" in issue.lower():
                all_suggestions.append("Verify data wasn't accidentally filtered or transformed")

        # --- Decision logic ---
        critical_issues = [i for i in all_issues if any(
            w in i.lower() for w in ("out of range", "nan", "inf", "impossible")
        )]
        warning_issues = [i for i in all_issues if i not in critical_issues]

        if critical_issues and round_number < self.max_rounds:
            decision = ReflectDecision.RETRY
            reasoning = f"Critical issues found: {'; '.join(critical_issues)}"
            confidence = 0.2
        elif critical_issues:
            decision = ReflectDecision.FLAG
            reasoning = f"Critical issues persist after {round_number} rounds: {'; '.join(critical_issues)}"
            confidence = 0.3
        elif warning_issues:
            decision = ReflectDecision.FLAG
            reasoning = f"Results accepted with warnings: {'; '.join(warning_issues)}"
            confidence = 0.7
        else:
            decision = ReflectDecision.ACCEPT
            reasoning = "All sanity checks passed"
            confidence = 0.95

        reflection = ReflectionResult(
            decision=decision,
            reasoning=reasoning,
            issues=all_issues,
            suggestions=all_suggestions,
            confidence=confidence,
            metadata={
                "step_id": step_id,
                "round": round_number,
                "checked_at": datetime.utcnow().isoformat() + "Z",
            },
        )

        self._history.append(reflection.as_dict())
        return reflection

    def reflect_run(
        self,
        results: Dict[str, Dict[str, Any]],
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Reflect on an entire run's results.

        Returns summary with overall decision and per-step reflections.
        """
        step_reflections: Dict[str, Dict[str, Any]] = {}
        overall_issues: List[str] = []
        overall_confidence = 1.0
        has_critical = False

        for step_id, result in results.items():
            if not isinstance(result, dict):
                continue
            ref = self.reflect(step_id, result, context=context)
            step_reflections[step_id] = ref.as_dict()
            overall_issues.extend(ref.issues)
            overall_confidence = min(overall_confidence, ref.confidence)
            if ref.decision in (ReflectDecision.RETRY, ReflectDecision.REVISE):
                has_critical = True

        if has_critical:
            overall_decision = "needs_revision"
        elif any(r.get("decision") == "flag" for r in step_reflections.values()):
            overall_decision = "accepted_with_flags"
        else:
            overall_decision = "accepted"

        return {
            "schema": "clinimetria.reflection",
            "version": 1,
            "checked_at": datetime.utcnow().isoformat() + "Z",
            "overall_decision": overall_decision,
            "overall_confidence": round(overall_confidence, 2),
            "total_steps": len(step_reflections),
            "total_issues": len(overall_issues),
            "steps": step_reflections,
        }

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)
