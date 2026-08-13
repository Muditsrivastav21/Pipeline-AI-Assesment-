import { createTheme } from '@mui/material/styles';

const FONT_STACK = [
    '-apple-system',
    'BlinkMacSystemFont',
    '"Segoe UI"',
    'Roboto',
    '"Helvetica Neue"',
    'Arial',
    'sans-serif',
].join(',');

/**
 * Single brand accent (indigo -> teal) used across both palettes so the app
 * reads as one product whether the visitor is in light or dark mode.
 */
export const buildTheme = (mode = 'light') =>
    createTheme({
        palette: {
            mode,
            primary: { main: '#6C5CE7' },
            secondary: { main: '#00B8A9' },
            success: { main: '#2FBF71' },
            ...(mode === 'light'
                ? {
                      background: { default: '#F5F6FB', paper: '#FFFFFF' },
                  }
                : {
                      background: { default: '#101218', paper: '#181B23' },
                  }),
        },
        shape: { borderRadius: 12 },
        typography: {
            fontFamily: FONT_STACK,
            h6: { fontWeight: 700 },
            subtitle1: { fontWeight: 600 },
        },
        components: {
            MuiPaper: {
                styleOverrides: { root: { backgroundImage: 'none' } },
            },
            MuiButton: {
                styleOverrides: {
                    root: { textTransform: 'none', fontWeight: 600, borderRadius: 10 },
                },
            },
            MuiChip: {
                styleOverrides: { root: { fontWeight: 600 } },
            },
            MuiTextField: {
                defaultProps: { size: 'small' },
            },
        },
    });
