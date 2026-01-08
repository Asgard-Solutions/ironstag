// Iron Stag Theme - Nordic/Hunting Aesthetic
export const colors = {
  // Core palette
  background: '#0E1A14',
  backgroundLight: '#142119',
  backgroundCard: '#1A2B22',
  
  // Primary (Gold/Bronze)
  primary: '#C8A24A',
  primaryDark: '#A68836',
  primaryLight: '#D4B85C',
  
  // Text
  textPrimary: '#FFFFFF',
  textSecondary: '#A0A0A0',
  textMuted: '#6B6B6B',
  
  // Status colors
  harvest: '#4CAF50',
  harvestBg: 'rgba(76, 175, 80, 0.15)',
  pass: '#FF9800',
  passBg: 'rgba(255, 152, 0, 0.15)',
  
  // Functional
  error: '#FF5252',
  success: '#4CAF50',
  warning: '#FFC107',
  info: '#2196F3',
  
  // Borders
  border: '#2A3F32',
  borderLight: '#3A5042',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const borderRadius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const typography = {
  h1: {
    fontSize: 32,
    fontWeight: '700' as const,
    lineHeight: 40,
  },
  h2: {
    fontSize: 24,
    fontWeight: '600' as const,
    lineHeight: 32,
  },
  h3: {
    fontSize: 20,
    fontWeight: '600' as const,
    lineHeight: 28,
  },
  body: {
    fontSize: 16,
    fontWeight: '400' as const,
    lineHeight: 24,
  },
  bodySmall: {
    fontSize: 14,
    fontWeight: '400' as const,
    lineHeight: 20,
  },
  caption: {
    fontSize: 12,
    fontWeight: '400' as const,
    lineHeight: 16,
  },
};
