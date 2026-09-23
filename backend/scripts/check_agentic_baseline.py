"""Run characterization with optional runner-owned Redis or PostgreSQL.

No dependency install, source .env, real DB, external provider or production queue.
Invoke with an already prepared Python environment; artifacts live outside checkout.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="Run all offline backend tests")
    mode.add_argument(
        "--database", action="store_true", help="Fresh disposable pgvector + storage checks"
    )
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    if (backend.parent / ".env").exists():
        parser.error("Use a secret-free checkout without a root .env")
    output = Path(tempfile.mkdtemp(prefix="mealy-agentic-characterization-"))
    for name in ("home", "tmp", "hypothesis"):
        (output / name).mkdir()
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(output / "home"),
        "TMPDIR": str(output / "tmp"),
        "PYTHONPATH": str(backend),
        "PYTHONDONTWRITEBYTECODE": "1",
        "DATABASE_URL": "postgresql+asyncpg://synthetic:synthetic@127.0.0.1:1/not_a_real_db",
        "REDIS_URL": "redis://127.0.0.1:1/15",
        "OPENROUTER_API_KEY": "",
        "OPENROUTER_BASE_URL": "http://127.0.0.1:1/blocked",
        "SECRET_KEY": "synthetic-characterization-only",
        "AGENT_TOOL_USE_ENABLED": "false",
        "DEBUG": "false",
        "DEV_MODE": "false",
        "HYPOTHESIS_STORAGE_DIRECTORY": str(output / "hypothesis"),
    }
    container = None
    docker = shutil.which("docker")
    if (args.full or args.database) and docker is None:
        parser.error("Container checks require an existing Docker installation and local images")
    try:
        if args.full:
            name = "mealy-characterization-" + uuid.uuid4().hex[:12]
            subprocess.run(  # noqa: S603 - fixed argv, generated container name, no shell
                [
                    docker,
                    "run",
                    "--pull=never",
                    "--rm",
                    "-d",
                    "--name",
                    name,
                    "-p",
                    "127.0.0.1::6379",
                    "redis:7-alpine",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            container = name
            subprocess.run(  # noqa: S603 - fixed command against own container
                [docker, "exec", name, "redis-cli", "ping"],
                check=True,
                capture_output=True,
                text=True,
            )
            port = (
                subprocess.check_output(  # noqa: S603 - own generated container only
                    [docker, "port", name, "6379/tcp"], text=True
                )
                .strip()
                .rsplit(":", 1)[1]
            )
            environment["REDIS_URL"] = f"redis://127.0.0.1:{port}/15"
            environment["MEALY_DISPOSABLE_REDIS"] = "1"
        if args.database:
            name = "mealy-characterization-pg-" + uuid.uuid4().hex[:12]
            subprocess.run(  # noqa: S603 - own disposable container, fixed image, no volumes
                [
                    docker,
                    "run",
                    "--pull=never",
                    "--rm",
                    "-d",
                    "--name",
                    name,
                    "-p",
                    "127.0.0.1::5432",
                    "-e",
                    "POSTGRES_USER=synthetic",
                    "-e",
                    "POSTGRES_PASSWORD=synthetic",
                    "-e",
                    "POSTGRES_DB=mealy_characterization",
                    "pgvector/pgvector:pg16",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            container = name
            for _ in range(50):
                ready = subprocess.run(  # noqa: S603 - own disposable DB readiness only
                    [
                        docker,
                        "exec",
                        name,
                        "pg_isready",
                        "-U",
                        "synthetic",
                        "-d",
                        "mealy_characterization",
                    ],
                    capture_output=True,
                    check=False,
                )
                if ready.returncode == 0:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError("Disposable PostgreSQL did not become ready")
            port = (
                subprocess.check_output(  # noqa: S603 - own generated container only
                    [docker, "port", name, "5432/tcp"], text=True
                )
                .strip()
                .rsplit(":", 1)[1]
            )
            environment["DATABASE_URL"] = (
                f"postgresql+asyncpg://synthetic:synthetic@127.0.0.1:{port}/mealy_characterization"
            )
            environment["TEST_DATABASE_URL"] = environment["DATABASE_URL"]
            environment["MEALY_DISPOSABLE_DB"] = "1"
            with (output / "alembic-upgrade.log").open("w") as log:
                subprocess.run(
                    [sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
                    cwd=backend,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=60,
                )
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "tests.characterization.network_guard",
            "--hypothesis-seed=20260923",
            "--junitxml=" + str(output / "pytest.xml"),
        ]
        if args.full:
            command += ["-m", "not integration and not live_source"]
        elif args.database:
            command += [
                "tests/integration/test_plan_storage_characterization.py",
                "tests/integration/test_pgvector_search.py",
            ]
        else:
            command += ["tests/agent"]
        with (output / "pytest.log").open("w") as log:
            result = subprocess.run(  # noqa: S603 - fixed pytest argv, current interpreter
                command,
                cwd=backend,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=180,
            )
        record = {
            "argv": command,
            "cwd": str(backend),
            "exit_code": result.returncode,
            "full": args.full,
            "database": args.database,
            "network": "only runner-owned disposable service; other socket connects denied",
            "mock_boundaries": (
                ["cache writes; real PostgreSQL storage"]
                if args.database
                else ["LLM", "retrieval", "persistence in transition tests"]
            ),
            "artifacts": str(output),
        }
        (output / "run.json").write_text(json.dumps(record, indent=2))
        print(json.dumps(record, indent=2))
        print((output / "pytest.log").read_text()[-7000:])
        return result.returncode
    finally:
        if container is not None:
            subprocess.run([docker, "stop", container], check=True, capture_output=True)  # noqa: S603


if __name__ == "__main__":
    raise SystemExit(main())
