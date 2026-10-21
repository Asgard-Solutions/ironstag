import React from 'react';
import { Image, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { AlertTriangle, Images } from 'lucide-react-native';
import { colors, spacing, borderRadius } from '../../constants/theme';

export type ScanImageRecord = {
  image_id: string;
  position: number;
  url?: string | null;
  original_url?: string | null;
  crop_url?: string | null;
  crop_rect?: { x: number; y: number; width: number; height: number } | null;
  is_cropped?: boolean;
  width?: number | null;
  height?: number | null;
  captured_at?: string | null;
  local_image_id?: string | null;
  duplicate_of?: string | null;
};

export type MultiImageSummary = {
  photo_count: number;
  evidence_count: number;
  duplicates_removed?: { image_id: string; duplicate_of: string; kind: string }[];
  per_image_observations?: { image_id: string; usable: boolean; view: string; observations?: string | null }[];
  same_deer?: { verdict: string; reason?: string | null; conflicting_image_ids?: string[] };
  contradictions?: string[];
  warnings?: string[];
};

const photoLabel = (id: string) => `Photo ${id.split('_')[1] ?? id}`;

export function ScanPhotoStrip({
  uris,
  selected,
  onSelect,
}: {
  uris: (string | null)[];
  selected: number;
  onSelect: (index: number) => void;
}) {
  if (uris.length < 2) return null;
  return (
    <View style={styles.strip} testID="result-photo-strip">
      {uris.map((uri, index) => (
        <TouchableOpacity
          key={index}
          onPress={() => onSelect(index)}
          style={[styles.thumbWrap, index === selected && styles.thumbSelected]}
          testID={`result-photo-${index + 1}`}
          accessibilityLabel={`Show photo ${index + 1}`}
        >
          {uri ? <Image source={{ uri }} style={styles.thumb} /> : <View style={styles.thumbEmpty} />}
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{index + 1}</Text>
          </View>
        </TouchableOpacity>
      ))}
    </View>
  );
}

export function MultiPhotoEvidence({ summary }: { summary?: MultiImageSummary | null }) {
  if (!summary || summary.photo_count < 2) return null;
  const duplicates = summary.duplicates_removed || [];
  const contradictions = summary.contradictions || [];
  const warnings = summary.warnings || [];
  const verdict = summary.same_deer?.verdict;
  const flagged = contradictions.length > 0 || warnings.length > 0 || verdict === 'uncertain';

  return (
    <View style={styles.card} testID="multi-photo-evidence">
      <View style={styles.header}>
        <Images size={16} color={colors.primary} />
        <Text style={styles.title}>
          {summary.photo_count} photos analyzed together
          {summary.evidence_count !== summary.photo_count ? ` (${summary.evidence_count} independent)` : ''}
        </Text>
      </View>
      <Text style={styles.note}>
        Extra photos add visual evidence but never raise confidence on their own.
      </Text>
      {duplicates.map((d) => (
        <Text key={d.image_id} style={styles.item}>
          • {photoLabel(d.image_id)} matches {photoLabel(d.duplicate_of)}, so it wasn&apos;t counted as extra evidence.
        </Text>
      ))}
      {(summary.per_image_observations || []).map((o) => (
        <Text key={o.image_id} style={styles.item}>
          • {photoLabel(o.image_id)} ({o.view}{o.usable ? '' : ', limited use'}){o.observations ? `: ${o.observations}` : ''}
        </Text>
      ))}
      {flagged && (
        <View style={styles.warnBox}>
          <View style={styles.header}>
            <AlertTriangle size={14} color={colors.warning} />
            <Text style={styles.warnTitle}>
              {verdict === 'uncertain' ? 'Could not confirm these photos show the same deer' : 'Conflicting evidence'}
            </Text>
          </View>
          {[...contradictions, ...warnings].map((c, i) => (
            <Text key={i} style={styles.warnItem}>• {c}</Text>
          ))}
          <Text style={styles.warnItem}>Confidence was lowered to reflect this.</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  strip: { flexDirection: 'row', gap: spacing.sm, paddingHorizontal: spacing.md, marginTop: spacing.sm },
  thumbWrap: {
    width: 64, height: 64, borderRadius: borderRadius.sm, overflow: 'hidden',
    borderWidth: 2, borderColor: 'transparent', backgroundColor: colors.surface,
  },
  thumbSelected: { borderColor: colors.primary },
  thumb: { width: '100%', height: '100%' },
  thumbEmpty: { flex: 1, backgroundColor: colors.surfaceElevated },
  badge: {
    position: 'absolute', left: 3, top: 3, minWidth: 16, height: 16, borderRadius: 8,
    backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center',
  },
  badgeText: { color: colors.textOnPrimary, fontSize: 10, fontWeight: '700' },
  card: {
    marginHorizontal: spacing.md, marginTop: spacing.md, padding: spacing.md,
    borderRadius: borderRadius.md, backgroundColor: colors.backgroundCard, gap: 6,
  },
  header: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  title: { color: colors.textPrimary, fontWeight: '700', fontSize: 14, flexShrink: 1 },
  note: { color: colors.textMuted, fontSize: 12 },
  item: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  warnBox: { marginTop: 4, padding: spacing.sm, borderRadius: borderRadius.sm, backgroundColor: colors.warningBg, gap: 4 },
  warnTitle: { color: colors.warning, fontWeight: '700', fontSize: 13, flexShrink: 1 },
  warnItem: { color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
});
