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

        return {
            "docker_installed": bool(docker_cli),
            "docker_running": docker_running,
            "preferred_mode": "docker" if docker_running else "restricted_local",
            "message": "Docker container sandbox active." if docker_running else "Docker offline. Restricted local subprocess worktree sandbox active."
        }

from pathlib import Path
sandbox_detector = SandboxDetector()
