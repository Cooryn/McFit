"""Execute the exported skill outside the checkout, without host-specific APIs."""
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run_cli(entry, data, cwd):
    return subprocess.run([sys.executable, str(entry), "smoke"], input=json.dumps(data),
                          capture_output=True, text=True, encoding="utf-8", cwd=cwd)


def test_root_entry_outside_checkout(tmp_path, fixture_data):
    result = run_cli(ROOT / "mcfit.py", fixture_data, tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["recommendations"]


def test_exported_skill_runs_standalone(tmp_path, fixture_data):
    output = tmp_path / "mcfit.zip"
    subprocess.run([sys.executable, str(ROOT / "tools/export_skill.py"), "--output", str(output)], check=True)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert "mcfit/SKILL.md" in names
        assert not any(part in name.split("/") for name in names for part in ("private", ".git", ".venv", "__pycache__"))
        assert not any(name.endswith((".sqlite3", ".env", ".pyc")) for name in names)
        archive.extractall(tmp_path / "another assistant")
    entry = tmp_path / "another assistant/mcfit/scripts/cli.py"
    exported = run_cli(entry, fixture_data, tmp_path)
    original = run_cli(ROOT / "mcfit.py", fixture_data, tmp_path)
    assert exported.returncode == 0, exported.stderr
    assert json.loads(exported.stdout) == json.loads(original.stdout)
    # An existing user artifact must not be silently overwritten.
    before = output.read_bytes()
    again = subprocess.run([sys.executable, str(ROOT / "tools/export_skill.py"), "--output", str(output)], capture_output=True)
    assert again.returncode == 2 and output.read_bytes() == before
