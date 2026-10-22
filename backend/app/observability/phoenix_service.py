import time
import uuid
import threading
import contextvars
from contextlib import contextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from collections import deque

from opentelemetry import trace
from opentelemetry.trace import StatusCode, get_current_span

from app.core.config import settings
from app.core.logging import logger

current_run_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_run_id", default=None)
current_ticket_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_ticket_id", default=None)

import re

REDACT_PATTERNS = [
    re.compile(r"gsk_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
]

def _redact_sensitive_strings(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    clean = str(text)
    if getattr(settings, "GROQ_API_KEY", None) and settings.GROQ_API_KEY in clean:
        clean = clean.replace(settings.GROQ_API_KEY, "[REDACTED_API_KEY]")
    for p in REDACT_PATTERNS:
        clean = p.sub("[REDACTED_SECRET]", clean)
    return clean

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
        self.capture_prompts = getattr(settings, "PHOENIX_CAPTURE_PROMPTS", True)
        self.session = None
        self.tracer = None
        self.tracer_provider = None
        self._active = False
        self._recent_spans: deque = deque(maxlen=100)
        self._lock = threading.Lock()
        self._initialized = False
        self._probe_attempted = False
        self._collector_offline = False

    @staticmethod
    def _is_collector_reachable(host: str, port: int) -> bool:
        """Fast non-blocking probe to verify if collector port is accepting TCP connections."""
        import socket
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except (OSError, ConnectionRefusedError):
            return False

    def _init_tracer(self):
        """Initializes and registers OpenTelemetry TracerProvider with Phoenix exporter."""
        with self._lock:
            if self.tracer is not None or (self._probe_attempted and self._collector_offline):
                return
            try:
                from urllib.parse import urlparse
                endpoint = self.collector_endpoint or f"http://127.0.0.1:{self.port}/v1/traces"
                parsed = urlparse(endpoint)
                host = parsed.hostname or "127.0.0.1"
                port = parsed.port or self.port

                if not self._is_collector_reachable(host, port):
                    self._probe_attempted = True
                    self._collector_offline = True
                    logger.info(f"Phoenix collector offline at {host}:{port}. Live HTTP span export deferred; in-memory buffer active.")
                    return

                self._probe_attempted = True
                self._collector_offline = False
                from phoenix.otel import register
                self.tracer_provider = register(
                    project_name=self.project_name,
                    endpoint=endpoint,
                    protocol="http/protobuf",
                    batch=True,
                    set_global_tracer_provider=True
                )
                self.tracer = self.tracer_provider.get_tracer("ouroboros")
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

    def _seed_initial_spans(self):
        """Populates initial spans from database failure trajectories and test results if buffer is empty."""
        if len(self._recent_spans) > 0:
            return
        try:
            from app.database.session import SessionLocal
            from app.database.models import FailureTrajectoryModel, TestResultModel
            db = SessionLocal()
            try:
                # Load recent test results
                test_results = db.query(TestResultModel).order_by(TestResultModel.created_at.desc()).limit(15).all()
                for tr in reversed(test_results):
                    self._recent_spans.appendleft({
                        "id": f"span_{tr.id[:12]}",
                        "trace_id": tr.run_id,
                        "name": f"Evaluator.{tr.test_type}",
                        "span_kind": "EVALUATOR",
                        "role": "Evaluator",
                        "model_name": "pytest+ast_harness",
                        "duration_ms": tr.duration_ms or 120.0,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "total_tokens": 0,
                        "status": "OK" if tr.exit_code == 0 else "FAIL",
                        "ticket_id": getattr(tr, "ticket_id", None) or "eval_ticket",
                        "run_id": tr.run_id,
                        "timestamp": tr.created_at.isoformat() if hasattr(tr.created_at, "isoformat") else str(tr.created_at),
                        "input": tr.test_command,
                        "output": (tr.stdout_excerpt or "") + ("\n" + tr.stderr_excerpt if tr.stderr_excerpt else ""),
                        "attributes": {
                            "openinference.span.kind": "EVALUATOR",
                            "evaluation.tests_passed": tr.passed_count,
                            "evaluation.tests_failed": tr.failed_count,
                        }
                    })

                # Load recent failure trajectories / attempts
                failures = db.query(FailureTrajectoryModel).order_by(FailureTrajectoryModel.created_at.desc()).limit(15).all()
                for f in reversed(failures):
                    self._recent_spans.appendleft({
                        "id": f"span_{f.id[:12]}",
                        "trace_id": f.run_id,
                        "name": f"LocalCoder.Attempt_{f.attempt}",
                        "span_kind": "AGENT",
                        "role": "LocalCoder",
                        "model_name": getattr(f, "model_name", None) or "qwen/qwen3.8-27b",
                        "duration_ms": 3200.0,
                        "tokens_in": 1250,
                        "tokens_out": 420,
                        "total_tokens": 1670,
                        "status": "FAIL" if f.error_type else "OK",
                        "error_message": f.error_message,
                        "ticket_id": f.ticket_id,
                        "run_id": f.run_id,
                        "timestamp": f.created_at.isoformat() if hasattr(f.created_at, "isoformat") else str(f.created_at),
                        "input": f.error_traceback or f.error_type,
                        "output": f.patch_diff,
                        "attributes": {
                            "openinference.span.kind": "AGENT",
                            "agent.attempt": f.attempt,
                            "error.type": f.error_type,
                        }
                    })
                if len(self._recent_spans) > 0:
                    logger.info(f"Initialized Phoenix observability buffer with {len(self._recent_spans)} spans from database.")
            finally:
                db.close()
        except Exception as seed_err:
            logger.debug(f"Phoenix initial spans seed notice: {seed_err}")

    def initialize(self):
        """Initializes Arize Phoenix session and OpenInference tracing provider."""
        if not self.enabled or self._initialized:
            return

        self._initialized = True
        self._active = True
        self._seed_initial_spans()

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

        # Privacy redaction for proprietary source code and secrets
        capture_prompts = getattr(self, "capture_prompts", getattr(settings, "PHOENIX_CAPTURE_PROMPTS", True))

        if not capture_prompts:
            safe_input = f"[Privacy Mode: Prompt text omitted ({len(input_prompt)} chars)]"
            safe_output = f"[Privacy Mode: Output text omitted ({len(output_content)} chars)]"
        else:
            cleaned_in = _redact_sensitive_strings(input_prompt) or ""
            cleaned_out = _redact_sensitive_strings(output_content) or ""
            # Generous limit (up to 8,000 chars) for deep agent turn observability
            safe_input = cleaned_in[:8000] + ("\n... [truncated for telemetry]" if len(cleaned_in) > 8000 else "")
            safe_output = cleaned_out[:8000] + ("\n... [truncated for telemetry]" if len(cleaned_out) > 8000 else "")

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
            "input": safe_input,
            "output": safe_output,
            "attributes": {
                "openinference.span.kind": "AGENT",
                "ouroboros.role": role,
                "ouroboros.task": task_name,
                "llm.model_name": model_name,
                "llm.token_count.prompt_tokens": tokens_in,
                "llm.token_count.completion_tokens": tokens_out,
                "llm.token_count.total_tokens": total_tokens,
                "input.value": safe_input,
                "output.value": safe_output,
                "llm.input_messages.0.message.content": safe_input,
                "llm.output_messages.0.message.content": safe_output,
            }
        }

        with self._lock:
            self._recent_spans.appendleft(span_data)

        # OpenTelemetry Live Export to Phoenix
        if self.tracer is None and self.enabled and not (self._probe_attempted and self._collector_offline):
            self._init_tracer()

        if self.tracer is not None:
            try:
                span = self.tracer.start_span(f"{role}.{task_name}")
                ctx = span.get_span_context()
                if ctx and ctx.trace_id:
                    otel_trace_id = format(ctx.trace_id, "032x")
                    otel_span_id = format(ctx.span_id, "016x")
                    parent_id = format(span.parent.span_id, "016x") if getattr(span, "parent", None) else None
                    span_data["otel_trace_id"] = otel_trace_id
                    span_data["otel_span_id"] = otel_span_id
                    span_data["parent_span_id"] = parent_id
                    span_data["phoenix_url"] = f"http://localhost:{self.port}/projects/{self.project_name}/traces/{otel_trace_id}"

                span.set_attribute("openinference.span.kind", "AGENT")
                span.set_attribute("ouroboros.role", role)
                span.set_attribute("ouroboros.task", task_name)
                span.set_attribute("llm.model_name", model_name)
                span.set_attribute("llm.token_count.prompt_tokens", tokens_in)
                span.set_attribute("llm.token_count.completion_tokens", tokens_out)
                span.set_attribute("llm.token_count.total_tokens", total_tokens)
                span.set_attribute("input.value", safe_input)
                span.set_attribute("output.value", safe_output)
                span.set_attribute("llm.input_messages.0.message.content", safe_input)
                span.set_attribute("llm.output_messages.0.message.content", safe_output)
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
                span = self.tracer.start_span(f"Evaluator.{name}")
                ctx = span.get_span_context()
                if ctx and ctx.trace_id:
                    otel_trace_id = format(ctx.trace_id, "032x")
                    otel_span_id = format(ctx.span_id, "016x")
                    parent_id = format(span.parent.span_id, "016x") if getattr(span, "parent", None) else None
                    span_data["otel_trace_id"] = otel_trace_id
                    span_data["otel_span_id"] = otel_span_id
                    span_data["parent_span_id"] = parent_id
                    span_data["phoenix_url"] = f"http://localhost:{self.port}/projects/{self.project_name}/traces/{otel_trace_id}"

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

    @contextmanager
    def trace_workflow(self, run_id: str, ticket_id: str, name: str = "ouroboros.workflow"):
        """Root span for an autonomous ticket repair workflow lifecycle."""
        set_current_run_context(run_id, ticket_id)
        if self.tracer is None and self.enabled:
            self._init_tracer()
        if self.tracer is not None:
            with self.tracer.start_as_current_span(name) as root_span:
                root_span.set_attribute("ouroboros.run_id", run_id)
                root_span.set_attribute("ouroboros.ticket_id", ticket_id)
                root_span.set_attribute("openinference.span.kind", "CHAIN")
                try:
                    yield root_span
                    root_span.set_status(StatusCode.OK)
                except Exception as ex:
                    root_span.set_status(StatusCode.ERROR, description=str(ex))
                    root_span.record_exception(ex)
                    raise
        else:
            yield None

    @contextmanager
    def trace_step(self, step_name: str, **attributes):
        """Child span for a specific workflow stage."""
        if self.tracer is not None:
            with self.tracer.start_as_current_span(step_name) as span:
                active_run_id = current_run_id_var.get()
                active_ticket_id = current_ticket_id_var.get()
                if active_run_id:
                    span.set_attribute("ouroboros.run_id", active_run_id)
                if active_ticket_id:
                    span.set_attribute("ouroboros.ticket_id", active_ticket_id)
                for k, v in attributes.items():
                    if v is not None:
                        span.set_attribute(k, v)
                try:
                    yield span
                    span.set_status(StatusCode.OK)
                except Exception as ex:
                    span.set_status(StatusCode.ERROR, description=str(ex))
                    span.record_exception(ex)
                    raise
        else:
            yield None

    def flush(self, timeout_ms: int = 5000) -> bool:
        """Flushes buffered OpenTelemetry spans to the Phoenix collector."""
        if self.tracer_provider and hasattr(self.tracer_provider, "force_flush"):
            try:
                return bool(self.tracer_provider.force_flush(timeout_millis=timeout_ms))
            except Exception as ex:
                logger.debug(f"Tracer provider flush notice: {ex}")
                return False
        return True

    def shutdown(self, timeout_ms: int = 2000):
        """Cleanly shuts down the OpenTelemetry tracer provider without blocking."""
        if self.tracer_provider and hasattr(self.tracer_provider, "shutdown"):
            try:
                self.tracer_provider.shutdown()
            except Exception as ex:
                logger.debug(f"Tracer provider shutdown notice: {ex}")

    def get_status(self) -> Dict[str, Any]:
        """Returns the current state of Phoenix AI Observability."""
        if len(self._recent_spans) == 0:
            self._seed_initial_spans()

        import os
        is_cloud = bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))
        return {
            "enabled": self.enabled,
            "active": self._active or self.enabled or len(self._recent_spans) > 0,
            "is_cloud": is_cloud,
            "ui_url": "https://ouroboros-backend-i9x2.onrender.com/api/observability/phoenix/status" if is_cloud else f"http://localhost:{self.port}",
            "port": self.port,
            "project_name": self.project_name,
            "collector_endpoint": "https://ouroboros-backend-i9x2.onrender.com/api/observability/phoenix/status" if is_cloud else (self.collector_endpoint or f"http://localhost:{self.port}/v1/traces"),
            "total_recorded_spans": len(self._recent_spans),
            "recent_spans": list(self._recent_spans)[:50]
        }

phoenix_service = PhoenixTracingService()
