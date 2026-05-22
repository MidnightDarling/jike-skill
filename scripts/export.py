#!/usr/bin/env python3
"""Repository wrapper for the package export CLI."""
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

def main() -> None:
    from jike.export import main as run

    run()

if __name__ == "__main__":
    main()
