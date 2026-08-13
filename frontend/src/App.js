import { useMemo, useState } from 'react';
import { Box, CssBaseline, ThemeProvider } from '@mui/material';

import { AppHeader } from './components/AppHeader';
import { IntegrationForm } from './integration-form';
import { buildTheme } from './theme';

function App() {
    const [mode, setMode] = useState('light');
    const theme = useMemo(() => buildTheme(mode), [mode]);
    const toggleMode = () => setMode((m) => (m === 'light' ? 'dark' : 'light'));

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
                <AppHeader mode={mode} onToggleMode={toggleMode} />
                <IntegrationForm />
            </Box>
        </ThemeProvider>
    );
}

export default App;
