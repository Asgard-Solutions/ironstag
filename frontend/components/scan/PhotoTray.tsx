import React from 'react';
import { Image, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { ChevronLeft, ChevronRight, Crop, Plus, X } from 'lucide-react-native';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { MAX_SCAN_PHOTOS, ScanPhoto } from '../../utils/scanPhotos';

type Props = {
  photos: ScanPhoto[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onRemove: (index: number) => void;
  onMove: (index: number, direction: -1 | 1) => void;
  onAdd: () => void;
};

export function PhotoTray({ photos, selectedIndex, onSelect, onRemove, onMove, onAdd }: Props) {
  return (
    <View style={styles.row} testID="photo-tray">
      {photos.map((photo, index) => {
        const selected = index === selectedIndex;
        return (
          <View key={photo.key} style={styles.slot}>
            <TouchableOpacity
              style={[styles.thumbWrap, selected && styles.thumbSelected]}
              onPress={() => onSelect(index)}
              testID={`photo-thumb-${index + 1}`}
              accessibilityLabel={`Photo ${index + 1}`}
            >
              <Image source={{ uri: photo.uri }} style={styles.thumb} />
              <View style={styles.badge}>
                <Text style={styles.badgeText}>{index + 1}</Text>
              </View>
              {photo.crop && (
                <View style={styles.cropBadge}>
                  <Crop size={10} color={colors.textOnPrimary} />
                </View>
              )}
              <TouchableOpacity
                style={styles.remove}
                onPress={() => onRemove(index)}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                testID={`photo-remove-${index + 1}`}
                accessibilityLabel={`Remove photo ${index + 1}`}
              >
                <X size={12} color={colors.textPrimary} />
              </TouchableOpacity>
            </TouchableOpacity>
            {photos.length > 1 && (
              <View style={styles.moveRow}>
                <TouchableOpacity
                  style={[styles.moveBtn, index === 0 && styles.moveDisabled]}
                  disabled={index === 0}
                  onPress={() => onMove(index, -1)}
                  testID={`photo-move-left-${index + 1}`}
                  accessibilityLabel={`Move photo ${index + 1} earlier`}
                >
                  <ChevronLeft size={16} color={colors.textPrimary} />
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.moveBtn, index === photos.length - 1 && styles.moveDisabled]}
                  disabled={index === photos.length - 1}
                  onPress={() => onMove(index, 1)}
                  testID={`photo-move-right-${index + 1}`}
                  accessibilityLabel={`Move photo ${index + 1} later`}
                >
                  <ChevronRight size={16} color={colors.textPrimary} />
                </TouchableOpacity>
              </View>
            )}
          </View>
        );
      })}
      {photos.length < MAX_SCAN_PHOTOS && (
        <View style={styles.slot}>
          <TouchableOpacity style={[styles.thumbWrap, styles.addTile]} onPress={onAdd} testID="photo-add">
            <Plus size={22} color={colors.primary} />
            <Text style={styles.addText}>Add</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const TILE = 72;

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: spacing.sm, justifyContent: 'center' },
  slot: { alignItems: 'center' },
  thumbWrap: {
    width: TILE,
    height: TILE,
    borderRadius: borderRadius.md,
    borderWidth: 2,
    borderColor: 'transparent',
    overflow: 'hidden',
    backgroundColor: colors.surface,
  },
  thumbSelected: { borderColor: colors.primary },
  thumb: { width: '100%', height: '100%' },
  badge: {
    position: 'absolute', left: 4, top: 4, minWidth: 18, height: 18, borderRadius: 9,
    backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center',
  },
  badgeText: { color: colors.textOnPrimary, fontSize: 11, fontWeight: '700' },
  cropBadge: {
    position: 'absolute', left: 4, bottom: 4, width: 18, height: 18, borderRadius: 9,
    backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center',
  },
  remove: {
    position: 'absolute', right: 4, top: 4, width: 22, height: 22, borderRadius: 11,
    backgroundColor: 'rgba(0,0,0,0.65)', alignItems: 'center', justifyContent: 'center',
  },
  moveRow: { flexDirection: 'row', marginTop: 4, gap: 4 },
  moveBtn: {
    width: 34, height: 28, borderRadius: borderRadius.sm, backgroundColor: colors.surface,
    alignItems: 'center', justifyContent: 'center',
  },
  moveDisabled: { opacity: 0.3 },
  addTile: { alignItems: 'center', justifyContent: 'center', borderColor: colors.border, borderStyle: 'dashed' },
  addText: { color: colors.primary, fontSize: 12, marginTop: 2, fontWeight: '600' },
});
