"""One-time interactive Primary Admin bootstrap command."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.cli import bootstrap_primary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    args = parser.parse_args()
    bootstrap_primary(args.email)
