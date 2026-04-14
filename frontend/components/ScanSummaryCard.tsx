import React, { forwardRef } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
} from 'react-native';
import { colors, spacing, borderRadius, typography, shadows } from '../constants/theme';

interface ScanSummaryCardProps {
  imageUri: string | null;
  recommendation: string | null;
  deerAge: number | null;
  confidence: number | null;
  deerType: string | null;
  deerSex: string | null;
  antlerPoints: number | null;
  reasoning: string | null;
  /** If true, renders a compact branded card for sharing */
  shareMode?: boolean;
}

// ============ CONFIDENCE HELPERS ============
const UNCERTAIN_AGE_CONFIDENCE_CAP = 60;

function isAgeUncertain(age: number | null | undefined): boolean {
  return age === null || age === undefined || age === 0;
}

function getCalibratedConfidence(rawConfidence: number | null, age: number | null): number {
  const confidence = rawConfidence || 0;
  if (isAgeUncertain(age)) {
    return Math.min(confidence, UNCERTAIN_AGE_CONFIDENCE_CAP);
  }
  return confidence;
}

function getAgeDisplayText(age: number | null): string {
  if (isAgeUncertain(age)) {
    return 'Uncertain';
  }
  return `${age} years`;
}

export function getConfidenceLabel(confidence: number): {
  label: string;
  guidance: string;
  color: string;
} {
  if (confidence >= 80) {
    return {
      label: 'High confidence',
      guidance: 'Strong indicators present in the image',
      color: colors.harvest,
    };
  }
  if (confidence >= 60) {
    return {
      label: 'Moderate confidence',
      guidance: 'Best used with your own field judgment',
      color: colors.primary,
    };
  }
  return {
    label: 'Low confidence',
    guidance: 'Consider additional visual verification',
    color: colors.warning,
  };
}

/**
 * Parse reasoning text into a summary and visible cue bullets.
 * Falls back gracefully if parsing can't identify cues.
 */
export function parseReasoning(reasoning: string | null): {
  summary: string;
  cues: string[];
} {
  if (!reasoning) return { summary: '', cues: [] };

  // Split into sentences
  const sentences = reasoning
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);

  // Take first 1-2 sentences as summary
  const summary = sentences.slice(0, 2).join(' ');

  // Known body cue keywords to look for in the text
  const cueKeywords = [
    'deep chest',
    'heavy neck',
    'thick neck',
    'neck development',
    'blocky frame',
    'blocky body',
    'mature body',
    'body mass',
    'belly sag',
    'sagging belly',
    'pot belly',
    'backline',
    'back line',
    'swayed back',
    'Roman nose',
    'muscular',
    'muscling',
    'shoulder',
    'wide spread',
    'spread',
    'tine length',
    'tine',
    'beam',
    'beam mass',
    'beam length',
    'mass',
    'main beam',
    'brow tines',
    'rack',
    'antler',
    'leg length',
    'short legs',
    'tarsal staining',
    'tarsal gland',
    'rump',
    'chest depth',
    'hindquarters',
    'velvet',
    'dark tarsal',
    'body proportion',
    'waist',
    'narrow waist',
    'neck girth',
    'mature frame',
    'young',
    'juvenile',
    'skeletal',
    'filled out',
  ];

  // Extract matching cues from the reasoning text (case-insensitive)
  const lowerReasoning = reasoning.toLowerCase();
  const foundCues: string[] = [];

  for (const kw of cueKeywords) {
    if (lowerReasoning.includes(kw.toLowerCase()) && foundCues.length < 6) {
      // Capitalize first letter of each word
      const formatted = kw
        .split(' ')
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(' ');
      // Avoid near-duplicates
      const isDuplicate = foundCues.some(
        (existing) =>
          existing.toLowerCase().includes(kw.toLowerCase()) ||
          kw.toLowerCase().includes(existing.toLowerCase())
      );
      if (!isDuplicate) {
        foundCues.push(formatted);
      }
    }
  }

  return { summary, cues: foundCues };
}

/**
 * Reusable Scan Summary Card
 * Used in the Scan Result hero section and for share card rendering.
 */
