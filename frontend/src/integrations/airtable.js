// airtable.js

import { IntegrationConnect } from './integration-connect';

export const AirtableIntegration = (props) => (
    <IntegrationConnect integrationType="Airtable" {...props} />
);
