# Pipeline AI  Integrations Technical Assessment

HubSpot OAuth 2.0 integration (Part 1) and CRM item loading (Part 2), built alongside
the provided Airtable and Notion integrations.

See [ARCHITECTURE.md](ARCHITECTURE.md) for system diagrams (OAuth sequence, data
flow, code layout, and data model), and [SUBMISSION.md](SUBMISSION.md) for the
implementation write-up and screen-recording script.

---

## Quick start

### 0. Prerequisites

- Python 3.10+
- Node 18+
- Redis

```bash
redis-server
```

### 1. Create a HubSpot app

HubSpot has retired browser-only app creation ("Legacy Apps" public-app creation is
disabled) in favor of the **Projects** framework, which is scaffolded via their CLI:

```bash
npm i -g @hubspot/cli
hs account auth                 # opens a browser to log in and authorize the CLI
hs project create \
  --name PipelineHubSpotApp \
  --project-base app \
  --distribution private \
  --auth oauth \
  --features
```

> `--distribution private` matters: `marketplace` distribution requires signing
> HubSpot's publisher acceptable-use policy before the app can even be installed in your
> own account, which is unnecessary friction for local testing.

Edit the generated `src/app/app-hsmeta.json` and set:

```jsonc
"redirectUrls": ["http://localhost:8000/integrations/hubspot/oauth2callback"],
"requiredScopes": [
  "oauth",
  "crm.objects.contacts.read",
  "crm.objects.companies.read",
  "crm.objects.deals.read"
],
```

Then deploy it and grab the credentials:

```bash
cd PipelineHubSpotApp
hs project upload --force
```

Open the printed HubSpot URL → your app → **Auth** tab → copy the **Client ID** and
**Client secret**.

