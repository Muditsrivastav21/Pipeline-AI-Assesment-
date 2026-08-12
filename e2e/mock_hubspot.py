"""A mock HubSpot server used only for local E2E testing.

Implements just enough of HubSpot's real protocol for the app's hubspot.py to
work against it unmodified (its URLs are monkeypatched to point here in
run_backend.py, so the shipped hubspot.py itself needs no test-only branches):

  GET  /oauth/authorize                 -> real consent-style HTML page
  POST /oauth/v1/token                  -> issues fake tokens (validates the
                                            authorization code AND client_secret,
                                            exactly like the real endpoint)
  GET  /oauth/v1/access-tokens/{token}  -> portal (hub) lookup
  GET  /crm/v3/objects/{contacts|companies|deals} -> paginated fake CRM records

This is test-only infrastructure, not part of the submission.
"""
import secrets
import time
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

app = FastAPI()

EXPECTED_CLIENT_ID = 'mock-hubspot-client-id'
EXPECTED_CLIENT_SECRET = 'mock-hubspot-client-secret'

# authorization codes issued by /oauth/authorize, single-use, short-lived
_ISSUED_CODES: dict[str, dict] = {}
# access tokens we've handed out, so /crm and /access-tokens can validate them
_ISSUED_TOKENS: dict[str, dict] = {}

FAKE_HUB_ID = 87654321

CONTACTS = [
    {
        'id': '101',
        'createdAt': '2024-01-05T10:00:00Z',
        'updatedAt': '2024-06-01T11:30:00Z',
        'archived': False,
        'properties': {
            'firstname': 'Ada', 'lastname': 'Lovelace',
            'email': 'ada@example.com', 'phone': '555-0101',
            'jobtitle': 'Analyst', 'company': 'Pipeline AI', 'lifecyclestage': 'lead',
        },
    },
    {
        'id': '102',
        'createdAt': '2024-02-10T09:00:00Z',
        'updatedAt': '2024-06-02T09:00:00Z',
        'archived': False,
        'properties': {
            'firstname': 'Grace', 'lastname': 'Hopper',
            'email': 'grace@example.com', 'phone': '555-0102',
            'jobtitle': 'Engineer', 'company': 'Pipeline AI', 'lifecyclestage': 'customer',
        },
    },
]

COMPANIES = [
    {
        'id': '201',
        'createdAt': '2023-11-01T09:00:00Z',
        'updatedAt': '2024-05-01T09:00:00Z',
        'archived': False,
        'properties': {
            'name': 'Pipeline AI', 'domain': 'addpipeline.ai',
            'industry': 'SOFTWARE', 'city': 'San Francisco', 'country': 'USA',
            'numberofemployees': '25', 'annualrevenue': '1000000',
        },
    },
]

DEALS = [
    {
        'id': '301',
        'createdAt': '2024-04-01T08:00:00Z',
        'updatedAt': '2024-05-01T08:00:00Z',
        'archived': False,
        'properties': {
            'dealname': 'Enterprise Rollout', 'dealstage': 'contractsent',
            'pipeline': 'default', 'amount': '50000', 'closedate': '2024-08-01',
        },
    },
    {
        'id': '302',
        'createdAt': '2024-04-15T08:00:00Z',
        'updatedAt': '2024-05-15T08:00:00Z',
        'archived': False,
        'properties': {
            'dealname': 'Pilot Program', 'dealstage': 'appointmentscheduled',
            'pipeline': 'default', 'amount': '8000', 'closedate': '2024-09-01',
        },
    },
]

OBJECTS = {'contacts': CONTACTS, 'companies': COMPANIES, 'deals': DEALS}


