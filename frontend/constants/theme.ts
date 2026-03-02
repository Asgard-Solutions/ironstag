// Iron Stag Theme - Nordic Precision AI Field Platform
// Brand Shift: Slate-dominant with controlled green accents

export const colors = {
  // ═══════════════════════════════════════════════════════════════
  // CORE BACKGROUNDS - Obsidian Slate (NEW DOMINANT)
  // ═══════════════════════════════════════════════════════════════
  background: '#0F1418',           // Obsidian Slate - Primary app background
  backgroundGradientTop: '#151B20', // Subtle gradient top (optional)
  backgroundGradientBottom: '#0B0F12', // Subtle gradient bottom (optional)
  
  // ═══════════════════════════════════════════════════════════════
  // SECONDARY SURFACES - Deep Pine (Controlled Green)
  // Use ONLY for: Cards, Result panels, HARVEST badge, Selected states
  // ═══════════════════════════════════════════════════════════════
  backgroundCard: '#0F261D',       // Deep Pine - Cards and elevated surfaces
  surface: '#0F261D',              // Deep Pine - Section blocks
  surfaceElevated: '#132A21',      // Slightly lighter pine for hover states
  
  // Legacy compatibility (maps to new system)
  backgroundLight: '#0F1418',      // Now maps to slate, not green
  
  // ═══════════════════════════════════════════════════════════════
  // PRIMARY ACCENT - Brushed Brass
  // Use for: Primary buttons, Icon accents, Premium badge, Key CTAs
  // ═══════════════════════════════════════════════════════════════
  primary: '#B8954A',              // Brushed Brass - refined, less saturated
  primaryDark: '#96793C',          // Darker brass for pressed states
  primaryLight: '#CDAA5E',         // Lighter brass for highlights
  textOnPrimary: '#0F1418',        // Slate text on brass buttons
  
  // ═══════════════════════════════════════════════════════════════
  // PRECISION ACCENT - Nordic Ice Blue (Minimal Use)
  // Use sparingly for: Confidence %, AI indicators, Scan progress
  // ═══════════════════════════════════════════════════════════════
  precision: '#4DA3C7',            // Nordic Ice Blue
  precisionDark: '#3D8AA8',        // Darker ice blue
  precisionLight: '#6BB8D6',       // Lighter ice blue
  
  // ═══════════════════════════════════════════════════════════════
  // TEXT HIERARCHY
  // ═══════════════════════════════════════════════════════════════
  textPrimary: '#FFFFFF',          // Primary text - bright white
  textSecondary: '#B8C4BD',        // Secondary text - slightly green tint
  textMuted: '#6B7D74',            // Muted text - slate-green
  textOnSurface: '#E8EDE9',        // Text on pine surfaces
  white: '#FFFFFF',
  
  // ═══════════════════════════════════════════════════════════════
  // STATUS COLORS - Refined
  // ═══════════════════════════════════════════════════════════════
  // HARVEST - Uses Deep Pine background
  harvest: '#5FBF6D',              // Slightly brighter green for text
  harvestBg: '#0F261D',            // Deep Pine background
  harvestBorder: '#2D5A3D',        // Subtle green border
  
  // PASS - Brass-tinted warning
  pass: '#D4A852',                 // Brass-tinted amber
  passBg: 'rgba(184, 149, 74, 0.15)', // Subtle brass background
  passBorder: '#96793C',           // Brass border
  
  // ═══════════════════════════════════════════════════════════════
  // FUNCTIONAL COLORS
  // ═══════════════════════════════════════════════════════════════
  error: '#E85454',                // Refined red
  errorBg: 'rgba(232, 84, 84, 0.12)',
  success: '#5FBF6D',              // Refined green
  successBg: 'rgba(95, 191, 109, 0.12)',
  warning: '#D4A852',              // Brass-tinted warning
  warningBg: 'rgba(212, 168, 82, 0.12)',
  info: '#4DA3C7',                 // Nordic Ice Blue
  infoBg: 'rgba(77, 163, 199, 0.12)',
  
  // ═══════════════════════════════════════════════════════════════
  // BORDERS & SHADOWS
  // ═══════════════════════════════════════════════════════════════
  border: '#1E2D26',               // Subtle pine border
  borderLight: '#2A3F32',          // Lighter border
  borderBrass: 'rgba(184, 149, 74, 0.3)', // Brass accent border
  
  // ═══════════════════════════════════════════════════════════════
  // NAVIGATION
  // ═══════════════════════════════════════════════════════════════
  navBackground: '#0F1418',        // Obsidian Slate
  navActive: '#B8954A',            // Brass for active
  navInactive: '#6B7D74',          // Muted gray for inactive
  
  // ═══════════════════════════════════════════════════════════════
  // SPECIAL ELEMENTS
  // ═══════════════════════════════════════════════════════════════
  premiumBadge: '#B8954A',         // Brass
  confidenceIndicator: '#4DA3C7', // Ice Blue
  scanProgress: '#4DA3C7',         // Ice Blue
  aiIndicator: '#4DA3C7',          // Ice Blue
};

// ═══════════════════════════════════════════════════════════════
// SHADOW SYSTEM - Premium Depth
// ═══════════════════════════════════════════════════════════════
export const shadows = {
  card: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 4,
  },
  cardHover: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
  },
  button: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 2,
  },
  modal: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4,
    shadowRadius: 16,
    elevation: 8,
  },
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
    letterSpacing: -0.5,
  },
  h2: {
    fontSize: 24,
    fontWeight: '600' as const,
    lineHeight: 32,
    letterSpacing: -0.3,
  },
  h3: {
    fontSize: 20,
    fontWeight: '600' as const,
    lineHeight: 28,
    letterSpacing: 0,
  },
  sectionHeader: {
    fontSize: 14,
    fontWeight: '600' as const,
    lineHeight: 20,
    letterSpacing: 1.2,
    textTransform: 'uppercase' as const,
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
