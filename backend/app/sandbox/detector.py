import time
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from app.core.security import run_safe_subprocess
from app.core.logging import logger

class SandboxDetector:
    """
    Detects available sandboxing runtime capabilities on the host system.
    Determines whether Docker is running or if restricted local isolation must be engaged.
    Maintains a bounded TTL cache to eliminate 5-10 second Windows named pipe timeouts
    on repeated capability checks during evaluation and test suites.
    """
    _cache: Optional[Dict[str, Any]] = None
    _cache_time: float = 0.0
    _cache_ttl_seconds: float = 30.0
    _docker_running: Optional[bool] = None
    _docker_cli: Optional[bool] = None
    _docker_probe_time: float = 0.0

    @classmethod
    def reset_cache(cls) -> None:
        """Forces the capability cache to expire immediately."""
        cls._cache = None
        cls._cache_time = 0.0
        cls._docker_running = None
        cls._docker_cli = None
        cls._docker_probe_time = 0.0

    @classmethod
    async def detect_capabilities(cls, force_refresh: bool = False) -> Dict[str, Any]:
        now = time.monotonic()
        from app.core.config import settings

        fail_closed_required = bool(settings.REQUIRE_CONTAINER_SANDBOX or settings.SANDBOX_MODE == "fail_closed")
        sandbox_mode = getattr(settings, "SANDBOX_MODE", "auto")

        if (
            not force_refresh
            and cls._cache is not None
            and (now - cls._cache_time) < cls._cache_ttl_seconds
            and cls._cache.get("fail_closed_required") == fail_closed_required
            and cls._cache.get("sandbox_mode") == sandbox_mode
        ):
            return dict(cls._cache)

        # Re-probe Docker if force_refresh or probe expired
        if force_refresh or cls._docker_probe_time == 0 or (now - cls._docker_probe_time) >= cls._cache_ttl_seconds:
            docker_cli = bool(shutil.which("docker") or shutil.which("docker.exe"))
            docker_running = False

            if docker_cli:
                try:
                    code, out, err = await run_safe_subprocess(
                        ["docker", "info"],
                        cwd=Path("."),
                        timeout=5
                    )
                    if code == 0 and "Server" in out and "ERROR" not in out:
                        docker_running = True
                except Exception:
                    docker_running = False

            cls._docker_cli = docker_cli
            cls._docker_running = docker_running
            cls._docker_probe_time = now
        else:
            docker_cli = cls._docker_cli
            docker_running = cls._docker_running

        can_execute = True
        reason_code = "OK"

        if sandbox_mode == "restricted_local":
            if fail_closed_required:
                preferred_mode = "blocked"
                can_execute = False
                reason_code = "RUNTIME_UNAVAILABLE"
                message = "EXECUTION BLOCKED: Strict container sandbox required by policy, but restricted_local mode configured."
            else:
                preferred_mode = "restricted_local"
                reason_code = "NONE"
                message = "Restricted local subprocess worktree sandbox enforced by configuration."
        elif not docker_running and fail_closed_required:
            preferred_mode = "blocked"
            can_execute = False
            reason_code = "RUNTIME_UNAVAILABLE"
            message = "EXECUTION BLOCKED: Strict container sandbox required by policy, but Docker is offline."
        elif docker_running:
            # Check if required sandbox image is present locally before committing to docker mode
            sandbox_image = getattr(settings, "DOCKER_SANDBOX_IMAGE", "ouroboros-pytest-sandbox:3.12")
            image_exists = False
            try:
                code, out, _ = await run_safe_subprocess(
                    ["docker", "image", "inspect", sandbox_image],
                    cwd=Path("."),
                    timeout=3
                )
                image_exists = (code == 0)
            except Exception:
                image_exists = False

            if image_exists:
                preferred_mode = "docker"
                reason_code = "NONE"
                message = "Docker container sandbox active."
            elif fail_closed_required:
                preferred_mode = "blocked"
                can_execute = False
                reason_code = "RUNTIME_UNAVAILABLE"
                message = f"EXECUTION BLOCKED: Strict container sandbox required, but image '{sandbox_image}' is not found locally."
            else:
                preferred_mode = "restricted_local"
                reason_code = "NONE"
                message = f"Docker active but sandbox image '{sandbox_image}' absent. Restricted local sandbox active."
        else:
            preferred_mode = "restricted_local"
            reason_code = "NONE"
            message = "Docker offline. Restricted local subprocess worktree sandbox active."

        result = {
            "docker_installed": bool(docker_cli),
            "docker_running": bool(docker_running),
            "preferred_mode": preferred_mode,
            "can_execute": can_execute,
            "reason_code": reason_code,
            "fail_closed_required": fail_closed_required,
            "sandbox_mode": sandbox_mode,
            "message": message
        }
        cls._cache = result
        cls._cache_time = now
        return dict(result)

sandbox_detector = SandboxDetector()
