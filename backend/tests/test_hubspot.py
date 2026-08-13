"""Unit tests for backend/integrations/hubspot.py.

Runs entirely offline: Redis and HubSpot's HTTP API are replaced with
lightweight fakes so `pytest` needs no live services or credentials. See
`e2e/` for the separate, heavier browser-driven end-to-end suite.
"""
import base64
import hashlib
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import HTTPException

from integrations import hubspot

# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class FakeRedis:
    """In-memory stand-in for the three redis_client helpers hubspot.py uses."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def add(self, key, value, expire=None):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = json.dumps(self._json)

    def json(self):
        return self._json


class FakeAsyncClient:
    """Stand-in for httpx.AsyncClient; routes calls to a per-test handler."""

    handler = None  # set per-test via the fake_http fixture

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url, **kwargs):
        return FakeAsyncClient.handler('GET', url, kwargs)

    async def post(self, url, **kwargs):
        return FakeAsyncClient.handler('POST', url, kwargs)


class DummyRequest:
    """Minimal stand-in for fastapi.Request; hubspot.py only reads .query_params."""

    def __init__(self, params: dict):
        self.query_params = params


@pytest.fixture
def fake_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(hubspot, 'add_key_value_redis', redis.add)
    monkeypatch.setattr(hubspot, 'get_value_redis', redis.get)
    monkeypatch.setattr(hubspot, 'delete_key_redis', redis.delete)
    return redis


@pytest.fixture
def fake_http(monkeypatch):
    def _install(handler):
        FakeAsyncClient.handler = handler
        monkeypatch.setattr(httpx, 'AsyncClient', FakeAsyncClient)

    return _install


@pytest.fixture(autouse=True)
def fixed_credentials(monkeypatch):
    """Deterministic client id/secret regardless of the local .env, so these
    tests pass the same way on a fresh clone with no .env at all."""
    monkeypatch.setattr(hubspot, 'CLIENT_ID', 'test-client-id')
    monkeypatch.setattr(
        hubspot, 'REDIRECT_URI', 'http://localhost:8000/integrations/hubspot/oauth2callback'
    )
    monkeypatch.setenv('HUBSPOT_CLIENT_SECRET', 'test-client-secret')


# --------------------------------------------------------------------------
# authorize_hubspot
# --------------------------------------------------------------------------


async def test_authorize_hubspot_builds_valid_consent_url_and_persists_state(fake_redis):
    url = await hubspot.authorize_hubspot('user-1', 'org-1')

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    assert url.startswith(hubspot.AUTHORIZATION_URL)
    assert qs['client_id'] == ['test-client-id']
    assert qs['redirect_uri'] == [hubspot.REDIRECT_URI]
    assert set(qs['scope'][0].split()) == set(hubspot.SCOPES)
    assert qs['response_type'] == ['code']
    assert qs['code_challenge_method'] == ['S256']
    assert 'code_challenge' in qs
    assert 'state' in qs

    # State (and the PKCE verifier) were persisted for the callback to check later.
    saved = json.loads(fake_redis.store['hubspot_state:org-1:user-1'])
    assert saved['user_id'] == 'user-1'
    assert saved['org_id'] == 'org-1'
    assert 'code_verifier' in saved

    # The challenge in the URL really is SHA256(code_verifier), base64url, unpadded.
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(saved['code_verifier'].encode()).digest())
        .decode()
        .rstrip('=')
    )
    assert qs['code_challenge'][0] == expected_challenge


async def test_authorize_hubspot_requires_client_id(monkeypatch, fake_redis):
    monkeypatch.setattr(hubspot, 'CLIENT_ID', '')
    with pytest.raises(HTTPException) as exc_info:
        await hubspot.authorize_hubspot('user-1', 'org-1')
    assert exc_info.value.status_code == 500


# --------------------------------------------------------------------------
# oauth2callback_hubspot
# --------------------------------------------------------------------------


async def test_oauth2callback_rejects_missing_code_or_state(fake_redis):
    with pytest.raises(HTTPException) as exc_info:
        await hubspot.oauth2callback_hubspot(DummyRequest({}))
    assert exc_info.value.status_code == 400


async def test_oauth2callback_surfaces_provider_error(fake_redis):
    request = DummyRequest({'error': 'access_denied', 'error_description': 'User said no'})
    with pytest.raises(HTTPException) as exc_info:
        await hubspot.oauth2callback_hubspot(request)
    assert exc_info.value.status_code == 400
    assert 'User said no' in exc_info.value.detail


async def test_oauth2callback_rejects_tampered_state(fake_redis):
    # Well-formed but never issued by authorize_hubspot / not present in Redis.
    fake_state = base64.urlsafe_b64encode(
        json.dumps({'state': 'not-the-real-one', 'user_id': 'u1', 'org_id': 'o1'}).encode()
    ).decode()
    request = DummyRequest({'code': 'abc', 'state': fake_state})
    with pytest.raises(HTTPException) as exc_info:
        await hubspot.oauth2callback_hubspot(request)
    assert exc_info.value.status_code == 400
    assert 'State does not match' in exc_info.value.detail


async def test_oauth2callback_exchanges_code_for_tokens(fake_redis, fake_http):
    # Run the real authorize step first so a valid state/verifier is in Redis.
    auth_url = await hubspot.authorize_hubspot('user-1', 'org-1')
    state = parse_qs(urlparse(auth_url).query)['state'][0]

    captured = {}

    def handler(method, url, kwargs):
        assert method == 'POST'
        assert url == hubspot.TOKEN_URL
        captured['data'] = kwargs['data']
        return FakeResponse(
            200,
            {
                'access_token': 'fake-access-token',
                'refresh_token': 'fake-refresh-token',
                'expires_in': 1800,
            },
        )

    fake_http(handler)

    request = DummyRequest({'code': 'auth-code-123', 'state': state})
    response = await hubspot.oauth2callback_hubspot(request)

    assert response.status_code == 200
    assert captured['data']['code'] == 'auth-code-123'
    assert captured['data']['client_secret'] == 'test-client-secret'
    assert 'code_verifier' in captured['data']  # PKCE round-trip

    stored = json.loads(fake_redis.store['hubspot_credentials:org-1:user-1'])
    assert stored['access_token'] == 'fake-access-token'
    # State is single-use: consumed by the callback.
    assert 'hubspot_state:org-1:user-1' not in fake_redis.store


async def test_oauth2callback_raises_on_failed_token_exchange(fake_redis, fake_http):
    auth_url = await hubspot.authorize_hubspot('user-1', 'org-1')
    state = parse_qs(urlparse(auth_url).query)['state'][0]

    fake_http(lambda method, url, kwargs: FakeResponse(401, {'message': 'bad code'}))

    request = DummyRequest({'code': 'bad-code', 'state': state})
    with pytest.raises(HTTPException) as exc_info:
        await hubspot.oauth2callback_hubspot(request)
    assert exc_info.value.status_code == 401


# --------------------------------------------------------------------------
# get_hubspot_credentials
# --------------------------------------------------------------------------


async def test_get_hubspot_credentials_is_single_use(fake_redis):
    fake_redis.store['hubspot_credentials:org-1:user-1'] = json.dumps({'access_token': 'tok'})

    creds = await hubspot.get_hubspot_credentials('user-1', 'org-1')
    assert creds['access_token'] == 'tok'

    with pytest.raises(HTTPException) as exc_info:
        await hubspot.get_hubspot_credentials('user-1', 'org-1')
    assert exc_info.value.status_code == 400


async def test_get_hubspot_credentials_missing_raises_400(fake_redis):
    with pytest.raises(HTTPException) as exc_info:
        await hubspot.get_hubspot_credentials('nobody', 'nowhere')
    assert exc_info.value.status_code == 400


# --------------------------------------------------------------------------
# Item-mapping helpers (the "which fields matter, how are they named" logic)
# --------------------------------------------------------------------------

CONTACT_CONFIG = hubspot.HUBSPOT_OBJECTS[0]
COMPANY_CONFIG = hubspot.HUBSPOT_OBJECTS[1]
DEAL_CONFIG = hubspot.HUBSPOT_OBJECTS[2]


def test_contact_name_prefers_full_name_over_email():
    record = {
        'id': '101',
        'createdAt': '2024-01-01T00:00:00Z',
        'updatedAt': '2024-02-01T00:00:00Z',
        'archived': False,
        'properties': {'firstname': 'Ada', 'lastname': 'Lovelace', 'email': 'ada@example.com'},
    }
    item = hubspot.create_integration_item_metadata_object(record, CONTACT_CONFIG, hub_id='123')
    assert item.name == 'Ada Lovelace'
    assert item.type == 'Contact'
    assert item.id == '101_Contact'
    assert item.parent_path_or_name == 'Contacts'
    assert item.url == 'https://app.hubspot.com/contacts/123/record/0-1/101'
    assert item.visibility is True


def test_contact_name_falls_back_to_email_then_placeholder():
    no_name = {'id': '102', 'properties': {'email': 'grace@example.com'}}
    item = hubspot.create_integration_item_metadata_object(no_name, CONTACT_CONFIG)
    assert item.name == 'grace@example.com'

    no_name_or_email = {'id': '103', 'properties': {}}
    item = hubspot.create_integration_item_metadata_object(no_name_or_email, CONTACT_CONFIG)
    assert item.name == 'Contact 103'


def test_company_name_falls_back_to_domain():
    record = {'id': '201', 'properties': {'domain': 'example.com'}}
    item = hubspot.create_integration_item_metadata_object(record, COMPANY_CONFIG)
    assert item.name == 'example.com'


def test_archived_record_is_not_visible():
    record = {'id': '301', 'archived': True, 'properties': {'dealname': 'Old Deal'}}
    item = hubspot.create_integration_item_metadata_object(record, DEAL_CONFIG)
    assert item.visibility is False


def test_directory_item_reports_child_count():
    item = hubspot._create_directory_item(CONTACT_CONFIG, child_count=5)
    assert item.directory is True
    assert item.type == 'Contact Collection'
    assert item.children == ['5']


# --------------------------------------------------------------------------
# get_items_hubspot (pagination, concurrency, graceful degradation)
# --------------------------------------------------------------------------


def _crm_page(records, next_after=None):
    body = {'results': records}
    if next_after:
        body['paging'] = {'next': {'after': next_after}}
    return body


async def test_get_items_hubspot_paginates_and_aggregates_all_object_types(fake_http):
    contacts_pages = [
        _crm_page([{'id': '1', 'properties': {'firstname': 'A', 'lastname': 'One'}}], next_after='2'),
        _crm_page([{'id': '2', 'properties': {'firstname': 'B', 'lastname': 'Two'}}]),
    ]
    contacts_calls = {'n': 0}

    def handler(method, url, kwargs):
        assert method == 'GET'
        if 'access-tokens' in url:
            return FakeResponse(200, {'hub_id': 999})
        if url.endswith('/contacts'):
            page = contacts_pages[contacts_calls['n']]
            contacts_calls['n'] += 1
            return FakeResponse(200, page)
        if url.endswith('/companies'):
            return FakeResponse(200, _crm_page([{'id': '10', 'properties': {'name': 'Acme'}}]))
        if url.endswith('/deals'):
            return FakeResponse(200, _crm_page([{'id': '20', 'properties': {'dealname': 'Big Deal'}}]))
        raise AssertionError(f'unexpected URL {url}')

    fake_http(handler)

    items = await hubspot.get_items_hubspot({'access_token': 'tok'})

    # 3 directory items + 2 contacts + 1 company + 1 deal = 7
    assert len(items) == 7
    assert contacts_calls['n'] == 2  # both pages were fetched

    directories = {i.type: i for i in items if i.directory}
    assert directories['Contact Collection'].children == ['2']

    names = {i.name for i in items}
    assert {'A One', 'B Two', 'Acme', 'Big Deal'} <= names

    # Deep links use the hub_id from the concurrent access-token lookup.
    contact = next(i for i in items if i.id == '1_Contact')
    assert contact.url == 'https://app.hubspot.com/contacts/999/record/0-1/1'


async def test_get_items_hubspot_skips_object_type_on_403(fake_http):
    def handler(method, url, kwargs):
        if 'access-tokens' in url:
            return FakeResponse(200, {'hub_id': 1})
        if url.endswith('/contacts'):
            return FakeResponse(200, _crm_page([{'id': '1', 'properties': {'firstname': 'A'}}]))
        if url.endswith('/companies'):
            return FakeResponse(403, {'message': 'missing scope'})
        if url.endswith('/deals'):
            return FakeResponse(200, _crm_page([]))
        raise AssertionError(url)

    fake_http(handler)

    items = await hubspot.get_items_hubspot({'access_token': 'tok'})

    # Companies degrades to an empty collection instead of failing the whole load.
    companies_dir = next(i for i in items if i.type == 'Company Collection')
    assert companies_dir.children == ['0']
    assert any(i.type == 'Contact' for i in items)


async def test_get_items_hubspot_raises_on_401(fake_http):
    def handler(method, url, kwargs):
        if 'access-tokens' in url:
            return FakeResponse(200, {'hub_id': 1})
        return FakeResponse(401, {'message': 'expired token'})

    fake_http(handler)

    with pytest.raises(HTTPException) as exc_info:
        await hubspot.get_items_hubspot({'access_token': 'expired'})
    assert exc_info.value.status_code == 401


async def test_get_items_hubspot_requires_access_token():
    with pytest.raises(HTTPException) as exc_info:
        await hubspot.get_items_hubspot({})
    assert exc_info.value.status_code == 400
