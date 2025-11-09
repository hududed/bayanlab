#!/usr/bin/env python3
"""
Pipeline runner entry point
Run from repository root
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# Now import and run
from backend.services.pipeline_runner import main

if __name__ == "__main__":
    main()
