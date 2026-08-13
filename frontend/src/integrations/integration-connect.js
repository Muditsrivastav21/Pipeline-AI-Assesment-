// integration-connect.js

import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Box, Button, CircularProgress, Snackbar, Typography } from '@mui/material';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import axios from 'axios';

import { API_BASE_URL, INTEGRATION_ENDPOINTS } from '../config';
import { PROVIDER_META } from './provider-meta';

/**
 * Shared OAuth "Connect" button.
 *
 * Every integration follows the same three steps:
 *   1. POST /integrations/<endpoint>/authorize   -> returns the provider consent URL
 *   2. open that URL in a popup and wait for it to close
 *   3. POST /integrations/<endpoint>/credentials -> returns the stored tokens
 *
 * Keeping it in one place means adding an integration only requires registering
 * its name, and fixes (popup blocking, timer cleanup) apply everywhere at once.
 */
export const IntegrationConnect = ({
    integrationType,
    user,
    org,
    integrationParams,
    setIntegrationParams,
}) => {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const [notice, setNotice] = useState(null); // { message, severity }
    const pollTimerRef = useRef(null);

    const endpoint = INTEGRATION_ENDPOINTS[integrationType];
    const meta = PROVIDER_META[integrationType] || {};

    const clearPollTimer = useCallback(() => {
        if (pollTimerRef.current) {
            window.clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
        }
    }, []);

    // Step 3: the popup closed, so the callback should have stored credentials.
    const handleWindowClosed = useCallback(async () => {
        try {
            const formData = new FormData();
            formData.append('user_id', user);
            formData.append('org_id', org);
            const response = await axios.post(
                `${API_BASE_URL}/integrations/${endpoint}/credentials`,
                formData
            );
            const credentials = response.data;
            if (credentials) {
                setIsConnected(true);
                setIntegrationParams((prev) => ({
                    ...prev,
                    credentials,
                    type: integrationType,
                }));
            }
        } catch (e) {
            setNotice({
                message:
                    e?.response?.data?.detail ||
                    `Could not retrieve ${integrationType} credentials.`,
                severity: 'error',
            });
        } finally {
            setIsConnecting(false);
        }
    }, [user, org, endpoint, integrationType, setIntegrationParams]);

    // Steps 1 & 2.
    const handleConnectClick = async () => {
        try {
            setIsConnecting(true);
            const formData = new FormData();
            formData.append('user_id', user);
            formData.append('org_id', org);
            const response = await axios.post(
                `${API_BASE_URL}/integrations/${endpoint}/authorize`,
                formData
            );
            const authURL = response?.data;

            const newWindow = window.open(
                authURL,
                `${integrationType} Authorization`,
                'width=600, height=700'
            );

            // window.open returns null when the popup is blocked. Without this
            // guard the poll below would treat it as "already closed" and
            // immediately request credentials that do not exist yet.
            if (!newWindow) {
                setIsConnecting(false);
                setNotice({
                    message: 'Popup blocked. Please allow popups for this site and retry.',
                    severity: 'warning',
                });
                return;
            }

            clearPollTimer();
            pollTimerRef.current = window.setInterval(() => {
                if (newWindow.closed) {
                    clearPollTimer();
                    handleWindowClosed();
                }
            }, 200);
        } catch (e) {
            setIsConnecting(false);
            setNotice({
                message:
                    e?.response?.data?.detail ||
                    `Could not start the ${integrationType} authorization flow.`,
                severity: 'error',
            });
        }
    };

    useEffect(() => {
        setIsConnected(Boolean(integrationParams?.credentials));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Stop polling if the user switches integration mid-flow.
    useEffect(() => clearPollTimer, [clearPollTimer]);

    return (
        <Box>
            <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
                <Button
                    variant="contained"
                    onClick={isConnected ? () => {} : handleConnectClick}
                    disabled={isConnecting}
                    startIcon={isConnected ? <CheckCircleRoundedIcon /> : null}
                    sx={{
                        pointerEvents: isConnected ? 'none' : 'auto',
                        cursor: isConnected ? 'default' : 'pointer',
                        bgcolor: isConnected ? 'success.main' : meta.color,
                        color: '#fff',
                        '&:hover': {
                            bgcolor: isConnected ? 'success.dark' : meta.color,
                            filter: isConnected ? undefined : 'brightness(0.92)',
                        },
                        '&.Mui-disabled': {
                            bgcolor: meta.color,
                            opacity: 0.6,
                            color: '#fff',
                        },
                    }}
                >
                    {isConnecting ? (
                        <CircularProgress size={20} sx={{ color: '#fff' }} />
                    ) : isConnected ? (
                        `${integrationType} Connected`
                    ) : (
                        `Connect to ${integrationType}`
                    )}
                </Button>
                {isConnected && (
                    <Typography variant="body2" color="text.secondary">
                        Authorized — continue when you're ready.
                    </Typography>
                )}
            </Box>

            <Snackbar
                open={Boolean(notice)}
                autoHideDuration={5000}
                onClose={() => setNotice(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            >
                {notice && (
                    <Alert
                        severity={notice.severity}
                        variant="filled"
                        onClose={() => setNotice(null)}
                        sx={{ width: '100%' }}
                    >
                        {notice.message}
                    </Alert>
                )}
            </Snackbar>
        </Box>
    );
};
