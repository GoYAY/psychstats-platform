"""Regenerate only the five approved samples, never during a normal site build."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site'))
from sitegen.illustrated_examples import export_samples


def main():
    export_samples()


if __name__ == '__main__':
    main()
