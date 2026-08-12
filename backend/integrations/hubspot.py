# hubspot.py

"""HubSpot OAuth 2.0 integration.

Flow mirrors the Airtable/Notion integrations:

    authorize_hubspot          -> builds the consent URL, stashes CSRF state in Redis
    oauth2callback_hubspot     -> validates state, exchanges the code for tokens
    get_hubspot_credentials    -> pops the stored credentials for the frontend
    get_items_hubspot          -> reads CRM objects and maps them to IntegrationItems

Unlike the provided integrations this module uses `httpx.AsyncClient` for every
outbound call so the FastAPI event loop is never blocked, and it fans the three
CRM object types out concurrently.
"""

import asyncio
import base64
import hashlib
import json
import secrets
from typing import Any, Callable
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from config import get_env, redirect_uri, require_env
from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, delete_key_redis, get_value_redis

CLIENT_ID = get_env('HUBSPOT_CLIENT_ID')
CLIENT_SECRET = get_env('HUBSPOT_CLIENT_SECRET')
REDIRECT_URI = redirect_uri('hubspot')

AUTHORIZATION_URL = 'https://app.hubspot.com/oauth/authorize'
TOKEN_URL = 'https://api.hubapi.com/oauth/v1/token'
TOKEN_INFO_URL = 'https://api.hubapi.com/oauth/v1/access-tokens'
API_BASE_URL = 'https://api.hubapi.com'

# `oauth` is mandatory for any public app; the rest are what get_items reads.
SCOPES = [
    'oauth',
    'crm.objects.contacts.read',
    'crm.objects.companies.read',
    'crm.objects.deals.read',
]

STATE_TTL_SECONDS = 600
CREDENTIALS_TTL_SECONDS = 600

# Guard rails so a large portal cannot hang the request forever.
PAGE_SIZE = 100
MAX_PAGES_PER_OBJECT = 10
REQUEST_TIMEOUT = httpx.Timeout(30.0)


def _state_key(org_id: str, user_id: str) -> str:
    return f'hubspot_state:{org_id}:{user_id}'


def _credentials_key(org_id: str, user_id: str) -> str:
    return f'hubspot_credentials:{org_id}:{user_id}'


# ---------------------------------------------------------------------------
# Part 1 - OAuth
# ---------------------------------------------------------------------------

async def authorize_hubspot(user_id, org_id):
    """Return the HubSpot consent URL for this user/org."""
    if not CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail='HUBSPOT_CLIENT_ID is not configured. See backend/.env.example.',
        )

    # PKCE (RFC 7636): newer HubSpot developer projects mandate it (OAuth 2.1),
    # and it's harmless to include for classic public apps too, which ignore it.
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest())
        .decode('utf-8')
        .rstrip('=')
    )

    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id,
        'code_verifier': code_verifier,
    }
    encoded_state = base64.urlsafe_b64encode(
        json.dumps(state_data).encode('utf-8')
    ).decode('utf-8')

    await add_key_value_redis(
        _state_key(org_id, user_id),
        json.dumps(state_data),
        expire=STATE_TTL_SECONDS,
    )

    query = urlencode(
        {
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'scope': ' '.join(SCOPES),
            'state': encoded_state,
            'response_type': 'code',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        }
    )
    return f'{AUTHORIZATION_URL}?{query}'


async def oauth2callback_hubspot(request: Request):
    """Handle HubSpot's redirect: verify state, swap the code for tokens."""
    if request.query_params.get('error'):
        raise HTTPException(
            status_code=400,
            detail=request.query_params.get('error_description')
            or request.query_params.get('error'),
        )

    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail='Missing code or state parameter.')

    try:
        state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail='Invalid state parameter.')

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state_raw = await get_value_redis(_state_key(org_id, user_id))
    if not saved_state_raw:
        raise HTTPException(status_code=400, detail='State does not match.')
    saved_state = json.loads(saved_state_raw)
    if original_state != saved_state.get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')
    code_verifier = saved_state.get('code_verifier')

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response, _ = await asyncio.gather(
            client.post(
                TOKEN_URL,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': REDIRECT_URI,
                    'client_id': CLIENT_ID,
                    'client_secret': require_env('HUBSPOT_CLIENT_SECRET'),
                    # Only sent when we generated one (see authorize_hubspot); the
                    # real HubSpot token endpoint accepts/ignores it either way.
                    **({'code_verifier': code_verifier} if code_verifier else {}),
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
            ),
            delete_key_redis(_state_key(org_id, user_id)),
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f'HubSpot token exchange failed: {response.text}',
        )

    await add_key_value_redis(
        _credentials_key(org_id, user_id),
        json.dumps(response.json()),
        expire=CREDENTIALS_TTL_SECONDS,
    )

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    """Pop the credentials saved by the OAuth callback (single use)."""
    credentials = await get_value_redis(_credentials_key(org_id, user_id))
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')

    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')

    await delete_key_redis(_credentials_key(org_id, user_id))
    return credentials