@app.get('/oauth/authorize', response_class=HTMLResponse)
async def authorize(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query(...),
    state: str = Query(...),
):
    """Consent screen. A real human/Playwright clicks 'Approve' to continue."""
    if client_id != EXPECTED_CLIENT_ID:
        return HTMLResponse(f'<h1>Unrecognized client_id: {client_id}</h1>', status_code=400)

    code = secrets.token_urlsafe(16)
    _ISSUED_CODES[code] = {'issued_at': time.time(), 'redirect_uri': redirect_uri}

    approve_qs = urlencode({'redirect_uri': redirect_uri, 'state': state, 'code': code})
    deny_qs = urlencode({'redirect_uri': redirect_uri, 'state': state})

    return HTMLResponse(f"""
    <html>
      <body style="font-family: sans-serif; max-width: 420px; margin: 60px auto;">
        <h2>Mock HubSpot</h2>
        <p><b>Test App</b> is requesting access to:</p>
        <ul>{''.join(f'<li>{s}</li>' for s in scope.split())}</ul>
        <a id="approve" href="/oauth/approve?{approve_qs}">
          <button style="padding:8px 20px;">Approve</button>
        </a>
        <a id="deny" href="/oauth/deny?{deny_qs}">
          <button style="padding:8px 20px;">Deny</button>
        </a>
      </body>
    </html>
    """)


@app.get('/oauth/approve')
async def approve(redirect_uri: str, state: str, code: str):
    return RedirectResponse(f'{redirect_uri}?{urlencode({"code": code, "state": state})}')


@app.get('/oauth/deny')
async def deny(redirect_uri: str, state: str):
    return RedirectResponse(
        f'{redirect_uri}?{urlencode({"error": "access_denied", "error_description": "User denied access"})}'
    )


@app.post('/oauth/v1/token')
async def token(
    grant_type: str = Form(...),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    client_id: str = Form(...),
    client_secret: str = Form(...),
):
    if client_id != EXPECTED_CLIENT_ID or client_secret != EXPECTED_CLIENT_SECRET:
        return JSONResponse({'message': 'invalid client credentials'}, status_code=401)

    if grant_type == 'authorization_code':
        issued = _ISSUED_CODES.pop(code, None) if code else None
        if not issued:
            return JSONResponse({'message': 'invalid or expired code'}, status_code=400)
        if issued['redirect_uri'] != redirect_uri:
            return JSONResponse({'message': 'redirect_uri mismatch'}, status_code=400)
    elif grant_type != 'refresh_token':
        return JSONResponse({'message': f'unsupported grant_type {grant_type}'}, status_code=400)

    access_token = secrets.token_urlsafe(24)
    refresh_token = secrets.token_urlsafe(24)
    _ISSUED_TOKENS[access_token] = {'hub_id': FAKE_HUB_ID}

    return {
        'token_type': 'bearer',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': 1800,
    }


@app.get('/oauth/v1/access-tokens/{access_token}')
async def access_token_info(access_token: str):
    info = _ISSUED_TOKENS.get(access_token)
    if not info:
        return JSONResponse({'message': 'invalid token'}, status_code=404)
    return {'hub_id': info['hub_id'], 'scopes': ['oauth', 'crm.objects.contacts.read']}


def _authed(request: Request) -> bool:
    auth = request.headers.get('authorization', '')
    token_value = auth.removeprefix('Bearer ').strip()
    return token_value in _ISSUED_TOKENS


@app.get('/crm/v3/objects/{object_type}')
async def list_objects(object_type: str, request: Request, limit: int = 100, after: str | None = None):
    if not _authed(request):
        return JSONResponse({'message': 'expired or invalid access token'}, status_code=401)
    if object_type not in OBJECTS:
        return JSONResponse({'message': 'unknown object type'}, status_code=404)

    records = OBJECTS[object_type]
    # Simulate pagination: 1 record per page so multi-page logic is exercised.
    start = int(after) if after else 0
    page = records[start:start + 1]
    body: dict = {'results': page}
    next_start = start + 1
    if next_start < len(records):
        body['paging'] = {'next': {'after': str(next_start)}}
    return body
