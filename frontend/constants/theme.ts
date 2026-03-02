// ═══════════════════════════════════════════════════════════════════════════
// IRON STAG DESIGN SYSTEM - NORDIC PRECISION AI PLATFORM
// ═══════════════════════════════════════════════════════════════════════════
// Brand Position: Forged precision decision instrument for ethical hunters
// Visual Tone: Slate-dominant, structured, metallic, professional, premium
// NOT: Olive, warm green, orange CTA, rustic hunting aesthetic
// ═══════════════════════════════════════════════════════════════════════════

export const colors = {
  // ═══════════════════════════════════════════════════════════════════════════
  // 1️⃣ PRIMARY BACKGROUND - Obsidian Slate (GLOBAL DEFAULT)
  // Use for: App background, screen base, navigation bar, modals
  // NO green full-screen backgrounds
  // ═══════════════════════════════════════════════════════════════════════════
  background: '#0F1418',              // Obsidian Slate - PRIMARY
  backgroundGradientTop: '#151B20',   // Subtle gradient top (optional)
  backgroundGradientBottom: '#0B0F12', // Subtle gradient bottom (optional)
  
  // ═══════════════════════════════════════════════════════════════════════════
  // 2️⃣ PRIMARY SURFACE / CARDS - Cold Steel
  // Use for: Cards, panels, containers, history tiles, analysis sections
  // Cards should visually float using soft shadow
  // ═══════════════════════════════════════════════════════════════════════════
  backgroundCard: '#1A2329',          // Cold Steel - Cards and elevated surfaces
  surface: '#1A2329',                 // Cold Steel - Panels and containers
  surfaceElevated: '#212A31',         // Slightly lighter for hover/pressed states
  surfaceSecondary: '#151B20',        // Darker surface variant
  
  // ═══════════════════════════════════════════════════════════════════════════
  // 3️⃣ IDENTITY ACCENT - Brushed Brass (PRIMARY CTA COLOR)
  // Use for: Primary buttons, key icons, premium badge, selected nav, major CTAs
  // Replaces green as main action color
  // Tone: Metallic and refined, NOT bright yellow or warm gold
  // ═══════════════════════════════════════════════════════════════════════════
  primary: '#B8954A',                 // Brushed Brass - PRIMARY CTA
  primaryDark: '#9A7B3D',             // Darker brass for pressed states
  primaryLight: '#CDAA5E',            // Lighter brass for highlights
  primaryMuted: 'rgba(184, 149, 74, 0.15)', // Subtle brass background
  textOnPrimary: '#0F1418',           // Slate text on brass buttons
  
  // ═══════════════════════════════════════════════════════════════════════════
  // 4️⃣ LIMITED IDENTITY GREEN - Dark Pine (CONTROLLED USE ONLY)
  // Use ONLY for: HARVEST badge, ethical confirmation, positive outcomes
  // Green must NOT dominate screens
  // ═══════════════════════════════════════════════════════════════════════════
  harvest: '#5FBF6D',                 // Harvest text color (brighter for readability)
  harvestBg: '#10251E',               // Dark Pine - HARVEST badge background ONLY
  harvestBorder: '#1D4A35',           // Subtle green border for harvest states
  
  // ═══════════════════════════════════════════════════════════════════════════
  // 5️⃣ PRECISION INDICATOR - Nordic Ice Blue (MINIMAL USE)
  // Use sparingly for: Confidence %, AI indicators, scan progress, analytics
  // ═══════════════════════════════════════════════════════════════════════════
  precision: '#4DA3C7',               // Nordic Ice Blue
  precisionDark: '#3D8AA8',           // Darker ice blue
  precisionLight: '#6BB8D6',          // Lighter ice blue
  precisionMuted: 'rgba(77, 163, 199, 0.15)', // Subtle ice blue background
  
  // Aliases for precision accent
  confidence: '#4DA3C7',              // Confidence percentage
  aiIndicator: '#4DA3C7',             // AI processing indicators
  scanProgress: '#4DA3C7',            // Scan progress bars
  analytics: '#4DA3C7',               // Analytics highlights
  
  // ═══════════════════════════════════════════════════════════════════════════
  // TEXT HIERARCHY
  // ═══════════════════════════════════════════════════════════════════════════
  textPrimary: '#FFFFFF',             // Primary text - bright white
  textSecondary: '#A8B4B0',           // Secondary text - cool gray with slight warmth
  textMuted: '#6B7D78',               // Muted text - slate gray
  textOnSurface: '#E8ECEB',           // Text on Cold Steel surfaces
  white: '#FFFFFF',
  
  // ═══════════════════════════════════════════════════════════════════════════
  // STATUS COLORS
  // ═══════════════════════════════════════════════════════════════════════════
  // PASS - Brass-tinted warning (NOT orange)
  pass: '#D4A852',                    // Brass-amber for PASS recommendation
  passBg: '#1A2329',                  // Cold Steel background
  passBorder: '#B8954A',              // Brass border for warning emphasis
  
  // SUCCESS - Limited green (harvest contexts only)
  success: '#5FBF6D',
  successBg: 'rgba(95, 191, 109, 0.12)',
  
  // ERROR
  error: '#E85454',
  errorBg: 'rgba(232, 84, 84, 0.12)',
  
  // WARNING - Brass-tinted (NOT orange)
  warning: '#D4A852',
  warningBg: 'rgba(212, 168, 82, 0.12)',
  
  // INFO - Ice Blue
  info: '#4DA3C7',
  infoBg: 'rgba(77, 163, 199, 0.12)',
  
  // ═══════════════════════════════════════════════════════════════════════════
  // BORDERS & DIVIDERS
  // ═══════════════════════════════════════════════════════════════════════════
  border: '#2A353D',                  // Subtle border on slate
  borderLight: '#354250',             // Lighter border
  borderBrass: 'rgba(184, 149, 74, 0.4)', // Brass accent border
  divider: '#1E2930',                 // Divider lines
  
  // ═══════════════════════════════════════════════════════════════════════════
  // NAVIGATION BAR
  // Background → Obsidian Slate, Active → Brass, Inactive → Muted gray
  // NO green navigation highlights
  // ═══════════════════════════════════════════════════════════════════════════
  navBackground: '#0F1418',           // Obsidian Slate
  navActive: '#B8954A',               // Brushed Brass for active state
  navInactive: '#6B7D78',             // Muted gray for inactive
  
  // ═══════════════════════════════════════════════════════════════════════════
  // SPECIAL ELEMENTS
  // ═══════════════════════════════════════════════════════════════════════════
  premiumBadge: '#B8954A',            // Brushed Brass
  premiumBadgeBg: 'rgba(184, 149, 74, 0.2)',
  
  // Input fields
  inputBackground: '#1A2329',         // Cold Steel
  inputBorder: '#2A353D',
  inputFocus: '#B8954A',              // Brass focus ring
  
  // Overlay
  overlay: 'rgba(15, 20, 24, 0.85)',  // Dark slate overlay
  modalBackground: '#1A2329',         // Cold Steel for modals
  
  // ═══════════════════════════════════════════════════════════════════════════
  // LEGACY COMPATIBILITY (mapped to new system)
  // ═══════════════════════════════════════════════════════════════════════════
  backgroundLight: '#1A2329',         // Now maps to Cold Steel
  confidenceIndicator: '#4DA3C7',     // Ice Blue
};

// ═══════════════════════════════════════════════════════════════════════════
// ELEVATION & DEPTH SYSTEM
// Design must feel layered and engineered
// ═══════════════════════════════════════════════════════════════════════════
export const shadows = {
  // Card Shadow - Black at 20-30%, medium blur, subtle lift
  card: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 4,
  },
  // Elevated card (hover/focus state)
  cardElevated: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.30,
    shadowRadius: 12,
    elevation: 6,
  },
  // Button - Slight top highlight, soft drop shadow
  button: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.20,
    shadowRadius: 4,
    elevation: 2,
  },
  // Primary button (brass) - Enhanced depth
  buttonPrimary: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
  },
  // Modal shadow
  modal: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.40,
    shadowRadius: 16,
    elevation: 8,
  },
  // Subtle inner highlight for buttons
  innerHighlight: {
    shadowColor: 'rgba(255, 255, 255, 0.1)',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 1,
    shadowRadius: 0,
    elevation: 0,
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
