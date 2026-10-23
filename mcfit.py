"""Host-independent entry point; the portable skill remains self-contained."""
from pathlib import Path
import runpy
import sys


def main():
    scripts = Path(__file__).resolve().parent / ".agents" / "skills" / "mcfit" / "scripts"
    sys.path.insert(0, str(scripts))
    runpy.run_path(str(scripts / "cli.py"), run_name="__main__")


if __name__ == "__main__":
    main()
