"""Export an auditable, self-contained skill without local data or credentials."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".agents" / "skills" / "mcfit"
# Explicit manifest prevents caches, private files or credentials entering releases.
MANIFEST = (
    "SKILL.md",
    "references/contracts.md", "references/mcp-integration.md",
    "references/nutrition-method.md", "references/output-examples.md",
    "references/workflows.md", "references/host-compatibility.md",
    "scripts/cli.py", "scripts/language.py", "scripts/mcp_policy.py",
    "scripts/models.py", "scripts/normalize.py", "scripts/nutrition.py",
    "scripts/optimizer.py", "scripts/orders.py", "scripts/reporting.py",
    "scripts/storage.py",
)


def export(destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("输出文件已存在，请选择新路径")
    sources = []
    for name in MANIFEST:
        path = SOURCE / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(SOURCE.resolve()):
            raise ValueError(f"技能文件缺失或不是普通内部文件：{name}")
        sources.append((name, path.read_bytes()))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sources:
            entry = zipfile.ZipInfo(f"mcfit/{name}", date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
    return destination


def main():
    parser = argparse.ArgumentParser(description="Export the portable McFit skill")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "mcfit-skill.zip")
    args = parser.parse_args()
    try:
        print(export(args.output))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Export failed: {exc}\n")


if __name__ == "__main__":
    main()
