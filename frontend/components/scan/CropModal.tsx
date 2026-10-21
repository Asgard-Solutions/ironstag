import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Image, Modal, PanResponder, StyleSheet, Text, TouchableOpacity, View, LayoutChangeEvent } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { CropRect, MIN_CROP_FRACTION, ScanPhoto } from '../../utils/scanPhotos';

type Handle = 'move' | 'tl' | 'tr' | 'bl' | 'br';
const FULL: CropRect = { x: 0, y: 0, width: 1, height: 1 };
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function applyDrag(start: CropRect, handle: Handle, dx: number, dy: number): CropRect {
  let { x, y, width, height } = start;
  if (handle === 'move') {
    return { x: clamp(x + dx, 0, 1 - width), y: clamp(y + dy, 0, 1 - height), width, height };
  }
  const right = x + width;
  const bottom = y + height;
  if (handle === 'tl' || handle === 'bl') x = clamp(x + dx, 0, right - MIN_CROP_FRACTION);
  if (handle === 'tl' || handle === 'tr') y = clamp(y + dy, 0, bottom - MIN_CROP_FRACTION);
  const newRight = handle === 'tr' || handle === 'br' ? clamp(right + dx, x + MIN_CROP_FRACTION, 1) : right;
  const newBottom = handle === 'bl' || handle === 'br' ? clamp(bottom + dy, y + MIN_CROP_FRACTION, 1) : bottom;
  return { x, y, width: newRight - x, height: newBottom - y };
}

type Props = {
  photo: ScanPhoto | null;
  onCancel: () => void;
  onApply: (crop: CropRect | null) => void;
};

export function CropModal({ photo, onCancel, onApply }: Props) {
  const insets = useSafeAreaInsets();
  const [box, setBox] = useState({ width: 0, height: 0 });
  const [rect, setRect] = useState<CropRect>(FULL);
  const rectRef = useRef(rect);
  const startRef = useRef(rect);
  const displayRef = useRef({ width: 1, height: 1 });

  useEffect(() => {
    const initial = photo?.crop || FULL;
    setRect(initial);
    rectRef.current = initial;
  }, [photo]);

  // Fit the photo inside the available area (contain)
  const display = useMemo(() => {
    if (!photo || !box.width || !box.height) return { width: 0, height: 0 };
    const scale = Math.min(box.width / photo.width, box.height / photo.height);
    return { width: photo.width * scale, height: photo.height * scale };
  }, [photo, box]);
  displayRef.current = { width: display.width || 1, height: display.height || 1 };

  const responders = useMemo(() => {
    const make = (handle: Handle) =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderTerminationRequest: () => false,
        onPanResponderGrant: () => {
          startRef.current = rectRef.current;
        },
        onPanResponderMove: (_e, g) => {
          const next = applyDrag(
            startRef.current,
            handle,
            g.dx / displayRef.current.width,
            g.dy / displayRef.current.height,
          );
          rectRef.current = next;
          setRect(next);
        },
      });
    return { move: make('move'), tl: make('tl'), tr: make('tr'), bl: make('bl'), br: make('br') };
  }, []);

  const onLayout = (e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setBox({ width, height });
  };

  const apply = () => {
    const isFull = rect.width >= 0.999 && rect.height >= 0.999;
    onApply(isFull ? null : {
      x: Number(rect.x.toFixed(4)),
      y: Number(rect.y.toFixed(4)),
      width: Number(rect.width.toFixed(4)),
      height: Number(rect.height.toFixed(4)),
    });
  };

  const frame = {
    left: rect.x * display.width,
    top: rect.y * display.height,
    width: rect.width * display.width,
    height: rect.height * display.height,
  };

  return (
    <Modal visible={!!photo} animationType="slide" onRequestClose={onCancel} testID="crop-modal">
      <View style={[styles.container, { paddingTop: insets.top + spacing.sm, paddingBottom: insets.bottom + spacing.md }]}>
        <Text style={styles.title}>Adjust crop</Text>
        <Text style={styles.hint}>
          Keep the deer&apos;s full body, head, and legs inside the frame. Your original photo is kept.
        </Text>
        <View style={styles.stage} onLayout={onLayout}>
          {photo && display.width > 0 && (
            <View style={{ width: display.width, height: display.height }}>
              <Image source={{ uri: photo.uri }} style={{ width: display.width, height: display.height }} pointerEvents="none" />
              {/* Dim outside the crop */}
              <View style={[styles.dim, { left: 0, top: 0, right: 0, height: frame.top }]} />
              <View style={[styles.dim, { left: 0, top: frame.top + frame.height, right: 0, bottom: 0 }]} />
              <View style={[styles.dim, { left: 0, top: frame.top, width: frame.left, height: frame.height }]} />
              <View style={[styles.dim, { left: frame.left + frame.width, top: frame.top, right: 0, height: frame.height }]} />
              <View style={[styles.frame, frame]} {...responders.move.panHandlers} testID="crop-frame">
                {(['tl', 'tr', 'bl', 'br'] as const).map((h) => (
                  <View
                    key={h}
                    testID={`crop-handle-${h}`}
                    style={[styles.handle, h.includes('t') ? { top: -14 } : { bottom: -14 }, h.includes('l') ? { left: -14 } : { right: -14 }]}
                    {...responders[h].panHandlers}
                  >
                    <View style={styles.handleDot} />
                  </View>
                ))}
              </View>
            </View>
          )}
        </View>
        <View style={styles.actions}>
          <TouchableOpacity style={styles.secondary} onPress={onCancel} testID="crop-cancel">
            <Text style={styles.secondaryText}>Cancel</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondary} onPress={() => { setRect(FULL); rectRef.current = FULL; }} testID="crop-reset">
            <Text style={styles.secondaryText}>Reset</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.primary} onPress={apply} testID="crop-apply">
            <Text style={styles.primaryText}>Apply</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingHorizontal: spacing.md },
  title: { color: colors.textPrimary, fontSize: 18, fontWeight: '700', textAlign: 'center' },
  hint: { color: colors.textSecondary, fontSize: 13, textAlign: 'center', marginTop: spacing.xs, marginBottom: spacing.md },
  stage: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  dim: { position: 'absolute', backgroundColor: 'rgba(0,0,0,0.55)' },
  frame: { position: 'absolute', borderWidth: 2, borderColor: colors.primary },
  handle: { position: 'absolute', width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
  handleDot: { width: 16, height: 16, borderRadius: 8, backgroundColor: colors.primary, borderWidth: 2, borderColor: colors.background },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  secondary: { flex: 1, minHeight: 48, borderRadius: borderRadius.md, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
  secondaryText: { color: colors.textPrimary, fontWeight: '600' },
  primary: { flex: 1, minHeight: 48, borderRadius: borderRadius.md, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  primaryText: { color: colors.textOnPrimary, fontWeight: '700' },
});
