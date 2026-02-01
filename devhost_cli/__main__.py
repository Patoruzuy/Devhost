"""Allow running package as: python -m devhost_cli"""

import sys

from .main import main

if __name__ == "__main__":
    sys.exit(main())
