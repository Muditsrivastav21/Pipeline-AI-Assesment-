import { useState } from 'react';
import {
    Box,
    Button,
    Container,
    Divider,
    Grid,
    Paper,
    Step,
    StepLabel,
    Stepper,
    TextField,
    Typography,
} from '@mui/material';

import { ProviderCard } from './components/ProviderCard';
import { DataForm } from './data-form';
import { AirtableIntegration } from './integrations/airtable';
import { HubSpotIntegration } from './integrations/hubspot';
import { NotionIntegration } from './integrations/notion';

const integrationMapping = {
    'HubSpot': HubSpotIntegration,
    'Airtable': AirtableIntegration,
    'Notion': NotionIntegration,
};

const STEPS = ['Your details', 'Connect a provider', 'Load data'];

export const IntegrationForm = () => {
    const [integrationParams, setIntegrationParams] = useState({});
    const [user, setUser] = useState('TestUser');
    const [org, setOrg] = useState('TestOrg');
    const [currType, setCurrType] = useState(null);
    const [activeStep, setActiveStep] = useState(0);

    const CurrIntegration = currType ? integrationMapping[currType] : null;
    const isConnected = Boolean(integrationParams?.credentials);
    const detailsComplete = user.trim().length > 0 && org.trim().length > 0;

    // Switching integration type must drop any previously loaded credentials,
    // otherwise the DataForm would load the new type using the old tokens.
    const handleTypeChange = (value) => {
        setCurrType(value);
        setIntegrationParams({});
    };

    return (
        <Container maxWidth="md" sx={{ py: { xs: 3, sm: 5 } }}>
            <Paper variant="outlined" sx={{ p: { xs: 2, sm: 4 } }}>
                <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4 }}>
                    {STEPS.map((label) => (
                        <Step key={label}>
                            <StepLabel>{label}</StepLabel>
                        </Step>
                    ))}
                </Stepper>

                {activeStep === 0 && (
                    <Box>
                        <Typography variant="h6" gutterBottom>
                            Who's connecting?
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                            These identify where credentials are stored — they are not sent to
                            the provider.
                        </Typography>
                        <Box display="flex" gap={2} flexWrap="wrap">
                            <TextField
                                label="User"
                                value={user}
                                onChange={(e) => setUser(e.target.value)}
                                sx={{ flex: 1, minWidth: 220 }}
                            />
                            <TextField
                                label="Organization"
                                value={org}
                                onChange={(e) => setOrg(e.target.value)}
                                sx={{ flex: 1, minWidth: 220 }}
                            />
                        </Box>
                        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
                            <Button
                                variant="contained"
                                disabled={!detailsComplete}
                                onClick={() => setActiveStep(1)}
                            >
                                Continue
                            </Button>
                        </Box>
                    </Box>
                )}

                {activeStep === 1 && (
                    <Box>
                        <Typography variant="h6" gutterBottom>
                            Choose an integration
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                            Pick a provider, then authorize access in the popup that opens.
                        </Typography>
                        <Grid container spacing={2}>
                            {Object.keys(integrationMapping).map((name) => (
                                <Grid item xs={12} sm={4} key={name}>
                                    <ProviderCard
                                        name={name}
                                        selected={currType === name}
                                        onSelect={handleTypeChange}
                                    />
                                </Grid>
                            ))}
                        </Grid>

                        {CurrIntegration && (
                            <Box sx={{ mt: 3 }}>
                                <Divider sx={{ mb: 3 }} />
                                <CurrIntegration
                                    key={currType}
                                    user={user}
                                    org={org}
                                    integrationParams={integrationParams}
                                    setIntegrationParams={setIntegrationParams}
                                />
                            </Box>
                        )}

                        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'space-between' }}>
                            <Button onClick={() => setActiveStep(0)}>Back</Button>
                            <Button
                                variant="contained"
                                disabled={!isConnected}
                                onClick={() => setActiveStep(2)}
                            >
                                Continue
                            </Button>
                        </Box>
                    </Box>
                )}

                {activeStep === 2 && (
                    <Box>
                        <Typography variant="h6" gutterBottom>
                            Load data from {currType}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                            Fetches everything <code>get_items_{currType?.toLowerCase()}</code>{' '}
                            returns and renders it below.
                        </Typography>
                        <DataForm
                            integrationType={integrationParams?.type}
                            credentials={integrationParams?.credentials}
                        />
                        <Box sx={{ mt: 3 }}>
                            <Button onClick={() => setActiveStep(1)}>Back</Button>
                        </Box>
                    </Box>
                )}
            </Paper>
        </Container>
    );
};
