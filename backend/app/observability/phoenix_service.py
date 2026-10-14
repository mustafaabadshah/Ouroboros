import time
import uuid
import threading
import contextvars
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from collections import deque

from app.core.config import settings
from app.core.logging import logger

current_run_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_run_id", default=None)
current_ticket_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_ticket_id", default=None)

def set_current_run_context(run_id: Optional[str], ticket_id: Optional[str]):
    """Sets contextual run and ticket IDs for ambient OpenTelemetry tracing."""
    current_run_id_var.set(run_id)
    current_ticket_id_var.set(ticket_id)

class PhoenixTracingService:
    """
    Arize Phoenix AI Observability & OpenTelemetry Tracing Service.
    Instrumented for Project Ouroboros:
    - Traces agent execution spans (Architect, Planner, Coder, Test Engineer, Evaluator, Reviewer).
    - Embedded Arize Phoenix UI session management (default http://localhost:6006).
    - OpenTelemetry / OpenInference export to Arize Phoenix collector for live tracing dashboard.
    - Captures model name, latency, prompt tokens, completion tokens, and evaluation verdicts.
    - Maintains an in-memory buffer of recent spans for rapid dashboard display.
    """

    def __init__(self):
        self.enabled = settings.PHOENIX_ENABLED
        self.port = settings.PHOENIX_PORT
        self.project_name = settings.PHOENIX_PROJECT_NAME
        self.collector_endpoint = settings.PHOENIX_COLLECTOR_ENDPOINT
        self.session = None
        self.tracer = None
        self.tracer_provider = None
        self._active = False
        self._recent_spans: deque = deque(maxlen=100)
        self._lock = threading.Lock()
        self._initialized = False

    def _init_tracer(self):
        """Initializes and registers OpenTelemetry TracerProvider with Phoenix exporter."""
        with self._lock:
            if self.tracer is not None:
                return
            try:
                from phoenix.otel import register
                from opentelemetry import trace
                endpoint = self.collector_endpoint or f"http://localhost:{self.port}/v1/traces"
                self.tracer_provider = register(
                    project_name=self.project_name,
                    endpoint=endpoint,
                    protocol="http/protobuf",
                    batch=False,
                    set_global_tracer_provider=True
                )
                self.tracer = trace.get_tracer("ouroboros")
                logger.info(f"Arize Phoenix OpenTelemetry tracer active for project '{self.project_name}' at {endpoint}")
            except Exception as ex:
                logger.debug(f"Arize Phoenix tracer registration notice: {ex}")

    def _launch_phoenix_server(self):
        try:
            import sys
            import phoenix as px
            if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
                try:
                    sys.stdout.reconfigure(encoding='utf-8')
                except Exception:
                    pass
            self.session = px.launch_app(port=self.port, host="127.0.0.1")
            self._active = True
            logger.info(f"Arize Phoenix UI active at http://localhost:{self.port} (Project: {self.project_name})")
            time.sleep(0.5)
            self._init_tracer()
        except Exception as ex:
            logger.warning(f"Phoenix UI background launch notice: {ex}")
            self._active = True
            self._init_tracer()

    def initialize(self):
        """Initializes Arize Phoenix session and OpenInference tracing provider."""
        if not self.enabled or self._initialized:
            return

        self._initialized = True
        self._active = True

        if not self.collector_endpoint:
            thread = threading.Thread(target=self._launch_phoenix_server, daemon=True)
            thread.start()
        else:
            logger.info(f"Arize Phoenix configured with remote collector: {self.collector_endpoint}")
            self._init_tracer()

    def record_agent_span(
        self,
        role: str,
        task_name: str,
        model_name: str,
        input_prompt: str,
        output_content: str,
        duration_ms: float,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        run_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        status: str = "OK",
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records an agent execution span adhering to OpenInference semantic conventions."""
        run_id = run_id or current_run_id_var.get()
        ticket_id = ticket_id or current_ticket_id_var.get()

        span_id = f"span_{uuid.uuid4().hex[:12]}"
        trace_id = run_id or f"trace_{uuid.uuid4().hex[:12]}"

        tokens_in = tokens_in or 0
        tokens_out = tokens_out or 0
        total_tokens = tokens_in + tokens_out

        span_data = {
            "id": span_id,
            "trace_id": trace_id,
            "name": f"{role}.{task_name}",
            "span_kind": "AGENT",
            "role": role,
            "model_name": model_name,
            "duration_ms": round(duration_ms, 2),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": total_tokens,
            "status": status,
            "error_message": error_message,
            "ticket_id": ticket_id,
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": {
                "openinference.span.kind": "AGENT",
                "ouroboros.role": role,
                "ouroboros.task": task_name,
                "llm.model_name": model_name,
                "llm.token_count.prompt_tokens": tokens_in,
                "llm.token_count.completion_tokens": tokens_out,
                "llm.token_count.total_tokens": total_tokens,
                "input.value": input_prompt[:300] + ("..." if len(input_prompt) > 300 else ""),
                "output.value": output_content[:300] + ("..." if len(output_content) > 300 else ""),
            }
        }

        with self._lock:
            self._recent_spans.appendleft(span_data)

        # OpenTelemetry Live Export to Phoenix
        if self.tracer is None and self.enabled:
            self._init_tracer()

        if self.tracer is not None:
            try:
                from opentelemetry.trace import StatusCode
                span = self.tracer.start_span(f"{role}.{task_name}")
                span.set_attribute("openinference.span.kind", "AGENT")
                span.set_attribute("ouroboros.role", role)
                span.set_attribute("ouroboros.task", task_name)
                span.set_attribute("llm.model_name", model_name)
                span.set_attribute("llm.token_count.prompt_tokens", tokens_in)
                span.set_attribute("llm.token_count.completion_tokens", tokens_out)
                span.set_attribute("llm.token_count.total_tokens", total_tokens)
                span.set_attribute("input.value", input_prompt)
                span.set_attribute("output.value", output_content)
                if run_id:
                    span.set_attribute("session.id", run_id)
                    span.set_attribute("ouroboros.run_id", run_id)
                if ticket_id:
                    span.set_attribute("ouroboros.ticket_id", ticket_id)
                if status == "OK":
                    span.set_status(StatusCode.OK)
                else:
                    span.set_status(StatusCode.ERROR, description=error_message or "Agent turn failed")
                span.end()
            except Exception as ex:
                logger.debug(f"Phoenix OpenTelemetry agent span export skipped: {ex}")

        # Log trace point
        logger.info(
            f"[Phoenix Trace] {role}.{task_name} -> {status} ({duration_ms:.1f}ms, {total_tokens} tokens) [model: {model_name}]"
        )
        return span_data

    def record_evaluator_span(
        self,
        name: str,
        run_id: str,
        ticket_id: str,
        verdict: str,
        tests_passed: int,
        tests_failed: int,
        duration_ms: float,
        ast_changes: List[str]
    ) -> Dict[str, Any]:
        """Records a deterministic test & AST evaluation span in Phoenix."""
        run_id = run_id or current_run_id_var.get() or "eval_run"
        ticket_id = ticket_id or current_ticket_id_var.get() or "eval_ticket"

        span_id = f"span_{uuid.uuid4().hex[:12]}"
        span_data = {
            "id": span_id,
            "trace_id": run_id,
            "name": f"Evaluator.{name}",
            "span_kind": "EVALUATOR",
            "role": "Evaluator",
            "model_name": "pytest+ast_harness",
            "duration_ms": round(duration_ms, 2),
            "tokens_in": 0,
            "tokens_out": 0,
            "total_tokens": 0,
            "status": "OK" if verdict == "PASS" else "FAIL",
            "ticket_id": ticket_id,
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": {
                "openinference.span.kind": "EVALUATOR",
                "evaluation.verdict": verdict,
                "evaluation.tests_passed": tests_passed,
                "evaluation.tests_failed": tests_failed,
                "evaluation.ast_changes_count": len(ast_changes),
            }
        }

        with self._lock:
            self._recent_spans.appendleft(span_data)

        # OpenTelemetry Live Export to Phoenix
        if self.tracer is None and self.enabled:
            self._init_tracer()

        if self.tracer is not None:
            try:
                from opentelemetry.trace import StatusCode
                span = self.tracer.start_span(f"Evaluator.{name}")
                span.set_attribute("openinference.span.kind", "EVALUATOR")
                span.set_attribute("evaluation.verdict", verdict)
                span.set_attribute("evaluation.tests_passed", tests_passed)
                span.set_attribute("evaluation.tests_failed", tests_failed)
                span.set_attribute("evaluation.ast_changes_count", len(ast_changes))
                if run_id:
                    span.set_attribute("session.id", run_id)
                    span.set_attribute("ouroboros.run_id", run_id)
                if ticket_id:
                    span.set_attribute("ouroboros.ticket_id", ticket_id)
                span.set_status(StatusCode.OK if verdict == "PASS" else StatusCode.ERROR)
                span.end()
            except Exception as ex:
                logger.debug(f"Phoenix OpenTelemetry evaluator span export skipped: {ex}")

        logger.info(f"[Phoenix Trace] Evaluator.{name} -> Verdict: {verdict} ({duration_ms:.1f}ms)")
        return span_data

    def get_status(self) -> Dict[str, Any]:
        """Returns the current state of Phoenix AI Observability."""
        return {
            "enabled": self.enabled,
            "active": self._active,
            "ui_url": f"http://localhost:{self.port}",
            "port": self.port,
            "project_name": self.project_name,
            "collector_endpoint": self.collector_endpoint or f"http://localhost:{self.port}/v1/traces",
            "total_recorded_spans": len(self._recent_spans),
            "recent_spans": list(self._recent_spans)[:25]
        }

phoenix_service = PhoenixTracingService()