> Sample CRM data is already seeded into every HubSpot account (e.g. "Brian Halligan
> (Sample Contact)"), so a developer test account isn't required to see records load.

### 2. Backend

```bash
cd backend
cp .env.example .env          # then fill in HUBSPOT_CLIENT_ID / HUBSPOT_CLIENT_SECRET
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm i
npm run start
```

Open <http://localhost:3000>, pick **HubSpot** in the Integration Type dropdown,
click **Connect to HubSpot**, approve the app in the popup, then click **Load Data**.

The resulting `IntegrationItem` list is:
- printed to the **backend console** (the suggested approach in the brief),
- logged to the **browser console**, and
- rendered as a **table** in the UI.

---

## What was implemented

### Part 1 - HubSpot OAuth (`backend/integrations/hubspot.py`)

| Function | Behaviour |
| --- | --- |
| `authorize_hubspot` | Builds `https://app.hubspot.com/oauth/authorize` with `client_id`, `redirect_uri`, space-separated `scope`, and a random `state`. The state (plus `user_id`/`org_id`) is stored in Redis with a 10-minute TTL. |
| `oauth2callback_hubspot` | Rejects provider errors and missing/malformed params, verifies the returned `state` against Redis (CSRF), then POSTs form-encoded to `https://api.hubapi.com/oauth/v1/token` with `grant_type=authorization_code`. Tokens are cached in Redis (10-min TTL) and the popup is closed. |
| `get_hubspot_credentials` | Pops the credentials from Redis (single-use) or raises `400 No credentials found.` |
| `refresh_hubspot_token` | Bonus: exchanges a `refresh_token` for a fresh access token. |

Note: HubSpot's token endpoint takes `client_id`/`client_secret` **in the form body**
(unlike Airtable/Notion, which use HTTP Basic). PKCE (RFC 7636, `S256`) is generated and
sent on every authorize/token round trip: HubSpot's newer Projects-based apps run OAuth
2.1 and mandate it, while classic apps simply ignore the extra parameters, so one code
path works against both.

### Part 2 — Loading items (`get_items_hubspot`)

Queries three CRM v3 endpoints concurrently (`asyncio.gather`):

- `GET /crm/v3/objects/contacts`
- `GET /crm/v3/objects/companies`
- `GET /crm/v3/objects/deals`

and maps each record onto an `IntegrationItem`:

| `IntegrationItem` field | Source |
| --- | --- |
| `id` | `<hubspot id>_<Type>`, e.g. `101_Contact` |
| `type` | `Contact` / `Company` / `Deal` |
| `name` | contact: full name → email → `Contact <id>`; company: `name` → `domain`; deal: `dealname` |
| `creation_time` / `last_modified_time` | `createdAt` / `updatedAt` |
| `parent_id`, `parent_path_or_name` | the object's collection (`Contacts`, `Companies`, `Deals`) |
| `url` | deep link `https://app.hubspot.com/contacts/<hubId>/record/<objectTypeId>/<id>`; the hub id comes from `GET /oauth/v1/access-tokens/<token>` |
| `directory` | `true` on the one collection item emitted per object type |
| `children` | record count on collection items |
| `visibility` | `false` for archived records |

Structure: a flat list of one **collection** item per object type, each followed by its
records - the same base/table parent-child shape the Airtable integration uses.

Handling:
- **Pagination** via the `paging.next.after` cursor (`limit=100`, capped at 10 pages per
  object type so one request can't run away).
- **`403`** on an object type (scope not granted) is skipped rather than failing the
  whole load; **`401`** and other errors surface as `HTTPException`.
- Requests use `httpx.AsyncClient`, so the event loop is never blocked.

### Frontend

- `src/integrations/hubspot.js` — the HubSpot integration component.
- `src/integrations/integration-connect.js` — **new**: the connect/popup/credentials
  flow was identical across all three integrations, so it was extracted into one
  reusable component. `airtable.js`, `notion.js` and `hubspot.js` are now thin wrappers.
- `src/integration-form.js` — HubSpot registered in `integrationMapping`.
- `src/data-form.js` — HubSpot endpoint registered; loaded items render as a sortable
  table (type, name, parent, last modified, deep link) instead of a raw string in a
  disabled text field.
- `src/config.js` — single source of truth for the API base URL and the
  integration → endpoint slug map, so OAuth and load routes cannot drift.

---

## Changes to provided code (and why)

The brief allows modifying provided files. Beyond adding HubSpot:

1. **Secrets removed from source.** `airtable.py` contained a live Client ID and Secret
   committed in plaintext. All credentials now load from `backend/.env` via
   `backend/config.py`; `.env.example` documents the required variables and `.gitignore`
   keeps `.env` out of version control.
2. **`get_items_notion` never returned its result** — it built the list, printed it, then
   fell through to a bare `return`, so `/integrations/notion/load` always responded
   `null`. Fixed to return the list.
3. **HubSpot load route renamed** from `/integrations/hubspot/get_hubspot_items` (whose
   handler was also misnamed `load_slack_data_integration`) to
   `/integrations/hubspot/load`, matching Airtable and Notion.
4. **`IntegrationItem` gained `to_dict()` and `__repr__`.** Without `__repr__`, printing
   the list to the console — the brief's suggested output — produced
   `<IntegrationItem object at 0x...>`. Routes now serialize explicitly via `to_dict()`.
5. **Popup-blocked bug in the OAuth flow.** The original poll condition
   `newWindow?.closed !== false` evaluates to `true` when `window.open` returns `null`
   (popup blocked), immediately firing the credentials request against a flow that never
   ran. Now handled explicitly, and the poll interval is cleared on unmount.
6. **Switching integration type clears stale credentials**, so the data form can't load
   one provider using another's tokens.
7. **CORS origin** is configurable via `FRONTEND_ORIGIN`.

---

## Verification

### Automated tests

```bash
cd backend
pip install -r requirements-test.txt
pytest tests/test_hubspot.py -v
```

18 unit tests in `backend/tests/test_hubspot.py`, run entirely offline (Redis and
HubSpot's HTTP API are both faked, no credentials or network needed):

| Area | Covered by |
| --- | --- |
| `authorize_hubspot` | Consent URL has the right host/scopes/state; PKCE `code_challenge` really is `SHA256(code_verifier)`; missing `CLIENT_ID` raises `500`. |
| `oauth2callback_hubspot` | Missing `code`/`state` → `400`; provider `error` param surfaces; tampered/unknown `state` → `400 State does not match.`; a successful exchange stores tokens in Redis and consumes the state (single use); a failed exchange propagates HubSpot's status code. |
| `get_hubspot_credentials` | Single-use retrieval (second call → `400`); missing credentials → `400`. |
| Item mapping | Contact name fallback chain (full name → email → placeholder); company name falls back to domain; archived records get `visibility=False`; directory items report the correct child count. |
| `get_items_hubspot` | Multi-page pagination is followed to completion; all three object types are aggregated with correct parent/child structure and hub-id-based deep links; a `403` on one object type degrades to an empty collection instead of failing the whole load; a `401` raises; a request with no `access_token` is rejected before any HTTP call is made. |

### Two layers of end-to-end testing were also done, both against the unmodified submission code:

**1. Offline / mocked E2E** — Redis and HubSpot's API replaced with fakes:

- 10/10 Playwright E2E checks (browser → popup consent → connected state → loaded
  table → clear) against a protocol-faithful mock HubSpot server.
- Through the real FastAPI stack: `/authorize`, `/credentials` (including single-use
  semantics and the `400` empty case) and `/load` return correct JSON.

**2. Live end-to-end** — a real HubSpot Projects app (private distribution, OAuth 2.1 +
PKCE) was created, its Client ID/Secret placed in `backend/.env`, and the full flow
exercised through the actual UI:

- Real consent/install screen → **Allow** → popup closes → **"HubSpot Connected"**.
- **Load Data** returned the account's live seeded CRM records (contacts, a company,
  and deal/company collections), rendered correctly as directory + record rows with
  working "Open" deep links back into HubSpot.
- Real Airtable and Notion OAuth apps were also created and connected through the same
  shared `integration-connect.js` flow to confirm the refactor didn't regress the
  provided integrations.

Frontend builds clean with warnings-as-errors (`CI=true npm run build`).
