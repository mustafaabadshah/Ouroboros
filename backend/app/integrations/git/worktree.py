import os
import shutil
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
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

        if os.name != "nt" and worktree_path.exists():
            try:
                os.chmod(worktree_path, 0o775)
            except Exception:
                pass

        return worktree_path, candidate_branch, base_commit

    async def create_parallel_subtask_worktrees(
        self,
        repo_path: Path,
        ticket_id: str,
        subtask_keys: List[str]
    ) -> Dict[str, Tuple[Path, str, str]]:
        """
        Dynamic Task Parallelization (DAG Execution):
        Creates independent isolated worktrees for disjoint subtasks in parallel
        (e.g., candidate/{ticket_id}_{subtask_id}).
        Allows concurrent code synthesis in isolated cleanroom branches.
        """
        results = {}
        for key in subtask_keys:
            safe_key = key.replace(":", "-").replace("/", "-").lower()
            sub_ticket_id = f"{ticket_id}_{safe_key}"
            wt_path, branch, base = await self.create_worktree(repo_path, sub_ticket_id)
            results[key] = (wt_path, branch, base)
            logger.info(f"[DAG Parallel Worktree] Created isolated worktree for subtask '{key}': {wt_path}")
        return results

    async def cleanup_parallel_subtask_worktrees(
        self,
        repo_path: Path,
        ticket_id: str,
        subtask_keys: List[str]
    ) -> None:
        """Cleans up temporary parallel subtask worktrees after reconciliation."""
        for key in subtask_keys:
            safe_key = key.replace(":", "-").replace("/", "-").lower()
            sub_ticket_id = f"{ticket_id}_{safe_key}"
            cand_branch = f"candidate/{sub_ticket_id}"
            try:
                await self.remove_worktree(repo_path, sub_ticket_id, cand_branch)
            except Exception as e:
                logger.debug(f"Cleanup subtask worktree notice: {e}")

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

    @staticmethod
    def is_reparse_point_or_link(path: Path) -> bool:
        """
        Exhaustively checks whether path is a symbolic link, NTFS directory junction, or reparse point.
        Uses:
        1. os.path.islink & Path.is_symlink
        2. os.lstat st_reparse_tag check (Python 3.8+ Windows)
        3. Win32 GetFileAttributesW FILE_ATTRIBUTE_REPARSE_POINT (0x0400) via kernel32
        """
        p_str = str(path)
        if os.path.islink(p_str) or path.is_symlink():
            return True
        if os.name == "nt":
            try:
                st = os.lstat(p_str)
                if getattr(st, "st_reparse_tag", 0) != 0:
                    return True
            except Exception:
                pass
            try:
                import ctypes
                attrs = ctypes.windll.kernel32.GetFileAttributesW(p_str)
                if attrs != 0xFFFFFFFF and (attrs & 0x0400):  # FILE_ATTRIBUTE_REPARSE_POINT
                    return True
            except Exception:
                pass
        return False

    def validate_candidate_worktree_path(self, worktree_path: Path) -> Path:
        """
        Validates that worktree_path:
        1. Resolves strictly inside self.worktrees_root and is not the root itself.
        2. Is not a symlink, Windows NTFS directory junction, or reparse point.
        3. Is an authentic linked Git worktree (.git is a file, NOT a directory).
           Crucial guard: Protects primary/main repositories from destructive reset or clean.
        """
        raw_target = Path(worktree_path)
        # Check raw target for reparse point before path resolution
        if self.is_reparse_point_or_link(raw_target):
            raise ValueError(f"Security Violation: Path '{worktree_path}' is an NTFS junction or reparse point.")

        resolved_path = raw_target.resolve()
        resolved_root = self.worktrees_root.resolve()

        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            raise ValueError(
                f"Security Violation: Path '{resolved_path}' is outside designated worktrees root '{resolved_root}'."
            )

        if resolved_path == resolved_root:
            raise ValueError("Security Violation: Cannot operate on the worktrees root directory itself.")

        if self.is_reparse_point_or_link(resolved_path):
            raise ValueError(f"Security Violation: Resolved path '{resolved_path}' is a symlink, junction, or reparse point.")

        git_meta = resolved_path / ".git"
        if git_meta.exists():
            if git_meta.is_dir():
                raise ValueError(
                    f"Security Violation: Target '{resolved_path}' has a .git directory. "
                    "Refusing destructive operation on a primary Git repository!"
                )
            if not git_meta.is_file():
                raise ValueError(f"Security Violation: Target '{resolved_path}' has an invalid .git metadata object.")
        else:
            raise ValueError(f"Security Violation: Target '{resolved_path}' is not a valid Git worktree (missing .git).")

        return resolved_path

    async def reset_worktree_to_base(self, worktree_path: Path, base_commit: str) -> bool:
        """
        Resets the candidate worktree cleanly back to the base commit.
        Used between retry attempts to prevent dirty working trees or conflicts
        from prior flawed patches.
        Enforces strict boundary and identity validation before executing git reset/clean.
        """
        import re
        try:
            # 1. Validate worktree boundary & identity
            safe_worktree = self.validate_candidate_worktree_path(worktree_path)

            # 2. Validate commit hash format to prevent command injection or branch switching
            clean_commit = str(base_commit).strip()
            if not re.match(r"^[0-9a-fA-F]{7,40}$", clean_commit):
                logger.error(f"Security Violation: Refusing reset to invalid commit hash: '{base_commit}'")
                return False

            # 3. Execute bounded reset & clean
            code_reset, _, err_reset = await run_safe_subprocess(
                ["git", "reset", "--hard", clean_commit],
                cwd=safe_worktree
            )
            if code_reset != 0:
                logger.error(f"Git reset failed in worktree {safe_worktree}: {err_reset}")
                return False

            code_clean, _, err_clean = await run_safe_subprocess(
                ["git", "clean", "-fd"],
                cwd=safe_worktree
            )
            if code_clean != 0:
                logger.error(f"Git clean failed in worktree {safe_worktree}: {err_clean}")
                return False

            return True

        except Exception as e:
            logger.error(f"Security validation blocked worktree reset for '{worktree_path}': {e}")
            return False

    async def remove_worktree(self, repo_path: Path, ticket_id: str, candidate_branch: Optional[str] = None):
        """Safely tears down the worktree and prunes git references."""
        safe_ticket_id = ticket_id.replace(":", "-").replace("/", "-")
        worktree_path = (self.worktrees_root / safe_ticket_id).resolve()

        # Only clean up if strictly inside self.worktrees_root
        try:
            worktree_path.relative_to(self.worktrees_root.resolve())
            if worktree_path == self.worktrees_root.resolve():
                return
        except ValueError:
            logger.error(f"Refusing to remove worktree outside root: {worktree_path}")
            return

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

    async def garbage_collect_stale_worktrees(self, repo_path: Optional[Path] = None, max_age_hours: int = 24) -> int:
        """
        Scans self.worktrees_root for stale or orphaned candidate worktrees older than max_age_hours.
        Safely removes them and prunes git references to preserve host disk space.
        """
        import time
        pruned_count = 0
        if not self.worktrees_root.exists():
            return 0

        now = time.time()
        max_age_seconds = max_age_hours * 3600

        for child in list(self.worktrees_root.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                try:
                    mtime = child.stat().st_mtime
                    if (now - mtime) > max_age_seconds:
                        logger.info(f"[Worktree GC] Pruning stale worktree: {child.name} (age: {(now - mtime)/3600:.1f}h)")
                        if repo_path and repo_path.exists():
                            await run_safe_subprocess(["git", "worktree", "remove", "--force", str(child)], cwd=repo_path)
                        shutil.rmtree(child, ignore_errors=True)
                        pruned_count += 1
                except Exception as e:
                    logger.debug(f"[Worktree GC] Could not prune {child.name}: {e}")

        if repo_path and repo_path.exists() and pruned_count > 0:
            await run_safe_subprocess(["git", "worktree", "prune"], cwd=repo_path)

        if pruned_count > 0:
            logger.info(f"[Worktree GC] Cleaned up {pruned_count} stale candidate worktree(s).")
        return pruned_count

git_worktree_manager = GitWorktreeManager()
