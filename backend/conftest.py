"""Ensures `backend/` is on sys.path regardless of the directory pytest is
invoked from, so `from integrations.hubspot import ...` resolves the same way
it does when uvicorn runs main.py from inside backend/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
