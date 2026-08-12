// config.js

export const API_BASE_URL =
    process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// Backend route slug for each integration type. Used for both the OAuth
// endpoints and the `/load` endpoint, so the two can never drift apart.
export const INTEGRATION_ENDPOINTS = {
    Notion: 'notion',
    Airtable: 'airtable',
    HubSpot: 'hubspot',
};
