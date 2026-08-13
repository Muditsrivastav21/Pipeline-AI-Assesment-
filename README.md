# Pipeline AI - Integrations Technical Assessment

HubSpot OAuth integration (Part 1) and CRM item loading (Part 2), built on top of the
provided Airtable and Notion integrations.

---

## Setup

Prereqs: Python 3.10+, Node 18+, Redis.

### 1. HubSpot app

Browser-only app creation is disabled on HubSpot now, so this goes through their CLI:

```bash
npm i -g @hubspot/cli
hs account auth
hs project create --name PipelineHubSpotApp --project-base app --distribution private --auth oauth --features
```

(`--distribution private` avoids having to sign HubSpot's marketplace acceptable-use
policy just to test locally.)

In the generated `src/app/app-hsmeta.json`, set:

```jsonc
"redirectUrls": ["http://localhost:8000/integrations/hubspot/oauth2callback"],
"requiredScopes": [
  "oauth",
  "crm.objects.contacts.read",
  "crm.objects.companies.read",
  "crm.objects.deals.read"
],
```

Then:

```bash
cd PipelineHubSpotApp
hs project upload --force
```

Grab the Client ID / Secret from the app's Auth tab in HubSpot.

### 2. Backend

```bash
cd backend
cp .env.example .env   # fill in HUBSPOT_CLIENT_ID / HUBSPOT_CLIENT_SECRET
pip install -r requirements.txt
uvicorn main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm i
npm run start
```

Open localhost:3000, fill in User/Org, pick HubSpot, connect, load data. The item list
gets printed to the backend console and shown in the UI table.

---

## hubspot.py

`authorize_hubspot` builds the consent URL (client_id, redirect_uri, scope, state) and
stashes the state in Redis with a short TTL so `oauth2callback_hubspot` can check it
came back unmodified before exchanging the code for tokens. Also generates a PKCE
`code_challenge` on every request — newer HubSpot apps require it, older ones ignore
it, so one code path covers both.

`get_hubspot_credentials` pops the cached tokens out of Redis (single use).

`get_items_hubspot` pulls contacts, companies and deals concurrently
(`asyncio.gather`), follows pagination cursors, and maps each record to an
`IntegrationItem` (name fallback chain per object type, parent set to the collection,
deep link built from a portal-id lookup). A 403 on one object type just returns an
empty list for that type instead of failing the whole load; 401 raises.

## Frontend

`integrations/hubspot.js` follows the same pattern as the existing Airtable/Notion
components. The connect/popup/credentials logic was identical across all three so it's
factored into `integrations/integration-connect.js` — the provider files are now thin
wrappers around that. `data-form.js` renders the loaded items as a table instead of
dumping raw JSON into a text field.

## Changes to the provided code

- `airtable.py` had a live client ID/secret hardcoded in source — moved all secrets
  into `backend/.env` (see `.env.example`), added `.gitignore`.
- `get_items_notion` was missing its `return`, so `/notion/load` always came back
  `null`.
- HubSpot's load route was `/get_hubspot_items` with a handler named
  `load_slack_data_integration` — renamed to match the Airtable/Notion convention.
- `IntegrationItem` had no `__repr__`, so printing the list (the suggested output
  method) just gave `<IntegrationItem object at 0x...>`. Added `__repr__`/`to_dict()`.
- The OAuth popup's close-detection had a bug: if `window.open` got blocked and
  returned `null`, the poll treated that as "already closed" and fired a credentials
  request immediately. Fixed with an explicit null check.
- Switching integration type now clears stale credentials so the data form can't load
  one provider's data with another provider's token.

## Testing

```bash
cd backend
pip install -r requirements-test.txt
pytest tests/test_hubspot.py -v
```

18 unit tests, fully offline (Redis and HubSpot's API are both faked). Covers the
OAuth state/PKCE flow, single-use credential retrieval, the item name-fallback logic,
pagination, and the 403/401 error handling.

Also tested against a real HubSpot app end-to-end (real OAuth consent screen, real
seeded CRM data loading into the table, deep links resolving back into HubSpot).