async def refresh_hubspot_token(refresh_token: str) -> dict:
    """Exchange a refresh token for a fresh access token."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': require_env('HUBSPOT_CLIENT_ID'),
                'client_secret': require_env('HUBSPOT_CLIENT_SECRET'),
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f'HubSpot token refresh failed: {response.text}',
        )
    return response.json()


# ---------------------------------------------------------------------------
# Part 2 - Loading items
# ---------------------------------------------------------------------------

def _contact_name(properties: dict) -> str | None:
    full_name = ' '.join(
        part
        for part in (properties.get('firstname'), properties.get('lastname'))
        if part
    ).strip()
    return full_name or properties.get('email')


# Which CRM objects to pull, which properties matter, and how to name them.
# `object_type_id` is HubSpot's internal id used to build record permalinks.
HUBSPOT_OBJECTS: list[dict[str, Any]] = [
    {
        'type': 'Contact',
        'plural': 'Contacts',
        'path': 'contacts',
        'object_type_id': '0-1',
        'properties': [
            'firstname',
            'lastname',
            'email',
            'phone',
            'jobtitle',
            'company',
            'lifecyclestage',
        ],
        'name': _contact_name,
    },
    {
        'type': 'Company',
        'plural': 'Companies',
        'path': 'companies',
        'object_type_id': '0-2',
        'properties': [
            'name',
            'domain',
            'industry',
            'city',
            'country',
            'numberofemployees',
            'annualrevenue',
        ],
        'name': lambda properties: properties.get('name') or properties.get('domain'),
    },
    {
        'type': 'Deal',
        'plural': 'Deals',
        'path': 'deals',
        'object_type_id': '0-3',
        'properties': [
            'dealname',
            'dealstage',
            'pipeline',
            'amount',
            'closedate',
        ],
        'name': lambda properties: properties.get('dealname'),
    },
]


async def _fetch_object_page(
    client: httpx.AsyncClient,
    access_token: str,
    path: str,
    properties: list[str],
    after: str | None,
) -> dict:
    """Fetch one page of a CRM object list."""
    params: dict[str, Any] = {'limit': PAGE_SIZE, 'properties': ','.join(properties)}
    if after:
        params['after'] = after

    response = await client.get(
        f'{API_BASE_URL}/crm/v3/objects/{path}',
        headers={'Authorization': f'Bearer {access_token}'},
        params=params,
    )

    if response.status_code == 401:
        raise HTTPException(
            status_code=401, detail='HubSpot access token is invalid or expired.'
        )
    if response.status_code == 403:
        # Missing scope for this object type - skip it rather than failing the load.
        return {'results': []}
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f'HubSpot request for {path} failed: {response.text}',
        )
    return response.json()


async def _fetch_all_records(
    client: httpx.AsyncClient, access_token: str, config: dict
) -> list[dict]:
    """Page through every record of one CRM object type."""
    records: list[dict] = []
    after: str | None = None

    for _ in range(MAX_PAGES_PER_OBJECT):
        payload = await _fetch_object_page(
            client, access_token, config['path'], config['properties'], after
        )
        records.extend(payload.get('results', []))

        after = payload.get('paging', {}).get('next', {}).get('after')
        if not after:
            break

    return records


async def _fetch_hub_id(client: httpx.AsyncClient, access_token: str) -> str | None:
    """Look up the portal (hub) id so we can build clickable record URLs."""
    try:
        response = await client.get(f'{TOKEN_INFO_URL}/{access_token}')
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    hub_id = response.json().get('hub_id')
    return str(hub_id) if hub_id is not None else None


def create_integration_item_metadata_object(
    response_json: dict,
    config: dict,
    hub_id: str | None = None,
) -> IntegrationItem:
    """Map a single HubSpot CRM record onto an IntegrationItem."""
    properties = response_json.get('properties') or {}
    record_id = response_json.get('id')

    name_builder: Callable[[dict], str | None] = config['name']
    name = name_builder(properties) or f'{config["type"]} {record_id}'

    url = None
    if hub_id and record_id:
        url = (
            f'https://app.hubspot.com/contacts/{hub_id}'
            f'/record/{config["object_type_id"]}/{record_id}'
        )

    return IntegrationItem(
        id=f'{record_id}_{config["type"]}',
        type=config['type'],
        name=name,
        creation_time=response_json.get('createdAt'),
        last_modified_time=response_json.get('updatedAt'),
        parent_id=config['plural'],
        parent_path_or_name=config['plural'],
        url=url,
        mime_type=f'hubspot/{config["path"]}',
        visibility=not response_json.get('archived', False),
    )


def _create_directory_item(config: dict, child_count: int) -> IntegrationItem:
    """A folder-style item that groups all records of one object type."""
    return IntegrationItem(
        id=config['plural'],
        type=f'{config["type"]} Collection',
        name=config['plural'],
        directory=True,
        mime_type=f'hubspot/{config["path"]}',
        children=[str(child_count)],
    )


async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """Aggregate the metadata relevant to a HubSpot integration.

    Returns a flat list of IntegrationItems: one directory item per CRM object
    type, followed by that type's records (each record's `parent_id` points back
    at its directory).
    """
    if isinstance(credentials, str):
        credentials = json.loads(credentials)

    access_token = credentials.get('access_token')
    if not access_token:
        raise HTTPException(status_code=400, detail='No access token in credentials.')

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        hub_id, *record_groups = await asyncio.gather(
            _fetch_hub_id(client, access_token),
            *(
                _fetch_all_records(client, access_token, config)
                for config in HUBSPOT_OBJECTS
            ),
        )

    list_of_integration_item_metadata: list[IntegrationItem] = []
    for config, records in zip(HUBSPOT_OBJECTS, record_groups):
        list_of_integration_item_metadata.append(
            _create_directory_item(config, len(records))
        )
        for record in records:
            list_of_integration_item_metadata.append(
                create_integration_item_metadata_object(record, config, hub_id)
            )

    print(f'list_of_integration_item_metadata: {list_of_integration_item_metadata}')
    return list_of_integration_item_metadata
