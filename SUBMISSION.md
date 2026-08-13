# Submission Notes

Two things for the email reply, pulled out of the full write-up in
[README.md](README.md) / [ARCHITECTURE.md](ARCHITECTURE.md) so they're easy to paste
or read standalone.

---

## Implementation approach (paste into the email body)

I completed both parts of `hubspot.py` — `authorize_hubspot`, `oauth2callback_hubspot`,
`get_hubspot_credentials`, and `get_items_hubspot` — following the exact
authorize → popup → callback → credentials → load contract already used by the
provided `airtable.py` and `notion.py`, so HubSpot slots into the existing routing and
frontend without changing their shape.

**OAuth (Part 1):** `authorize_hubspot` builds HubSpot's consent URL with a
CSRF `state` (persisted in Redis with a short TTL) and a PKCE `code_challenge`
(`S256`) generated on every request — HubSpot's newer OAuth-2.1 developer apps require
PKCE, while classic apps simply ignore the extra parameters, so one code path handles
both without a feature flag. `oauth2callback_hubspot` verifies the state came back
unmodified before exchanging the code for tokens (HubSpot expects `client_id` /
`client_secret` in the POST body here, unlike Airtable/Notion's HTTP Basic), then
caches the tokens in Redis. `get_hubspot_credentials` pops them out once — single-use,
so a replayed request can't leak a stale token.

**Loading items (Part 2):** `get_items_hubspot` fetches contacts, companies, and deals
from the CRM v3 API concurrently via `asyncio.gather` (plus a hub-id lookup used to
build deep links back into HubSpot), each with cursor-based pagination capped at 10
pages so one request can't run away on a very large portal. A `403` on one object type
(a scope the user didn't grant) degrades to an empty result for that type instead of
failing the whole load; a `401` still raises, since that's not recoverable within the
request. Each record maps onto the shared `IntegrationItem` shape with a
provider-appropriate name fallback (e.g. contact: full name → email → `Contact <id>`),
grouped under one directory item per object type — the same collection → record
hierarchy the Airtable integration already uses, so `data-form.js` can render all
three providers' results with one table component.

**Along the way**, I found and fixed a few bugs in the provided code while building
against it: `get_items_notion` was missing its `return` statement (so `/notion/load`
always responded `null`), `airtable.py` had a live Client ID/Secret hardcoded in
source, and the frontend's popup-close detection had a race condition when a popup
was blocked. Full details and reasoning for every change are in README.md's
"Changes to provided code" section.

**Testing:** 18 offline pytest unit tests (Redis and HubSpot's API both faked — no
credentials needed to run them) cover the OAuth state machine, PKCE correctness,
pagination, and error handling. Beyond that, I created a real HubSpot OAuth app and
ran the full flow end-to-end against my own account — the "Load Data" screenshot in
the recording is genuinely live HubSpot data, not a mock.

---

## Screen recording script (~90 seconds)

Record with the backend, frontend, and Redis already running
(`uvicorn main:app --reload`, `npm start`, Redis) and `backend/.env` filled in with a
real HubSpot Client ID/Secret (see README "Create a HubSpot app").

1. **(0:00–0:10) Open http://localhost:3000.**
   Say: *"This is the integrations app with HubSpot added alongside the existing
   Airtable and Notion integrations."*
   Fill in User / Organization, open the Integration Type dropdown to show **HubSpot**
   is a selectable option next to Airtable/Notion.

2. **(0:10–0:35) Select HubSpot, click "Connect to HubSpot."**
   Say: *"This calls authorize_hubspot on the backend, which builds a HubSpot consent
   URL with a CSRF state and PKCE challenge, and opens it in a popup."*
   Let HubSpot's real consent screen load, click **Allow/Install**. Point out the
   popup closing itself and the button flipping to **"HubSpot Connected"**.
   Say: *"The popup closing triggers the frontend to call oauth2callback's result via
   the /credentials endpoint, which pops the tokens out of Redis."*

3. **(0:35–1:05) Click "Load Data."**
   Say: *"This calls get_items_hubspot, which fetches contacts, companies, and deals
   from HubSpot's CRM API concurrently and maps them onto IntegrationItem objects."*
   Show the resulting table — point out the directory rows (Contacts / Companies /
   Deals), the individual records, and click one **"Open"** link to show it deep-links
   back into the real HubSpot record.

4. **(1:05–1:20) Open the backend terminal.**
   Say: *"The same list is also printed to the console, per the suggested approach in
   the brief."* Scroll to show the `IntegrationItem(...)` list.

5. **(1:20–1:30) (Optional) Click "Clear Data," then briefly show `hubspot.py`** in an
   editor — `authorize_hubspot`, `oauth2callback_hubspot`, `get_hubspot_credentials`,
   `get_items_hubspot` — to close out showing the actual implementation.

Keep it under 2 minutes; the goal is proving the flow works end-to-end against a real
HubSpot account, not narrating every line of code.
