#!/usr/bin/env python3
"""
Chaos Tester -- Entry Point

Usage:
    python run.py                       # Start the web dashboard on port 5000
    python run.py --port 8080           # Custom port
    python run.py --host 0.0.0.0       # Listen on all interfaces
"""

import sys
import os

# Ensure the parent directory is on the path so 'chaos_tester' is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chaos_tester.app import main

if __name__ == "__main__":
    main()
