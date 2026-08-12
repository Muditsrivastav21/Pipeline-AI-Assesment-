# config.py
"""Central place to read integration settings from the environment.

Secrets (client ids/secrets) must never be committed to the repo, so they are
read from a local `.env` file (see `.env.example`) or the process environment.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load `backend/.env` regardless of the directory uvicorn was started from.
load_dotenv(Path(__file__).resolve().parent / '.env')

BACKEND_BASE_URL = os.environ.get('BACKEND_BASE_URL', 'http://localhost:8000')


def get_env(name: str, default: str | None = None) -> str | None:
    """Return an environment variable, treating blank values as unset."""
    value = os.environ.get(name, default)
    if value is not None:
        value = value.strip()
    return value or default


def require_env(name: str) -> str:
    """Return a required environment variable or fail with a clear message."""
    value = get_env(name)
    if not value:
        raise RuntimeError(
            f'Missing required environment variable: {name}. '
            f'Copy backend/.env.example to backend/.env and fill it in.'
        )
    return value


def redirect_uri(integration: str) -> str:
    """Build the OAuth callback URL registered with the provider."""
    return f'{BACKEND_BASE_URL}/integrations/{integration}/oauth2callback'
