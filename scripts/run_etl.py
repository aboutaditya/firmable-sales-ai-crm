#!/usr/bin/env python3
"""Compatibility wrapper; prefer `sales-intelligence etl ...`."""

import sys

from sales_intelligence.backend.commands import main


if __name__ == "__main__":
    sys.argv[1:1] = ["etl"]
    main()
