// playwright_test.js
//
// Drives the REAL frontend (localhost:3000) against the REAL backend
// (localhost:8000), which in turn talks to the mock HubSpot server
// (localhost:9500). Only HubSpot's own servers are substituted; every line
// of frontend/backend code in the submission runs unmodified.

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const results = [];
function record(step, pass, detail) {
    results.push({ step, pass, detail });
    console.log(`${pass ? 'PASS' : 'FAIL'} - ${step}${detail ? ' :: ' + detail : ''}`);
}

async function shot(page, name) {
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, name), fullPage: true });
}

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    page.on('console', (msg) => {
        if (msg.type() === 'error') console.log('  [browser console error]', msg.text());
    });

    try {
        // --- 1. Load the app -------------------------------------------------
        await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
        record('App loads', await page.locator('text=User').first().isVisible());
        await shot(page, '01-loaded.png');

        // --- 2. Fill user/org -------------------------------------------------
        const userField = page.locator('label:has-text("User")').locator('..').locator('input');
        const orgField = page.locator('label:has-text("Organization")').locator('..').locator('input');
        await userField.fill('E2EUser');
        await orgField.fill('E2EOrg');
        record('User/Org fields fillable', (await userField.inputValue()) === 'E2EUser');

        // --- 3. Select HubSpot from the Integration Type dropdown ------------
        await page.locator('#integration-type').click();
        await page.getByRole('option', { name: 'HubSpot', exact: true }).click();
        const connectButton = page.getByRole('button', { name: /Connect to HubSpot/i });
        record('HubSpot selectable in Integration Type dropdown', await connectButton.isVisible());
        await shot(page, '02-hubspot-selected.png');

        // --- 4. Click Connect -> real /authorize call -> popup opens ---------
        const [popup] = await Promise.all([
            context.waitForEvent('page'),
            connectButton.click(),
        ]);
        await popup.waitForLoadState('networkidle');
        record(
            'Connect click opens OAuth popup pointed at the (mock) HubSpot authorize URL',
            popup.url().includes('/oauth/authorize') && popup.url().includes('client_id=mock-hubspot-client-id')
        );
        await popup.screenshot({ path: path.join(SCREENSHOT_DIR, '03-oauth-popup-consent.png') });

        // --- 5. Approve consent in the popup (this is the one step a real ----
        //        HubSpot login+approval click would occupy) -------------------
        await popup.locator('#approve').click();
        await popup.waitForEvent('close', { timeout: 10000 }).catch(() => {});
        record('Popup closes itself after the callback runs (window.close())', popup.isClosed());

        // --- 6. Main window polls popup.closed, fetches credentials ----------
        const connectedButton = page.getByRole('button', { name: /HubSpot Connected/i });
        await connectedButton.waitFor({ state: 'visible', timeout: 10000 });
        record('Main window detects popup close and shows "HubSpot Connected"', true);
        await shot(page, '04-connected.png');

        // --- 7. Load Data -> real /load call -> real CRM item mapping --------
        const loadButton = page.getByRole('button', { name: /Load Data/i });
        await loadButton.click();

        const table = page.locator('table');
        await table.waitFor({ state: 'visible', timeout: 10000 });
        const rowTexts = await table.locator('tbody tr').allTextContents();
        await shot(page, '05-data-loaded.png');

        const expectedNames = ['Ada Lovelace', 'Grace Hopper', 'Pipeline AI', 'Enterprise Rollout', 'Pilot Program'];
        const joined = rowTexts.join(' | ');
        const allPresent = expectedNames.every((n) => joined.includes(n));
        record('Loaded table contains contacts, companies and deals from the mock CRM', allPresent, joined);

        const collectionRows = rowTexts.filter((t) => /Collection/.test(t));
        record('Directory/collection items rendered for each object type', collectionRows.length === 3);

        const linkCount = await table.locator('tbody a:has-text("Open")').count();
        record('Record deep-links (url field) rendered', linkCount >= 5, `${linkCount} links`);

        // --- 8. Clear Data ------------------------------------------------
        await page.getByRole('button', { name: /Clear Data/i }).click();
        await page.waitForTimeout(300);
        const noTable = (await table.count()) === 0;
        record('Clear Data resets the view', noTable);

    } catch (err) {
        record('Unhandled error during E2E run', false, err.message);
        await shot(page, 'error-state.png').catch(() => {});
    } finally {
        await browser.close();
    }

    console.log('\n=== SUMMARY ===');
    const failed = results.filter((r) => !r.pass);
    for (const r of results) console.log(`${r.pass ? '✔' : '✘'} ${r.step}`);
    console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
    fs.writeFileSync(path.join(__dirname, 'results.json'), JSON.stringify(results, null, 2));
    process.exit(failed.length ? 1 : 0);
})();
