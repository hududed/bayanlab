"""
pytest configuration for BayanLab tests
"""
import sys
from pathlib import Path

# Add backend directory to path so imports work
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))
