"""
Tests for GitWorktreeManager Isolation and Reset Security Guards.
Ensures destructive operations (git reset, git clean, git worktree remove)
can NEVER escape designated candidate worktrees or target primary repositories.
"""

import pytest
import tempfile
import asyncio
from pathlib import Path
from app.integrations.git.worktree import GitWorktreeManager
from app.core.security import run_safe_subprocess


@pytest.fixture
def temp_worktree_env():
    """Sets up a sandboxed temporary git repository and dedicated worktrees root."""
    with tempfile.TemporaryDirectory(prefix="test_wt_env_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        repo_path = tmp_path / "primary_repo"
        worktrees_root = tmp_path / "worktrees"
        repo_path.mkdir()
        worktrees_root.mkdir()

        # Initialize primary repository
        asyncio.run(run_safe_subprocess(["git", "init"], cwd=repo_path))
        asyncio.run(run_safe_subprocess(["git", "config", "user.name", "Test Ouroboros"], cwd=repo_path))
        asyncio.run(run_safe_subprocess(["git", "config", "user.email", "test@ouroboros.local"], cwd=repo_path))

        seed_file = repo_path / "README.md"
        seed_file.write_text("# Test Repo\n", encoding="utf-8")
        asyncio.run(run_safe_subprocess(["git", "add", "README.md"], cwd=repo_path))
        asyncio.run(run_safe_subprocess(["git", "commit", "-m", "Initial commit"], cwd=repo_path))
        asyncio.run(run_safe_subprocess(["git", "branch", "-M", "main"], cwd=repo_path))

        code, out, _ = asyncio.run(run_safe_subprocess(["git", "rev-parse", "HEAD"], cwd=repo_path))
        base_commit = out.strip()

        manager = GitWorktreeManager(base_worktree_dir=str(worktrees_root))
        yield {
            "root": tmp_path,
            "repo_path": repo_path,
            "worktrees_root": worktrees_root,
            "base_commit": base_commit,
            "manager": manager
        }


@pytest.mark.asyncio
async def test_reset_blocks_path_outside_worktrees_root(temp_worktree_env):
    """Rejects paths outside the designated disposable worktrees root."""
    manager = temp_worktree_env["manager"]
    base_commit = temp_worktree_env["base_commit"]
    foreign_path = temp_worktree_env["root"] / "foreign_dir"
    foreign_path.mkdir()

    res = await manager.reset_worktree_to_base(foreign_path, base_commit)
    assert res is False


@pytest.mark.asyncio
async def test_reset_blocks_worktrees_root_itself(temp_worktree_env):
    """Refuses to execute reset on the worktrees root directory itself."""
    manager = temp_worktree_env["manager"]
    base_commit = temp_worktree_env["base_commit"]
    root_path = temp_worktree_env["worktrees_root"]

    res = await manager.reset_worktree_to_base(root_path, base_commit)
    assert res is False


@pytest.mark.asyncio
async def test_reset_blocks_primary_repository(temp_worktree_env):
    """
    CRITICAL SECURITY GUARD: Refuses destructive reset on a primary Git repository
    (.git is a directory), even if mistakenly placed inside or near the worktrees root.
    """
    repo_path = temp_worktree_env["repo_path"]
    base_commit = temp_worktree_env["base_commit"]
    manager = temp_worktree_env["manager"]

    # Even if someone constructs a manager pointing to the repo's parent
    parent_manager = GitWorktreeManager(base_worktree_dir=str(repo_path.parent))
    res = await parent_manager.reset_worktree_to_base(repo_path, base_commit)
    assert res is False


@pytest.mark.asyncio
async def test_reset_blocks_missing_or_invalid_git_metadata(temp_worktree_env):
    """Refuses reset on an ordinary directory that lacks .git worktree metadata."""
    manager = temp_worktree_env["manager"]
    base_commit = temp_worktree_env["base_commit"]
    dummy_dir = temp_worktree_env["worktrees_root"] / "fake_ticket"
    dummy_dir.mkdir()

    res = await manager.reset_worktree_to_base(dummy_dir, base_commit)
    assert res is False


@pytest.mark.asyncio
async def test_reset_blocks_malformed_base_commit(temp_worktree_env):
    """Rejects command injection attempts or branch names in base_commit."""
    manager = temp_worktree_env["manager"]
    repo_path = temp_worktree_env["repo_path"]

    wt_path, _, _ = await manager.create_worktree(repo_path, "OURO-TEST-01")
    assert wt_path.exists()

    # Attempt with invalid commit strings
    for bad_commit in ["main", "HEAD~1", "; rm -rf /", "invalid_commit_name!", "../"]:
        res = await manager.reset_worktree_to_base(wt_path, bad_commit)
        assert res is False, f"Failed to reject malicious commit: {bad_commit}"


@pytest.mark.asyncio
async def test_reset_cleans_dirty_candidate_worktree(temp_worktree_env):
    """Validates that a legitimate linked worktree is cleanly reset to base commit."""
    manager = temp_worktree_env["manager"]
    repo_path = temp_worktree_env["repo_path"]
    base_commit = temp_worktree_env["base_commit"]

    wt_path, _, _ = await manager.create_worktree(repo_path, "OURO-TEST-02")
    assert wt_path.exists()
    assert (wt_path / ".git").is_file()  # Linked worktree must have a .git file

    # Dirty the worktree with an uncommitted file and an edit
    dirty_file = wt_path / "dirty.txt"
    dirty_file.write_text("untracked debris\n", encoding="utf-8")
    readme = wt_path / "README.md"
    readme.write_text("Modified content\n", encoding="utf-8")

    # Perform legitimate secure reset
    success = await manager.reset_worktree_to_base(wt_path, base_commit)
    assert success is True

    # Verify untracked debris is gone and modified content is reverted
    assert not dirty_file.exists()
    assert readme.read_text(encoding="utf-8") == "# Test Repo\n"


@pytest.mark.asyncio
async def test_remove_worktree_outside_root_is_blocked(temp_worktree_env):
    """Refuses to delete paths outside the worktrees root."""
    manager = temp_worktree_env["manager"]
    foreign_dir = temp_worktree_env["root"] / "do_not_delete"
    foreign_dir.mkdir()
    (foreign_dir / "precious.txt").write_text("save me\n", encoding="utf-8")

    # Attempt removal with path traversal ticket ID
    await manager.remove_worktree(
        repo_path=temp_worktree_env["repo_path"],
        ticket_id="../do_not_delete"
    )

    # Must remain intact
    assert foreign_dir.exists()
    assert (foreign_dir / "precious.txt").exists()


@pytest.mark.asyncio
async def test_reset_blocks_windows_ntfs_junction(temp_worktree_env):
    """
    CRITICAL WINDOWS GUARD:
    Verifies that an NTFS directory junction inside the worktrees root pointing
    to a foreign target outside the root is caught and blocked from reset.
    """
    import os, subprocess
    manager = temp_worktree_env["manager"]
    base_commit = temp_worktree_env["base_commit"]
    worktrees_root = temp_worktree_env["worktrees_root"]
    foreign_dir = temp_worktree_env["root"] / "foreign_victim_dir"
    foreign_dir.mkdir()
    (foreign_dir / "critical.txt").write_text("must never be wiped\n", encoding="utf-8")

    junction_path = worktrees_root / "junction_escape"

    if os.name == "nt":
        # Create genuine Windows NTFS directory junction
        cmd_res = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction_path), str(foreign_dir)],
            capture_output=True,
            text=True
        )
        if cmd_res.returncode == 0:
            assert junction_path.exists()
            # Attempt reset on junction
            res = await manager.reset_worktree_to_base(junction_path, base_commit)
            assert res is False
            # Ensure foreign victim remains untouched
            assert (foreign_dir / "critical.txt").exists()
            assert (foreign_dir / "critical.txt").read_text(encoding="utf-8") == "must never be wiped\n"
            # Cleanup junction safely
            subprocess.run(["cmd", "/c", "rmdir", str(junction_path)], capture_output=True)
    else:
        # On POSIX, test symlink
        junction_path.symlink_to(foreign_dir, target_is_directory=True)
        res = await manager.reset_worktree_to_base(junction_path, base_commit)
        assert res is False
        assert (foreign_dir / "critical.txt").exists()

