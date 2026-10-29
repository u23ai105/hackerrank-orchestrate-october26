#!/usr/bin/env python3
"""
Main entry point for HackerRank Orchestrate: Ghost Data Still Exists.
Executes the full deletion-audit pipeline on dataset/deletion_requests.csv
and generates the authoritative output.csv at repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from build_output import main

if __name__ == "__main__":
    main()
