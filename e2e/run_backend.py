"""Runs the REAL backend (unmodified main.py / hubspot.py) for E2E testing,
with HubSpot's URLs redirected to the local mock server.

Nothing in backend/ is edited: the redirect happens by overriding the module
constants at import time, after config.py has already read HUBSPOT_CLIENT_ID/
SECRET from the environment we set below. This is test-harness wiring only.
"""
import os
import sys

sys.path.insert(0, r'c:\Users\mudit\Downloads\Pipeline AI Assignment\Pipeline AI Assignment\backend')

os.environ['HUBSPOT_CLIENT_ID'] = 'mock-hubspot-client-id'
os.environ['HUBSPOT_CLIENT_SECRET'] = 'mock-hubspot-client-secret'
os.environ['REDIS_HOST'] = 'localhost'
os.environ['BACKEND_BASE_URL'] = 'http://localhost:8000'
os.environ['FRONTEND_ORIGIN'] = 'http://localhost:3000'

import integrations.hubspot as hubspot  # noqa: E402

hubspot.AUTHORIZATION_URL = 'http://localhost:9500/oauth/authorize'
hubspot.TOKEN_URL = 'http://localhost:9500/oauth/v1/token'
hubspot.TOKEN_INFO_URL = 'http://localhost:9500/oauth/v1/access-tokens'
hubspot.API_BASE_URL = 'http://localhost:9500'
hubspot.CLIENT_ID = os.environ['HUBSPOT_CLIENT_ID']
hubspot.CLIENT_SECRET = os.environ['HUBSPOT_CLIENT_SECRET']

import uvicorn  # noqa: E402
from main import app  # noqa: E402

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000, log_level='info')
