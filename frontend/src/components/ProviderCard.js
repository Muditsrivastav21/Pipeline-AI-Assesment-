import { Box, Card, CardActionArea, Typography } from '@mui/material';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';

import { PROVIDER_META } from '../integrations/provider-meta';

export const ProviderCard = ({ name, selected, onSelect }) => {
    const meta = PROVIDER_META[name] || { color: '#666', monogram: name?.[0] || '?', description: '' };

    return (
        <Card
            variant="outlined"
            sx={{
                position: 'relative',
                height: '100%',
                borderColor: selected ? meta.color : 'divider',
                borderWidth: selected ? 2 : 1,
                transition: 'transform .15s ease, box-shadow .15s ease',
                '&:hover': { transform: 'translateY(-2px)', boxShadow: 3 },
            }}
        >
            <CardActionArea onClick={() => onSelect(name)} sx={{ p: 2, height: '100%' }}>
                {selected && (
                    <CheckCircleRoundedIcon
                        fontSize="small"
                        sx={{ position: 'absolute', top: 10, right: 10, color: meta.color }}
                    />
                )}
                <Box
                    sx={{
                        width: 40,
                        height: 40,
                        borderRadius: '10px',
                        mb: 1.5,
                        bgcolor: meta.color,
                        color: '#fff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                        fontSize: 16,
                    }}
                >
                    {meta.monogram}
                </Box>
                <Typography variant="subtitle1">{name}</Typography>
                <Typography variant="body2" color="text.secondary">
                    {meta.description}
                </Typography>
            </CardActionArea>
        </Card>
    );
};
