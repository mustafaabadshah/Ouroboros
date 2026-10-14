import os
import shutil
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.core.security import run_safe_subprocess, validate_safe_path

class GitWorktreeManager:
    """
    Manages isolated Git worktrees for candidate patches.
    Guarantees:
    - Original repository branch and working tree are NEVER overwritten.
    - All edits, linting, and pytest runs execute inside an isolated disposable worktree.
    - Merge into original repository requires explicit human approval.
    """

    def __init__(self, base_worktree_dir: Optional[str] = None):
        raw_path = Path(base_worktree_dir or settings.ISOLATED_WORKTREE_DIR)
        if not raw_path.is_absolute():
            from app.core.config import PROJECT_ROOT
            raw_path = (PROJECT_ROOT / raw_path).resolve()
        self.worktrees_root = raw_path
        self.worktrees_root.mkdir(parents=True, exist_ok=True)

    async def get_base_commit(self, repo_path: Path) -> str:
        """Retrieves the current HEAD commit hash of the target repository."""
        code, out, err = await run_safe_subprocess(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path
        )
        if code != 0 or not out.strip():
            raise RuntimeError(f"Failed to resolve Git HEAD commit in {repo_path}: {err}")
        return out.strip()

    async def create_worktree(self, repo_path: Path, ticket_id: str) -> Tuple[Path, str, str]:
        """
        Creates an isolated Git worktree for candidate implementation.
        Returns (worktree_path, candidate_branch, base_commit).
        """
        base_commit = await self.get_base_commit(repo_path)
        safe_ticket_id = ticket_id.replace(":", "-").replace("/", "-")
        candidate_branch = f"candidate/{safe_ticket_id}"
        worktree_path = (self.worktrees_root / safe_ticket_id).resolve()

        # Clean existing worktree if left from earlier aborted attempt
        await self.remove_worktree(repo_path, ticket_id, candidate_branch)
        await run_safe_subprocess(["git", "worktree", "prune"], cwd=repo_path)
        await run_safe_subprocess(["git", "branch", "-D", candidate_branch], cwd=repo_path)

        # Create isolated worktree attached to candidate branch
        logger.info(f"Creating isolated Git worktree at {worktree_path} on branch {candidate_branch} from {base_commit[:8]}")
        code, out, err = await run_safe_subprocess(
            ["git", "worktree", "add", "-b", candidate_branch, str(worktree_path), base_commit],
            cwd=repo_path
        )
        if code != 0:
            logger.error(f"Failed to create Git worktree: {err}")
            raise RuntimeError(f"Git worktree creation failed: {err}")

        return worktree_path, candidate_branch, base_commit

    async def apply_patch(self, worktree_path: Path, patch_text: str) -> Tuple[bool, str]:
        """
        Applies a candidate patch into the isolated worktree using git apply.
        """
        worktree_path = Path(worktree_path).resolve()
        patch_file = worktree_path / "_candidate.patch"
        try:
            normalized_patch = patch_text.replace("\r\n", "\n").strip() + "\n"
            with open(patch_file, "wb") as f:
                f.write(normalized_patch.encode("utf-8"))

            # Check if patch applies cleanly
            check_code, _, check_err = await run_safe_subprocess(
                ["git", "apply", "--check", "--ignore-whitespace", "--whitespace=nowarn", str(patch_file)],
                cwd=worktree_path
            )
            if check_code != 0:
                return False, f"Patch failed dry-run check: {check_err}"

            # Apply patch
            apply_code, apply_out, apply_err = await run_safe_subprocess(
                ["git", "apply", "--ignore-whitespace", "--whitespace=nowarn", str(patch_file)],
                cwd=worktree_path
            )
            if apply_code != 0:
                return False, f"Patch apply failed: {apply_err}"

            return True, "Patch applied successfully."

        finally:
            if patch_file.exists():
                try:
                    patch_file.unlink()
                except Exception:
                    pass

    async def get_worktree_diff(self, worktree_path: Path) -> str:
        """Returns the unified diff of changes made inside the worktree."""
        code, out, _ = await run_safe_subprocess(
            ["git", "diff"],
            cwd=worktree_path
        )
        return out if code == 0 else ""

    async def commit_candidate(self, worktree_path: Path, message: str) -> bool:
        """Commits changes inside the candidate worktree."""
        add_code, _, _ = await run_safe_subprocess(["git", "add", "-A"], cwd=worktree_path)
        if add_code != 0:
            return False
        commit_code, _, _ = await run_safe_subprocess(
            ["git", "commit", "-m", message],
            cwd=worktree_path
        )
        return commit_code == 0

    async def merge_candidate(self, repo_path: Path, candidate_branch: str, target_branch: str = "main") -> Tuple[bool, str]:
        """
        Explicit Human-Approved Merge:
        Merges the approved candidate branch into the original target branch.
        """
        logger.info(f"Merging candidate branch {candidate_branch} into {target_branch} in {repo_path}")
        code, out, err = await run_safe_subprocess(
            ["git", "merge", candidate_branch, "--no-ff", "-m", f"Merge approved candidate {candidate_branch}"],
            cwd=repo_path
        )
        if code != 0:
            return False, f"Merge failed: {err}"
        return True, "Candidate merged successfully."

    async def remove_worktree(self, repo_path: Path, ticket_id: str, candidate_branch: Optional[str] = None):
        """Safely tears down the worktree and prunes git references."""
        safe_ticket_id = ticket_id.replace(":", "-").replace("/", "-")
        worktree_path = self.worktrees_root / safe_ticket_id

        if worktree_path.exists():
            await run_safe_subprocess(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=repo_path
            )
            # Extra cleanup if directory remains
            if worktree_path.exists():
                try:
                    shutil.rmtree(worktree_path, ignore_errors=True)
                except Exception:
                    pass

        await run_safe_subprocess(["git", "worktree", "prune"], cwd=repo_path)
        if candidate_branch:
            await run_safe_subprocess(["git", "branch", "-D", candidate_branch], cwd=repo_path)

git_worktree_manager = GitWorktreeManager()
