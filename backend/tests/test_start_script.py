import os
import shutil
import subprocess
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")


def _run_start(tmp_path: Path, **env: str) -> list[str]:
    """Run start.sh with stub alembic/python/uvicorn commands and return the calls it made, in order."""
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "calls.log"
    for name in ("alembic", "python", "uvicorn"):
        stub = stubs / name
        stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "$STUB_LOG"\n', newline="\n")
        stub.chmod(0o755)

    base = {key: value for key, value in os.environ.items() if key not in {"PORT", "SEED_ON_START", "RUN_MIGRATIONS_ON_START"}}
    result = subprocess.run(
        ["sh", "start.sh"],
        cwd=BACKEND_DIR,
        env={**base, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": log.as_posix(), **env},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return log.read_text().splitlines()


def test_by_default_it_migrates_seeds_then_serves_on_port_8000(tmp_path: Path):
    assert _run_start(tmp_path) == [
        "alembic upgrade head",
        "python -m app.seeds.seed",
        "uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers",
    ]


def test_it_listens_on_the_port_the_host_provides(tmp_path: Path):
    assert _run_start(tmp_path, PORT="9123")[-1].endswith("--port 9123 --no-proxy-headers")


def test_migrations_can_be_left_to_a_separate_pre_deploy_step(tmp_path: Path):
    calls = _run_start(tmp_path, RUN_MIGRATIONS_ON_START="false")

    assert not any(call.startswith("alembic") for call in calls)
    assert calls[0] == "python -m app.seeds.seed"


def test_seeding_can_be_switched_off(tmp_path: Path):
    calls = _run_start(tmp_path, SEED_ON_START="false")

    assert calls == [
        "alembic upgrade head",
        "uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers",
    ]


def test_uvicorn_never_trusts_forwarded_headers_by_itself(tmp_path: Path):
    uvicorn_call = _run_start(tmp_path)[-1]

    assert "--no-proxy-headers" in uvicorn_call
    assert "forwarded-allow-ips" not in uvicorn_call
