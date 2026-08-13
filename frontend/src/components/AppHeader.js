import { AppBar, Box, Toolbar, Tooltip, Switch, Typography } from '@mui/material';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';

import pipelineLogo from '../assets/logos/pipeline.svg';

export const AppHeader = ({ mode, onToggleMode }) => (
    <AppBar
        position="static"
        elevation={0}
        color="transparent"
        sx={{ borderBottom: '1px solid', borderColor: 'divider' }}
    >
        <Toolbar sx={{ maxWidth: 900, mx: 'auto', width: '100%', px: { xs: 1, sm: 2 } }}>
            <Box
                component="img"
                src={pipelineLogo}
                alt="Pipeline AI"
                sx={{ width: 36, height: 36, borderRadius: '10px', mr: 1.5, flexShrink: 0 }}
            />
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                <Typography variant="h6" noWrap sx={{ lineHeight: 1.15 }}>
                    Pipeline AI
                </Typography>
                <Typography variant="caption" color="text.secondary">
                    Integrations Console
                </Typography>
            </Box>
            <Tooltip title={mode === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}>
                <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                    <LightModeRoundedIcon
                        fontSize="small"
                        color={mode === 'light' ? 'warning' : 'disabled'}
                    />
                    <Switch
                        checked={mode === 'dark'}
                        onChange={onToggleMode}
                        size="small"
                        inputProps={{ 'aria-label': 'Toggle dark mode' }}
                    />
                    <DarkModeRoundedIcon
                        fontSize="small"
                        color={mode === 'dark' ? 'primary' : 'disabled'}
                    />
                </Box>
            </Tooltip>
        </Toolbar>
    </AppBar>
);
