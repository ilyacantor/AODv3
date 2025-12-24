"""Test execution API routes"""

import subprocess

from fastapi import APIRouter

from ..schemas import (
    RunTestsRequest,
    RunTestsResponse,
)


router = APIRouter(prefix="")


@router.post("/run-tests")
async def run_tests(request: RunTestsRequest) -> RunTestsResponse:
    """
    Run pytest tests and return results.
    """
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", request.test_path, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd="/home/runner/workspace"
        )

        output = result.stdout + result.stderr

        passed_count = 0
        failed_count = 0
        total = 0

        for line in output.split('\n'):
            if ' passed' in line and ('failed' in line or 'passed' in line):
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed':
                        try:
                            passed_count = int(parts[i-1])
                        except:
                            pass
                    if part == 'failed':
                        try:
                            failed_count = int(parts[i-1])
                        except:
                            pass

        total = passed_count + failed_count
        all_passed = failed_count == 0 and passed_count > 0

        summary_lines = [l for l in output.split('\n') if 'passed' in l or 'failed' in l or 'error' in l.lower()]
        summary = '\n'.join(summary_lines[-5:]) if summary_lines else ''

        return RunTestsResponse(
            passed=all_passed,
            total=total,
            passed_count=passed_count,
            failed_count=failed_count,
            summary=summary,
            output=output[-3000:] if len(output) > 3000 else output
        )
    except subprocess.TimeoutExpired:
        return RunTestsResponse(
            passed=False,
            total=0,
            passed_count=0,
            failed_count=0,
            summary="Test run timed out after 120 seconds",
            output="Timeout"
        )
    except Exception as e:
        return RunTestsResponse(
            passed=False,
            total=0,
            passed_count=0,
            failed_count=0,
            summary=str(e),
            output=str(e)
        )
