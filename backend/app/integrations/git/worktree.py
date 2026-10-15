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

    @staticmethod
    def _sanitize_patch(patch_text: str) -> str:
        """
        Sanitizes raw LLM diff text:
        1. Strips non-diff leading/trailing text.
        2. Normalizes line endings to \n.
        3. Drops trailing truncated/incomplete hunks (e.g. hunk ending mid-line without additions).
        """
        if not patch_text or not patch_text.strip():
            return ""

        clean = patch_text.replace("\r\n", "\n").strip()
        lines = clean.split("\n")

        # Extract only from first '--- a/' or '--- ' line
        start_idx = 0
        for i, l in enumerate(lines):
            if l.startswith("--- "):
                start_idx = i
                break
        lines = lines[start_idx:]

        # Drop trailing lines that are obviously truncated/incomplete
        while lines:
            last = lines[-1]
            if not last.strip():
                lines.pop()
                continue
            if last.startswith("@@") or (not last.startswith(" ") and not last.startswith("+") and not last.startswith("-")):
                lines.pop()
            else:
                break

        # Check last hunk: ensure it has at least one addition or deletion, otherwise pop trailing hunk lines
        hunk_indices = [i for i, l in enumerate(lines) if l.startswith("@@")]
        if hunk_indices:
            last_hunk_start = hunk_indices[-1]
            last_hunk_lines = lines[last_hunk_start:]
            has_changes = any(l.startswith("+") or l.startswith("-") for l in last_hunk_lines[1:])
            if not has_changes:
                lines = lines[:last_hunk_start]

        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _apply_hunks_directly(worktree_path: Path, patch_text: str) -> Tuple[bool, str]:
        """
        Resilient direct Python hunk application fallback.
        Parses target file and unified diff blocks, replacing context/deletions with additions.
        """
        try:
            import re
            lines = patch_text.splitlines()
            target_file_rel = None
            for l in lines:
                if l.startswith("+++ b/"):
                    target_file_rel = l[6:].strip()
                    break
                elif l.startswith("+++ "):
                    target_file_rel = l[4:].strip()
                    break

            if not target_file_rel:
                return False, "Could not determine target file from diff headers"

            try:
                full_target_path = validate_safe_path(worktree_path, target_file_rel)
            except ValueError as ve:
                return False, f"Security Violation in target path '{target_file_rel}': {ve}"

            if not full_target_path.exists():
                return False, f"Target file does not exist: {target_file_rel}"

            with open(full_target_path, "r", encoding="utf-8", errors="replace") as f:
                original_content = f.read()

            hunk_blocks = re.split(r"(^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@.*$)", patch_text, flags=re.MULTILINE)
            modified_content = original_content
            applied_count = 0

            for i in range(1, len(hunk_blocks), 2):
                hunk_body = hunk_blocks[i + 1] if i + 1 < len(hunk_blocks) else ""
                hunk_lines = [l for l in hunk_body.splitlines() if not l.startswith("---") and not l.startswith("+++")]
                old_lines = [l[1:] for l in hunk_lines if l.startswith(" ") or l.startswith("-")]
                new_lines = [l[1:] for l in hunk_lines if l.startswith(" ") or l.startswith("+")]

                old_block = "\n".join(old_lines)
                new_block = "\n".join(new_lines)

                if old_block and old_block in modified_content:
                    modified_content = modified_content.replace(old_block, new_block, 1)
                    applied_count += 1

            if applied_count > 0:
                with open(full_target_path, "w", encoding="utf-8") as f:
                    f.write(modified_content)
                return True, f"Directly applied {applied_count} hunk(s) to {target_file_rel}"

            return False, "Hunks could not find exact matching context in target file"
        except Exception as e:
            return False, f"Direct hunk applier failed: {e}"

    async def apply_patch(self, worktree_path: Path, patch_text: str) -> Tuple[bool, str]:
        """
        Applies a candidate patch into the isolated worktree using git apply with resilient fallbacks.
        """
        worktree_path = Path(worktree_path).resolve()
        patch_file = worktree_path / "_candidate.patch"
        try:
            cleaned_patch = self._sanitize_patch(patch_text)
            with open(patch_file, "wb") as f:
                f.write(cleaned_patch.encode("utf-8"))

            # 1. Try git apply with --recount and whitespace tolerance
            check_code, _, check_err = await run_safe_subprocess(
                ["git", "apply", "--check", "--recount", "--ignore-space-change", "--ignore-whitespace", "--whitespace=nowarn", str(patch_file)],
                cwd=worktree_path
            )
            if check_code == 0:
                apply_code, _, apply_err = await run_safe_subprocess(
                    ["git", "apply", "--recount", "--ignore-space-change", "--ignore-whitespace", "--whitespace=nowarn", str(patch_file)],
                    cwd=worktree_path
                )
                if apply_code == 0:
                    return True, "Patch applied successfully via git apply."

            # 2. Try git apply with 3-way merge fallback
            check_3way, _, _ = await run_safe_subprocess(
                ["git", "apply", "-3", "--recount", "--ignore-whitespace", str(patch_file)],
                cwd=worktree_path
            )
            if check_3way == 0:
                return True, "Patch applied successfully via 3-way git apply."

            # 3. Resilient Python direct hunk applier fallback
            direct_ok, direct_msg = self._apply_hunks_directly(worktree_path, cleaned_patch)
            if direct_ok:
                return True, f"Patch applied via resilient hunk applier ({direct_msg})."

            return False, f"Patch failed dry-run check: {check_err}"

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
            # Abort any in-progress merge conflict to restore repository cleanly
            await run_safe_subprocess(["git", "merge", "--abort"], cwd=repo_path)
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
