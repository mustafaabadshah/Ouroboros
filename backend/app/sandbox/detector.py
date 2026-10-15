import shutil
import asyncio
from typing import Dict, Any
from app.core.security import run_safe_subprocess
from app.core.logging import logger

class SandboxDetector:
    """
    Detects available sandboxing runtime capabilities on the host system.
    Determines whether Docker is running or if restricted local isolation must be engaged.
    """

    @staticmethod
    async def detect_capabilities() -> Dict[str, Any]:
        docker_cli = shutil.which("docker") or shutil.which("docker.exe")
        docker_running = False

        if docker_cli:
            try:
                code, out, err = await run_safe_subprocess(
                    ["docker", "info"],
                    cwd=Path("."),
                    timeout=3
                )
                if code == 0 and "Server" in out and "ERROR" not in out:
                    docker_running = True
            except Exception:
                docker_running = False

        from app.core.config import settings

        fail_closed_required = settings.REQUIRE_CONTAINER_SANDBOX or settings.SANDBOX_MODE == "fail_closed"
        can_execute = True

        if not docker_running and fail_closed_required:
            preferred_mode = "blocked"
            can_execute = False
            message = "EXECUTION BLOCKED: Strict container sandbox required by policy, but Docker is offline."
        elif docker_running:
            preferred_mode = "docker"
            message = "Docker container sandbox active."
        else:
            preferred_mode = "restricted_local"
            message = "Docker offline. Restricted local subprocess worktree sandbox active."

        return {
            "docker_installed": bool(docker_cli),
            "docker_running": docker_running,
            "preferred_mode": preferred_mode,
            "can_execute": can_execute,
            "fail_closed_required": fail_closed_required,
            "message": message
        }

from pathlib import Path
sandbox_detector = SandboxDetector()
