"""Check that the API works when only the deployment modules are present.

Copies the modules listed in MODULES into an empty temporary folder, starts a
clean Python process (isolated mode: no tests, no pytest, no AWS configuration),
imports capture_lambda and calls lambda_handler for /health and /ready.
It never contacts AWS and needs no credentials.

This does NOT prove that the package works on the real Lambda runtime.

Run from backend/api (virtual environment active):

    python scripts/check_package.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent

# The modules that must sit at the root of the deployment package.
# handler.py belongs to the technical lead and is not part of this list.
MODULES = (
    "capture_lambda",
    "capture_service",
    "config",
    "dynamodb_repository",
    "errors",
    "http_api",
    "inline_route_store",
    "models",
    "ports",
    "request_validation",
    "sqs_queue",
)

CONFIG_VARIABLES = ("CAPTURE_QUEUE_URL", "CAPTURES_TABLE_NAME")

CHILD_CODE = """
import json
import os
import sys

package_dir = os.path.abspath(sys.argv[1])
sys.path.insert(0, package_dir)

import capture_lambda
from http_api import HEALTH_PATH


def event(path):
    return {
        "rawPath": path,
        "requestContext": {"requestId": "check", "http": {"method": "GET"}},
    }


health = capture_lambda.lambda_handler(event(HEALTH_PATH), None)
ready = capture_lambda.lambda_handler(event(capture_lambda.READY_PATH), None)
loaded = sorted(
    name
    for name, module in sys.modules.items()
    if getattr(module, "__file__", None)
    and os.path.dirname(os.path.abspath(module.__file__)) == package_dir
)
print(
    json.dumps(
        {
            "health": health["statusCode"],
            "ready": ready["statusCode"],
            "loaded": loaded,
            "tests_imported": "tests" in sys.modules,
            "pytest_imported": "pytest" in sys.modules,
        }
    )
)
"""


def main() -> int:
    missing = [name for name in MODULES if not (API_DIR / f"{name}.py").is_file()]
    if missing:
        print("FAIL: missing module files:", ", ".join(missing))
        return 1

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        package_dir = Path(folder) / "package"
        package_dir.mkdir()
        for name in MODULES:
            shutil.copy2(API_DIR / f"{name}.py", package_dir / f"{name}.py")

        # No AWS configuration: /health must still work, /ready must say 503.
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in CONFIG_VARIABLES
        }
        completed = subprocess.run(
            [sys.executable, "-I", "-B", "-c", CHILD_CODE, str(package_dir)],
            capture_output=True,
            text=True,
            env=environment,
            cwd=folder,
            timeout=60,
            check=False,
        )
        if completed.returncode != 0:
            print("FAIL: the clean process could not import or run the package.")
            print(completed.stderr.strip()[-2000:])
            return 1

        report = json.loads(completed.stdout.strip().splitlines()[-1])

        if report["health"] != 200:
            problems.append(f"/health returned {report['health']}, expected 200")
        if report["ready"] != 503:
            problems.append(f"/ready returned {report['ready']}, expected 503")
        if report["tests_imported"] or report["pytest_imported"]:
            problems.append("the package imported tests or pytest")
        not_loaded = sorted(set(MODULES) - set(report["loaded"]))

        archive = Path(folder) / "package.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for name in MODULES:
                bundle.write(package_dir / f"{name}.py", f"{name}.py")
        size = archive.stat().st_size

    print(f"Modules copied:   {len(MODULES)}")
    print(f"Modules imported: {len(report['loaded'])}")
    if not_loaded:
        print("Note: copied but not imported (may be unused):", ", ".join(not_loaded))
    print(f"/health -> {report['health']}   /ready (no config) -> {report['ready']}")
    print(f"Zip of the modules only (without boto3): {size} bytes")

    if problems:
        for problem in problems:
            print("FAIL:", problem)
        return 1
    print("PACKAGE CHECK OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
