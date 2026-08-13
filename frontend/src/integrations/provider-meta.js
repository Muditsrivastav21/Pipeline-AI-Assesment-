import airtableLogo from '../assets/logos/airtable.svg';
import hubspotLogo from '../assets/logos/hubspot.svg';
import notionLogo from '../assets/logos/notion.svg';

// Visual identity for each provider's card/button.
export const PROVIDER_META = {
    HubSpot: {
        color: '#FF7A59',
        logo: hubspotLogo,
        description: 'Sync contacts, companies, and deals from your CRM.',
    },
    Airtable: {
        color: '#2D7FF9',
        logo: airtableLogo,
        description: 'Pull records from your bases and tables.',
    },
    Notion: {
        color: '#1A1A1A',
        logo: notionLogo,
        description: 'Import pages and databases from your workspace.',
    },
};
