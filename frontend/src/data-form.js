import { useState } from 'react';
import {
    Box,
    Button,
    Chip,
    CircularProgress,
    Link,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
} from '@mui/material';
import axios from 'axios';

import { API_BASE_URL, INTEGRATION_ENDPOINTS } from './config';

const formatDate = (value) => {
    if (!value) return '—';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const endpoint = INTEGRATION_ENDPOINTS[integrationType];

    const handleLoad = async () => {
        try {
            setIsLoading(true);
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials));
            const response = await axios.post(
                `${API_BASE_URL}/integrations/${endpoint}/load`,
                formData
            );
            const items = Array.isArray(response.data) ? response.data : [];
            // Mirror of the backend console output, for easy inspection.
            console.log(`${integrationType} IntegrationItems:`, items);
            setLoadedData(items);
        } catch (e) {
            alert(e?.response?.data?.detail || 'Failed to load data.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Box display="flex" justifyContent="center" alignItems="center" flexDirection="column" width="100%">
            <Box display="flex" flexDirection="column" width="100%">
                {loadedData === null ? (
                    <Typography variant="body2" sx={{ mt: 2, color: 'text.secondary' }}>
                        No data loaded yet.
                    </Typography>
                ) : loadedData.length === 0 ? (
                    <Typography variant="body2" sx={{ mt: 2, color: 'text.secondary' }}>
                        Loaded 0 items. The connected account has no records for the
                        requested object types.
                    </Typography>
                ) : (
                    <>
                        <Typography variant="subtitle1" sx={{ mt: 2 }}>
                            Loaded {loadedData.length} integration items
                        </Typography>
                        <TableContainer component={Paper} sx={{ mt: 1, maxHeight: 420 }}>
                            <Table stickyHeader size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Type</TableCell>
                                        <TableCell>Name</TableCell>
                                        <TableCell>Parent</TableCell>
                                        <TableCell>Last Modified</TableCell>
                                        <TableCell>Link</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {loadedData.map((item, index) => (
                                        <TableRow key={item.id ?? index} hover>
                                            <TableCell>
                                                <Chip
                                                    label={item.type || 'Unknown'}
                                                    size="small"
                                                    color={item.directory ? 'primary' : 'default'}
                                                />
                                            </TableCell>
                                            <TableCell>{item.name || '—'}</TableCell>
                                            <TableCell>{item.parent_path_or_name || '—'}</TableCell>
                                            <TableCell>{formatDate(item.last_modified_time)}</TableCell>
                                            <TableCell>
                                                {item.url ? (
                                                    <Link href={item.url} target="_blank" rel="noreferrer">
                                                        Open
                                                    </Link>
                                                ) : (
                                                    '—'
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </>
                )}
                <Button onClick={handleLoad} sx={{ mt: 2 }} variant="contained" disabled={isLoading}>
                    {isLoading ? <CircularProgress size={20} /> : 'Load Data'}
                </Button>
                <Button onClick={() => setLoadedData(null)} sx={{ mt: 1 }} variant="contained">
                    Clear Data
                </Button>
            </Box>
        </Box>
    );
};
