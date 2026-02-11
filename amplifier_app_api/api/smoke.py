"""Smoke test endpoint - run automated tests via API."""

import asyncio
import json
import logging
import subprocess
import sys
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/smoke-tests", tags=["testing"])


# Import app for quick tests
def _get_app():
    """Lazy import app to avoid circular dependency."""
    from ..main import app

    return app


@router.get("")
async def run_smoke_tests(
    verbose: bool = Query(default=False, description="Show verbose test output"),
    pattern: str = Query(default="test_smoke.py", description="Test file pattern to run"),
) -> dict[str, Any]:
    """Run smoke tests and return results.

    This endpoint executes pytest on the smoke test suite and returns results
    in JSON format. Useful for automated health checks and CI/CD pipelines.

    Args:
        verbose: If true, include detailed test output
        pattern: Test file pattern (default: test_smoke.py)

    Returns:
        JSON with test results including pass/fail counts and details
    """
    logger.info(f"Running smoke tests with pattern: {pattern}")

    try:
        # Build pytest command
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            f"tests/{pattern}",
            "-v" if verbose else "-q",
            "--tb=short",
            "--json-report",
            "--json-report-file=/tmp/smoke-test-results.json",
        ]

        # Run tests
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout
        )

        # Parse results if json report plugin available
        test_results = {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout if verbose else result.stdout.split("\n")[-5:],
            "stderr": result.stderr if result.stderr else None,
        }

        # Try to load JSON report
        try:
            with open("/tmp/smoke-test-results.json") as f:
                report = json.load(f)
                test_results["summary"] = report.get("summary", {})
                test_results["tests"] = report.get("tests", [])
        except FileNotFoundError:
            # JSON report plugin not installed, parse stdout
            test_results["note"] = (
                "Install pytest-json-report for detailed results: pip install pytest-json-report"
            )

        logger.info(
            f"Smoke tests completed: exit_code={result.returncode}, "
            f"success={result.returncode == 0}"
        )

        return test_results

    except subprocess.TimeoutExpired:
        logger.error("Smoke tests timed out after 60 seconds")
        return {
            "success": False,
            "error": "Tests timed out after 60 seconds",
            "exit_code": -1,
        }
    except Exception as e:
        logger.error(f"Error running smoke tests: {e}")
        return {
            "success": False,
            "error": str(e),
            "exit_code": -1,
        }


@router.get("/quick")
async def run_quick_smoke_tests() -> dict[str, Any]:
    """Run quick smoke tests (basic health checks only).

    This is a lightweight endpoint that runs only the most critical tests
    to verify the service is operational. Completes in <5 seconds.
    """
    logger.info("Running quick smoke tests")

    results = {
        "timestamp": asyncio.get_event_loop().time(),
        "tests": [],
        "passed": 0,
        "failed": 0,
    }

    # Test 1: Health endpoint
    try:
        from httpx import ASGITransport, AsyncClient

        app = _get_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            test_passed = response.status_code == 200
            results["tests"].append(
                {
                    "name": "health_endpoint",
                    "passed": test_passed,
                    "details": response.json() if test_passed else None,
                }
            )
            if test_passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
    except Exception as e:
        results["tests"].append({"name": "health_endpoint", "passed": False, "error": str(e)})
        results["failed"] += 1

    # Test 2: Database connectivity
    try:
        from ..storage import get_db

        db = await get_db()
        all_config = await db.count_configs()
        test_passed = isinstance(all_config, int)
        results["tests"].append({"name": "database_connectivity", "passed": test_passed})
        if test_passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
    except Exception as e:
        results["tests"].append({"name": "database_connectivity", "passed": False, "error": str(e)})
        results["failed"] += 1

    # Test 3: Sessions endpoint
    try:
        app = _get_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sessions")
            test_passed = response.status_code == 200
            results["tests"].append({"name": "sessions_endpoint", "passed": test_passed})
            if test_passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
    except Exception as e:
        results["tests"].append({"name": "sessions_endpoint", "passed": False, "error": str(e)})
        results["failed"] += 1

    # Test 4: Config endpoint
    try:
        app = _get_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/configs")
            test_passed = response.status_code == 200
            results["tests"].append({"name": "config_endpoint", "passed": test_passed})
            if test_passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
    except Exception as e:
        results["tests"].append({"name": "config_endpoint", "passed": False, "error": str(e)})
        results["failed"] += 1

    # Test 5: Applications endpoint (authentication infrastructure)
    try:
        app = _get_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/applications")
            test_passed = response.status_code == 200
            results["tests"].append({"name": "applications_endpoint", "passed": test_passed})
            if test_passed:
                results["passed"] += 1
            else:
                results["failed"] += 1
    except Exception as e:
        results["tests"].append({"name": "applications_endpoint", "passed": False, "error": str(e)})
        results["failed"] += 1

    results["success"] = results["failed"] == 0
    results["total"] = results["passed"] + results["failed"]

    logger.info(f"Quick smoke tests completed: {results['passed']}/{results['total']} passed")

    return results
