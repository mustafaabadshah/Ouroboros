"""
Evaluation Budget, Token Ceilings, and Request Pacing Controller.
Enforces:
1. Strict count of actual model requests across all roles (Planner, Coder, Repair).
2. Hard total-token ceiling (60,000 tokens) with pre-dispatch reservation and post-call reconciliation.
3. Dollar cost ceiling ($0.10 USD) based on verified model pricing, failing closed if pricing is unknown.
4. Shared minimum request pacing (3.0s interval) with injectible clock and sleeper for fast tests.
5. Structured classification of budget and provider error categories.
"""

import time
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Tuple, Callable


class ProviderErrorCategory(str, Enum):
    AUTH_ERROR = "PROVIDER_AUTH_ERROR"
    RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    TIMEOUT = "PROVIDER_TIMEOUT"
    UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    MALFORMED_RESPONSE = "PROVIDER_MALFORMED_RESPONSE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    TOKEN_CEILING_EXCEEDED = "TOKEN_CEILING_EXCEEDED"
    COST_CEILING_EXCEEDED = "COST_CEILING_EXCEEDED"


# Verified published rates for Groq remote inference models (USD per 1,000,000 tokens)
# Source: Groq Cloud official pricing for supported models (October 2026)
DEFAULT_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "qwen/qwen3.8-27b": {
        "input_per_m": 0.20,
        "output_per_m": 0.20
    },
    "llama-3.3-70b-versatile": {
        "input_per_m": 0.59,
        "output_per_m": 0.79
    },
    "llama-3.1-8b-instant": {
        "input_per_m": 0.05,
        "output_per_m": 0.08
    },
    "qwen2.5-coder:1.5b": {
        "input_per_m": 0.00,  # Local Ollama CPU execution
        "output_per_m": 0.00
    },
    "mock": {
        "input_per_m": 0.00,
        "output_per_m": 0.00
    }
}


