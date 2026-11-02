import io
import json
import os
import subprocess
import sys


def test_cli_doctor_without_secrets():
    result = subprocess.run(
        [sys.executable, "-m", "user_memory", "doctor"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["provider"] == "OpenAI"
    assert isinstance(data["openai_key_present"], bool)
    assert "api_key" not in data


def test_cli_help_has_memory_operations():
    result = subprocess.run(
        [sys.executable, "-m", "user_memory", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    assert all(command in result.stdout for command in ("chat", "profile", "inspect", "search", "procedure"))


def test_oa_01_cli_checks_missing_key_before_database():
    environment = {**os.environ, "OPENAI_API_KEY": "", "DATABASE_URL": "postgresql://localhost:1/memory_demo"}
    result = subprocess.run(
        [sys.executable, "-m", "user_memory", "turn", "Help with my invoice."],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1
    assert "OPENAI_API_KEY" in result.stderr


def test_d3_10_cli_policy_requires_admin_before_connections():
    environment = {**os.environ, "OPENAI_API_KEY": "", "DATABASE_URL": "postgresql://127.0.0.1:1/memory_demo"}
    result = subprocess.run(
        [sys.executable, "-m", "user_memory", "policy", "Pricing answers need a disclaimer."],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1
    assert "PermissionError" in result.stderr


def test_cli_json_round_trips_unicode_on_windows_pipe(monkeypatch):
    from user_memory.cli import print_json

    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stream)
    expected = {"fact": "मुंबई budget ₹20,000", "mem_ix": "fact\u200ckey:id"}
    print_json(expected)
    stream.flush()
    assert json.loads(buffer.getvalue().decode("ascii")) == expected


def test_doctor_finds_per_user_docker_without_refreshed_path(tmp_path, monkeypatch):
    from user_memory.cli import find_docker

    binary = tmp_path / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe"
    binary.parent.mkdir(parents=True)
    binary.touch()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert find_docker() == str(binary)
