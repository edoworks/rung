"""Allow running as `python3 -m rung`."""
from rung.cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())