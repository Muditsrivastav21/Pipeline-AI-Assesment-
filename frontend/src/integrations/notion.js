// notion.js

import { IntegrationConnect } from './integration-connect';

export const NotionIntegration = (props) => (
    <IntegrationConnect integrationType="Notion" {...props} />
);
