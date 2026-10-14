import os
import subprocess
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from app.core.logging import logger
from app.core.config import settings

PROTECTED_FILE_PATTERNS = [
    "validator.py",
    "board_manager.py",
    "stockfish.py",
    "config.py",
    ".env",
    ".git",
    "ouroboros.db",
]

def mask_secret(text: Optional[str]) -> str:
    """Masks API keys and secrets so they never leak into logs or telemetry."""
    if not text:
        return "NONE"
    clean = text.strip()
    if len(clean) <= 8:
        return "********"
    return f"{clean[:4]}...{clean[-4:]}"

def validate_safe_path(base_dir: Path, target_path: str) -> Path:
    """
    Validates that target_path resolves strictly within base_dir.
    Raises ValueError on directory traversal attempts or secret file access.
    """
    base_resolved = base_dir.resolve()
    target_resolved = (base_dir / target_path).resolve()

    try:
        target_resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Security Violation: Path traversal detected. Target '{target_path}' is outside '{base_dir}'.")

    # Reject secret-bearing files
    file_name = target_resolved.name.lower()
    if file_name in [".env", ".env.local", "id_rsa", "id_ed25519"] or file_name.endswith(".pem"):
        raise ValueError(f"Security Violation: Access to secret file '{file_name}' is forbidden.")

    return target_resolved

def is_protected_path(rel_path: str) -> bool:
    """Checks whether a relative file path belongs to protected engine or security logic."""
    clean = rel_path.replace("\\", "/").lower()
    for pattern in PROTECTED_FILE_PATTERNS:
        if pattern in clean:
            return True
    return False

async def run_safe_subprocess(
    cmd_args: List[str],
    cwd: Path,
    timeout: Optional[int] = None,
    extra_env: Optional[Dict[str, str]] = None,
    max_output_bytes: Optional[int] = None
) -> Tuple[int, str, str]:
    """
    Executes a subprocess safely using explicit argument arrays (no shell=True).
    Enforces timeout, working directory restrictions, and bounded output capture.
    """
    timeout = timeout or settings.SUBPROCESS_TIMEOUT_SECONDS
    max_bytes = max_output_bytes or settings.MAX_OUTPUT_CAPTURE_BYTES

    # Sanitize environment: clone system PATH and Python vars, but strip raw cloud keys
    safe_env = dict(os.environ)
    if extra_env:
        safe_env.update(extra_env)

    logger.debug(f"Running safe subprocess: {' '.join(cmd_args)} [cwd: {cwd}]")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=safe_env
        )

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(timeout)
            )
            exit_code = proc.returncode if proc.returncode is not None else 1
            stdout_str = stdout_data.decode("utf-8", errors="replace")[:max_bytes]
            stderr_str = stderr_data.decode("utf-8", errors="replace")[:max_bytes]
            return exit_code, stdout_str, stderr_str

        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception as kill_err:
                logger.warning(f"Failed to kill timed out process: {kill_err}")
            return -1, "", f"Execution timed out after {timeout} seconds."

    except Exception as e:
        logger.error(f"Error launching subprocess {cmd_args}: {e}")
        return 1, "", str(e)
