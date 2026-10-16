import pytest
import sys
from pathlib import Path
from app.evaluation.real_repo_pilot import RealRepoEvaluator, REAL_REPO_FIXTURES
from app.schemas.eval_contract import EvaluationOutcome

@pytest.mark.asyncio
async def test_real_repo_fixtures_preflight_and_evaluation():
    # Test fixture REAL-REPO-01 (fastapi_jwt_auth)
    fix_01 = next(f for f in REAL_REPO_FIXTURES if f["fixture_id"] == "REAL-REPO-01")
    result = await RealRepoEvaluator.evaluate_fixture(fix_01, force_mock=True)

    assert result["fixture_id"] == "REAL-REPO-01"
    assert result["outcome"] == EvaluationOutcome.PASS, f"REAL-REPO-01 failed: {result.get('error_detail')} | Diff: {result.get('patch_diff')}"
    assert result["verdict"] == "PASS"
    assert result["tests_passed"] >= 2
    assert result["tests_failed"] == 0

@pytest.mark.asyncio
async def test_real_repo_lru_cache_fixture():
    # Test fixture REAL-REPO-03 (lru_ttl_cache)
    fix_03 = next(f for f in REAL_REPO_FIXTURES if f["fixture_id"] == "REAL-REPO-03")
    result = await RealRepoEvaluator.evaluate_fixture(fix_03, force_mock=True)

    assert result["fixture_id"] == "REAL-REPO-03"
    assert result["outcome"] == EvaluationOutcome.PASS
    assert result["verdict"] == "PASS"

@pytest.mark.asyncio
async def test_real_repo_dry_run():
    fix_01 = next(f for f in REAL_REPO_FIXTURES if f["fixture_id"] == "REAL-REPO-01")
    result = await RealRepoEvaluator.evaluate_fixture(fix_01, dry_run=True)
    assert result["verdict"] == "SKIPPED"
    assert result["outcome"] == EvaluationOutcome.CANCELLED
