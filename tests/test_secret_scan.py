from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "secret_scan.py"


def run_secret_scan(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True,
        check=False,
        text=True,
    )


def test_secret_scan_detects_high_confidence_secret(tmp_path: Path) -> None:
    secret = "AKIA" + "1234567890ABCDEF"
    secret_file = tmp_path / "leak.txt"
    secret_file.write_text(f"AWS_ACCESS_KEY_ID={secret}\n", encoding="utf-8")

    result = run_secret_scan(tmp_path)

    assert result.returncode == 1
    assert "aws-access-key-id" in result.stdout
    assert "AKIA...CDEF" in result.stdout
    assert secret not in result.stdout


def test_secret_scan_allows_documented_placeholders(tmp_path: Path) -> None:
    placeholder = "AKIAIOSFODNN7" + "EXAMPLE"
    example_file = tmp_path / "example.env"
    example_file.write_text(f"AWS_ACCESS_KEY_ID={placeholder}\n", encoding="utf-8")

    result = run_secret_scan(tmp_path)

    assert result.returncode == 0
    assert "Secret scan passed" in result.stdout
