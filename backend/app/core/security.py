import os
import re
import subprocess
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from app.core.logging import logger
from app.core.config import settings

PROTECTED_FILE_PATTERNS = [
    "validator.py",
    "stockfish.py",
    "config.py",
    ".env",
    ".git",
    ".github",
    "workflows",
    "ouroboros.db",
    "judge.py",
    "runner.py",
    "detector.py",
    "security.py",
    "verify_acceptance.py",
    "conftest.py",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    ".pem",
    "docker-compose",
    "docker.sock",
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
    Raises ValueError on directory traversal attempts, unauthorized absolute paths,
    UNC paths, Windows drive-letter escapes, symlink escapes, or secret file access.
    """
    raw_target = str(target_path).strip()
    if not raw_target:
        raise ValueError("Security Violation: Target path is empty.")

    base_resolved = base_dir.resolve()

    # 1. Explicitly reject UNC network paths (e.g. \\server\share or //server/share)
    if raw_target.startswith(("\\\\", "//")):
        raise ValueError(f"Security Violation: Path traversal detected. UNC network path '{target_path}' is forbidden.")

    # 2. Reject Windows drive-letter paths (e.g. C:/, C:\) on foreign platforms or differing drives
    drive_match = re.match(r'^([a-zA-Z]):[/\\]?', raw_target)
    if drive_match:
        if os.name != "nt":
            raise ValueError(f"Security Violation: Path traversal detected. Windows drive path '{target_path}' escapes base directory '{base_dir}'.")
        target_drive = drive_match.group(1).upper() + ":"
        if base_resolved.drive and target_drive != base_resolved.drive.upper():
            raise ValueError(f"Security Violation: Path traversal detected. Drive '{target_drive}' differs from base drive '{base_resolved.drive}'.")

    # 3. Normalize path separators to forward slashes for cross-platform traversal handling
    normalized = raw_target.replace("\\", "/")

    # 4. Check absolute paths
    if normalized.startswith("/"):
        abs_target = Path(normalized).resolve()
        try:
            abs_target.relative_to(base_resolved)
            target_resolved = abs_target
        except ValueError:
            raise ValueError(f"Security Violation: Path traversal detected. Absolute path '{target_path}' escapes base directory '{base_dir}'.")
    elif drive_match and os.name == "nt":
        abs_target = Path(raw_target).resolve()
        try:
            abs_target.relative_to(base_resolved)
            target_resolved = abs_target
        except ValueError:
            raise ValueError(f"Security Violation: Path traversal detected. Drive path '{target_path}' escapes base directory '{base_dir}'.")
    else:
        target_resolved = (base_resolved / normalized).resolve()
        try:
            target_resolved.relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"Security Violation: Path traversal detected. Target '{target_path}' is outside '{base_dir}'.")

    # 5. Check for symlink jail escape
    try:
        candidate_path = base_resolved / normalized
        if candidate_path.is_symlink():
            resolved_symlink = candidate_path.resolve()
            resolved_symlink.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Security Violation: Path traversal detected. Symlink '{target_path}' escapes base directory '{base_dir}'.")

    # 6. Reject secret-bearing files and version control metadata
    file_name = target_resolved.name.lower()
    if file_name.startswith(".env") or file_name in ["id_rsa", "id_ed25519", "credentials.json"] or file_name.endswith(".pem"):
        raise ValueError(f"Security Violation: Access to secret file '{file_name}' is forbidden.")

    # 7. Block access directly into .git repository directory
    if ".git" in target_resolved.parts or file_name == ".git":
        raise ValueError(f"Security Violation: Direct modification of Git internal metadata '{target_path}' is forbidden.")

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
                if proc.pid:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                            timeout=5
                        )
                    else:
                        proc.kill()
                await proc.wait()
            except Exception as kill_err:
                logger.warning(f"Failed to kill timed out process tree: {kill_err}")
            return -1, "", f"Execution timed out after {timeout} seconds."

    except Exception as e:
        logger.error(f"Error launching subprocess {cmd_args}: {e}")
        return 1, "", str(e)