class EvaluationBudgetController:
    """
    Central controller tracking and enforcing request budgets, token ceilings,
    dollar spend, and pacing across all agent roles.
    """

    def __init__(
        self,
        max_requests: int = 120,
        max_tokens: int = 60000,
        max_cost_usd: Optional[float] = 0.10,
        min_pacing_seconds: float = 3.0,
        clock: Optional[Callable[[], float]] = None,
        sleeper: Optional[Callable[[float], Any]] = None,
        pricing_known: bool = True,
        pricing_table: Optional[Dict[str, Dict[str, float]]] = None
    ):
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.min_pacing_seconds = min_pacing_seconds

        self.clock = clock or time.perf_counter
        self.sleeper = sleeper or asyncio.sleep

        self.pricing_known = pricing_known
        self.pricing_table = pricing_table or DEFAULT_MODEL_PRICING

        # Usage tracking
        self.total_requests: int = 0
        self.total_tokens_in: int = 0
        self.total_tokens_out: int = 0
        self.total_tokens: int = 0
        self.total_cost_usd: float = 0.0

        # Reservation tracking
        self.active_reservations: int = 0
        self.reserved_tokens: int = 0
        self.reserved_cost_usd: float = 0.0

        self.last_request_timestamp: Optional[float] = None
        self.is_exhausted: bool = False
        self.exhaustion_reason: Optional[str] = None

    def _get_model_rates(self, model_name: str) -> Optional[Dict[str, float]]:
        if not self.pricing_known:
            return None
        return self.pricing_table.get(model_name)

    async def wait_pacing(self) -> float:
        """
        Enforces minimum interval between outbound requests.
        Returns the duration waited in seconds.
        """
        if self.last_request_timestamp is not None and self.min_pacing_seconds > 0:
            elapsed = self.clock() - self.last_request_timestamp
            if elapsed < self.min_pacing_seconds:
                wait_time = self.min_pacing_seconds - elapsed
                await self.sleeper(wait_time)
                return wait_time
        return 0.0

    def check_and_reserve(
        self,
        estimated_prompt_tokens: int = 1000,
        max_output_tokens: int = 2000,
        model_name: str = "qwen/qwen3.8-27b",
        role: str = "Agent"
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks all budget constraints and reserves resources before dispatch.
        Fails closed before outbound network calls.
        """
        if self.is_exhausted:
            return False, f"Budget already exhausted: {self.exhaustion_reason}"

        # 1. Request count check
        if self.total_requests >= self.max_requests:
            self.is_exhausted = True
            self.exhaustion_reason = f"Maximum request limit of {self.max_requests} reached."
            return False, self.exhaustion_reason

        # 2. Token ceiling check (actual + active reservations + proposed reservation)
        est_tokens = estimated_prompt_tokens + max_output_tokens
        projected_tokens = self.total_tokens + self.reserved_tokens + est_tokens
        if projected_tokens > self.max_tokens:
            self.is_exhausted = True
            self.exhaustion_reason = (
                f"Token ceiling of {self.max_tokens} tokens would be exceeded. "
                f"(Current actual: {self.total_tokens}, reserved: {self.reserved_tokens}, "
                f"requested: {est_tokens}, projected: {projected_tokens})."
            )
            return False, self.exhaustion_reason

        # 3. Cost ceiling check
        if self.max_cost_usd is not None:
            if not self.pricing_known:
                self.is_exhausted = True
                self.exhaustion_reason = (
                    "Cost ceiling is enforced but pricing data is marked unknown. "
                    "Failing closed to prevent unmonitored financial spend."
                )
                return False, self.exhaustion_reason

            rates = self._get_model_rates(model_name)
            if not rates:
                self.is_exhausted = True
                self.exhaustion_reason = f"Pricing data not available for model '{model_name}'. Failing closed."
                return False, self.exhaustion_reason

            est_cost = (
                (estimated_prompt_tokens / 1_000_000.0 * rates["input_per_m"]) +
                (max_output_tokens / 1_000_000.0 * rates["output_per_m"])
            )
            projected_cost = self.total_cost_usd + self.reserved_cost_usd + est_cost
            if projected_cost > self.max_cost_usd:
                self.is_exhausted = True
                self.exhaustion_reason = (
                    f"Cost ceiling of ${self.max_cost_usd:.4f} USD would be exceeded. "
                    f"(Current actual: ${self.total_cost_usd:.4f}, reserved: ${self.reserved_cost_usd:.4f}, "
                    f"requested: ${est_cost:.4f}, projected: ${projected_cost:.4f})."
                )
                return False, self.exhaustion_reason

            self.reserved_cost_usd += est_cost

        # Reserve and record request
        self.total_requests += 1
        self.active_reservations += 1
        self.reserved_tokens += est_tokens
        self.last_request_timestamp = self.clock()

        return True, None

    def reconcile_usage(
        self,
        actual_tokens_in: Optional[int],
        actual_tokens_out: Optional[int],
        estimated_prompt_tokens: int = 1000,
        max_output_tokens: int = 2000,
        model_name: str = "qwen/qwen3.8-27b"
    ):
        """
        Reconciles pre-dispatch reservations with actual reported usage.
        """
        est_tokens = estimated_prompt_tokens + max_output_tokens
        self.reserved_tokens = max(0, self.reserved_tokens - est_tokens)
        self.active_reservations = max(0, self.active_reservations - 1)

        tok_in = actual_tokens_in or 0
        tok_out = actual_tokens_out or 0
        call_tokens = tok_in + tok_out

        self.total_tokens_in += tok_in
        self.total_tokens_out += tok_out
        self.total_tokens += call_tokens

        # Reconcile cost
        if self.max_cost_usd is not None and self.pricing_known:
            rates = self._get_model_rates(model_name)
            if rates:
                est_cost = (
                    (estimated_prompt_tokens / 1_000_000.0 * rates["input_per_m"]) +
                    (max_output_tokens / 1_000_000.0 * rates["output_per_m"])
                )
                self.reserved_cost_usd = max(0.0, self.reserved_cost_usd - est_cost)

                actual_cost = (
                    (tok_in / 1_000_000.0 * rates["input_per_m"]) +
                    (tok_out / 1_000_000.0 * rates["output_per_m"])
                )
                self.total_cost_usd += actual_cost

    def get_summary(self) -> Dict[str, Any]:
        """Returns structured accounting state."""
        return {
            "total_requests": self.total_requests,
            "max_requests": self.max_requests,
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_tokens": self.total_tokens,
            "max_tokens": self.max_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "max_cost_usd": self.max_cost_usd,
            "is_exhausted": self.is_exhausted,
            "exhaustion_reason": self.exhaustion_reason,
            "pricing_known": self.pricing_known,
            "pacing_delay_seconds": self.min_pacing_seconds
        }