export const ScanSummaryCard = forwardRef<View, ScanSummaryCardProps>(
  function ScanSummaryCard(
    {
      imageUri,
      recommendation,
      deerAge,
      confidence: rawConfidence,
      deerType,
      deerSex,
      antlerPoints,
      reasoning,
      shareMode = false,
    },
    ref
  ) {
    const displayConfidence = getCalibratedConfidence(rawConfidence, deerAge);
    const ageText = getAgeDisplayText(deerAge);
    const confLabel = getConfidenceLabel(displayConfidence);
    const isHarvest = recommendation === 'HARVEST';

    const recommendationSubtext = isHarvest
      ? 'Based on maturity and visible body indicators'
      : 'Based on age estimate and development indicators';

    if (shareMode) {
      // ─── SHARE CARD MODE ───
      return (
        <View ref={ref} style={shareStyles.container}>
          {/* Deer image */}
          {imageUri && (
            <Image source={{ uri: imageUri }} style={shareStyles.image} resizeMode="cover" />
          )}

          {/* Recommendation hero */}
          <View
            style={[
              shareStyles.recoBanner,
              { backgroundColor: isHarvest ? colors.harvestBg : colors.surface },
            ]}
          >
            <Text style={shareStyles.recoLabel}>RECOMMENDATION</Text>
            <Text
              style={[
                shareStyles.recoValue,
                { color: isHarvest ? colors.harvest : colors.pass },
              ]}
            >
              {recommendation || 'UNKNOWN'}
            </Text>
          </View>

          {/* Stats row */}
          <View style={shareStyles.statsRow}>
            <View style={shareStyles.statItem}>
              <Text style={shareStyles.statLabel}>Estimated Age</Text>
              <Text style={shareStyles.statValue}>{ageText}</Text>
            </View>
            <View style={shareStyles.statDivider} />
            <View style={shareStyles.statItem}>
              <Text style={shareStyles.statLabel}>Confidence</Text>
              <Text style={[shareStyles.statValue, { color: confLabel.color }]}>
                {displayConfidence}%
              </Text>
            </View>
            {antlerPoints !== null && (
              <>
                <View style={shareStyles.statDivider} />
                <View style={shareStyles.statItem}>
                  <Text style={shareStyles.statLabel}>Points</Text>
                  <Text style={shareStyles.statValue}>{antlerPoints}</Text>
                </View>
              </>
            )}
          </View>

          {/* Branding footer */}
          <View style={shareStyles.footer}>
            <Text style={shareStyles.footerText}>Analyzed with Iron Stag</Text>
          </View>
        </View>
      );
    }

    // ─── NORMAL HERO MODE (used on scan result screen) ───
    return (
      <View ref={ref} style={heroStyles.container}>
        {/* Recommendation Hero */}
        <View
          style={[
            heroStyles.recoBanner,
            isHarvest ? heroStyles.harvestBanner : heroStyles.passBanner,
          ]}
        >
          <Text style={heroStyles.recoLabel}>RECOMMENDATION</Text>
          <Text
            style={[
              heroStyles.recoValue,
              { color: isHarvest ? colors.harvest : colors.pass },
            ]}
          >
            {recommendation || 'UNKNOWN'}
          </Text>
          <Text style={heroStyles.recoSubtext}>{recommendationSubtext}</Text>
        </View>
      </View>
    );
  }
);

// ═══════════ HERO STYLES ═══════════
const heroStyles = StyleSheet.create({
  container: {
    marginBottom: spacing.md,
  },
  recoBanner: {
    alignItems: 'center',
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    ...shadows.card,
  },
  harvestBanner: {
    backgroundColor: colors.harvestBg,
    borderColor: colors.harvestBorder,
  },
  passBanner: {
    backgroundColor: colors.surface,
    borderColor: colors.passBorder,
  },
  recoLabel: {
    ...typography.sectionHeader,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  recoValue: {
    fontSize: 36,
    fontWeight: '800',
    letterSpacing: 2,
    marginBottom: spacing.xs,
  },
  recoSubtext: {
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'center',
  },
});

// ═══════════ SHARE CARD STYLES ═══════════
const shareStyles = StyleSheet.create({
  container: {
    width: 380,
    backgroundColor: colors.background,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
  },
  image: {
    width: '100%',
    height: 240,
  },
  recoBanner: {
    alignItems: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  recoLabel: {
    ...typography.sectionHeader,
    color: colors.textMuted,
    marginBottom: 2,
  },
  recoValue: {
    fontSize: 30,
    fontWeight: '800',
    letterSpacing: 2,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
  },
  statItem: {
    alignItems: 'center',
    flex: 1,
  },
  statLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginBottom: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statValue: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  statDivider: {
    width: 1,
    height: 32,
    backgroundColor: colors.border,
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  footerText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
    letterSpacing: 0.5,
  },
});
