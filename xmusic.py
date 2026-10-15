#!/usr/bin/env python3
"""XMusic launcher:  python xmusic.py [--music-dir DIR] [--theme ID] [--no-animation]   (see --help)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xmusic_core.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
