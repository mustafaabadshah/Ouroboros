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

        if (
            not force_refresh
            and cls._cache is not None
            and (now - cls._cache_time) < cls._cache_ttl_seconds
            and cls._cache.get("fail_closed_required") == fail_closed_required
        ):
            return dict(cls._cache)

        if not force_refresh and cls._docker_probe_time > 0 and (now - cls._docker_probe_time) < cls._cache_ttl_seconds:
            docker_cli = cls._docker_cli
            docker_running = cls._docker_running
        else:
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

        can_execute = True
        reason_code = "OK"

        if not docker_running and fail_closed_required:
            preferred_mode = "blocked"
            can_execute = False
            reason_code = "RUNTIME_UNAVAILABLE"
            message = "EXECUTION BLOCKED: Strict container sandbox required by policy, but Docker is offline."
        elif docker_running:
            preferred_mode = "docker"
            reason_code = "NONE"
            message = "Docker container sandbox active."
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
            "message": message
        }
        cls._cache = result
        cls._cache_time = now
        return dict(result)

sandbox_detector = SandboxDetector()
