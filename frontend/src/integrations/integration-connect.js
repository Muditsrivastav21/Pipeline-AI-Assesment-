// integration-connect.js

import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Button, CircularProgress } from '@mui/material';
import axios from 'axios';

import { API_BASE_URL, INTEGRATION_ENDPOINTS } from '../config';

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
    const pollTimerRef = useRef(null);

    const endpoint = INTEGRATION_ENDPOINTS[integrationType];

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
            alert(
                e?.response?.data?.detail ||
                    `Could not retrieve ${integrationType} credentials.`
            );
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
                alert('Popup blocked. Please allow popups for this site and retry.');
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
            alert(
                e?.response?.data?.detail ||
                    `Could not start the ${integrationType} authorization flow.`
            );
        }
    };

    useEffect(() => {
        setIsConnected(Boolean(integrationParams?.credentials));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Stop polling if the user switches integration mid-flow.
    useEffect(() => clearPollTimer, [clearPollTimer]);

    return (
        <Box sx={{ mt: 2 }}>
            Parameters
            <Box
                display="flex"
                alignItems="center"
                justifyContent="center"
                sx={{ mt: 2 }}
            >
                <Button
                    variant="contained"
                    onClick={isConnected ? () => {} : handleConnectClick}
                    color={isConnected ? 'success' : 'primary'}
                    disabled={isConnecting}
                    style={{
                        pointerEvents: isConnected ? 'none' : 'auto',
                        cursor: isConnected ? 'default' : 'pointer',
                        opacity: isConnected ? 1 : undefined,
                    }}
                >
                    {isConnected ? (
                        `${integrationType} Connected`
                    ) : isConnecting ? (
                        <CircularProgress size={20} />
                    ) : (
                        `Connect to ${integrationType}`
                    )}
                </Button>
            </Box>
        </Box>
    );
};
