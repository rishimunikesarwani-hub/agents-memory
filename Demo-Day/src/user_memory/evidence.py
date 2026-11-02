"""Build identity for test evidence. This module contains no credential values."""

import hashlib
import json
from dataclasses import asdict

from .config import PROJECT_ROOT, Settings


def build_fingerprint() -> str:
    digest = hashlib.sha256()
    paths = [PROJECT_ROOT / "pyproject.toml", PROJECT_ROOT / "uv.lock", PROJECT_ROOT / "conftest.py"]
    paths.append(PROJECT_ROOT / "ops" / "test-demo1.ps1")
    paths.extend((PROJECT_ROOT / "ops").glob("*.ps1"))
    paths.extend(
        [
            PROJECT_ROOT / "ops" / "compose.yaml",
            PROJECT_ROOT / "ops" / "init-db.sql",
            PROJECT_ROOT / ".env.example",
        ]
    )
    for directory in ("src", "tests", "evals", "ops"):
        paths.extend((PROJECT_ROOT / directory).rglob("*.py"))
    for path in sorted(set(paths)):
        digest.update(str(path.relative_to(PROJECT_ROOT)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    digest.update(json.dumps(asdict(Settings.from_env()), sort_keys=True).encode())
    return digest.hexdigest()
