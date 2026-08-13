import { useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    InputAdornment,
    Link,
    Paper,
    Skeleton,
    Snackbar,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Typography,
} from '@mui/material';
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded';
import FolderRoundedIcon from '@mui/icons-material/FolderRounded';
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded';
import SearchRoundedIcon from '@mui/icons-material/SearchRounded';
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
    const [query, setQuery] = useState('');
    const [notice, setNotice] = useState(null); // { message, severity }
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
            setNotice({
                message: `Loaded ${items.length} item${items.length === 1 ? '' : 's'}.`,
                severity: 'success',
            });
        } catch (e) {
            setNotice({
                message: e?.response?.data?.detail || 'Failed to load data.',
                severity: 'error',
            });
        } finally {
            setIsLoading(false);
        }
    };

    const handleClear = () => {
        setLoadedData(null);
        setQuery('');
    };

    const filtered = useMemo(() => {
        if (!loadedData) return null;
        const q = query.trim().toLowerCase();
        if (!q) return loadedData;
        return loadedData.filter((item) =>
            [item.name, item.type, item.parent_path_or_name].some((field) =>
                field?.toLowerCase().includes(q)
            )
        );
    }, [loadedData, query]);

    return (
        <Box width="100%">
            {isLoading && (
                <Box sx={{ mb: 2 }}>
                    {[0, 1, 2, 3].map((i) => (
                        <Skeleton key={i} variant="rounded" height={36} sx={{ mb: 1 }} />
                    ))}
                </Box>
            )}

            {!isLoading && loadedData === null && (
                <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
                    No data loaded yet — click "Load Data" to fetch from {integrationType}.
                </Typography>
            )}

            {!isLoading && loadedData !== null && loadedData.length === 0 && (
                <Typography variant="body2" sx={{ mb: 2, color: 'text.secondary' }}>
                    Loaded 0 items. The connected account has no records for the requested
                    object types.
                </Typography>
            )}

            {!isLoading && loadedData !== null && loadedData.length > 0 && (
                <>
                    <Box
                        display="flex"
                        alignItems="center"
                        justifyContent="space-between"
                        flexWrap="wrap"
                        gap={1}
                        sx={{ mb: 1.5 }}
                    >
                        <Typography variant="subtitle1">
                            {filtered.length} of {loadedData.length} item
                            {loadedData.length === 1 ? '' : 's'}
                        </Typography>
                        <TextField
                            size="small"
                            placeholder="Filter by name, type, parent…"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchRoundedIcon fontSize="small" />
                                    </InputAdornment>
                                ),
                            }}
                            sx={{ minWidth: 240 }}
                        />
                    </Box>
                    <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 420 }}>
                        <Table stickyHeader size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Type</TableCell>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Parent</TableCell>
                                    <TableCell>Last Modified</TableCell>
                                    <TableCell align="right">Link</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {filtered.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={5}>
                                            <Typography
                                                variant="body2"
                                                color="text.secondary"
                                                sx={{ py: 2, textAlign: 'center' }}
                                            >
                                                No items match "{query}".
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    filtered.map((item, index) => (
                                        <TableRow key={item.id ?? index} hover>
                                            <TableCell>
                                                <Chip
                                                    icon={
                                                        item.directory ? (
                                                            <FolderRoundedIcon />
                                                        ) : (
                                                            <DescriptionRoundedIcon />
                                                        )
                                                    }
                                                    label={item.type || 'Unknown'}
                                                    size="small"
                                                    color={item.directory ? 'primary' : 'default'}
                                                    variant={item.directory ? 'filled' : 'outlined'}
                                                />
                                            </TableCell>
                                            <TableCell>{item.name || '—'}</TableCell>
                                            <TableCell>{item.parent_path_or_name || '—'}</TableCell>
                                            <TableCell>{formatDate(item.last_modified_time)}</TableCell>
                                            <TableCell align="right">
                                                {item.url ? (
                                                    <Link
                                                        href={item.url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        sx={{
                                                            display: 'inline-flex',
                                                            alignItems: 'center',
                                                            gap: 0.5,
                                                        }}
                                                    >
                                                        Open
                                                        <OpenInNewRoundedIcon sx={{ fontSize: 14 }} />
                                                    </Link>
                                                ) : (
                                                    '—'
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </>
            )}

            <Box display="flex" gap={1} sx={{ mt: 3 }}>
                <Button onClick={handleLoad} variant="contained" disabled={isLoading}>
                    {isLoading ? <CircularProgress size={20} color="inherit" /> : 'Load Data'}
                </Button>
                <Button onClick={handleClear} variant="outlined" disabled={!loadedData}>
                    Clear Data
                </Button>
            </Box>

            <Snackbar
                open={Boolean(notice)}
                autoHideDuration={4000}
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
