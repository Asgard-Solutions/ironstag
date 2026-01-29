import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated, ViewStyle } from 'react-native';
import { colors, spacing, borderRadius } from '../constants/theme';

interface SkeletonProps {
  width?: number | string;
  height?: number;
  borderRadius?: number;
  style?: ViewStyle;
}

/**
 * Animated skeleton placeholder for loading states.
 * Provides better perceived performance than spinners.
 */
export function Skeleton({ 
  width = '100%', 
  height = 20, 
  borderRadius: radius = borderRadius.md,
  style 
}: SkeletonProps) {
  const animatedValue = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(animatedValue, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(animatedValue, {
          toValue: 0,
          duration: 1000,
          useNativeDriver: true,
        }),
      ])
    );
    animation.start();
    return () => animation.stop();
  }, [animatedValue]);

  const opacity = animatedValue.interpolate({
    inputRange: [0, 1],
    outputRange: [0.3, 0.7],
  });

  return (
    <Animated.View
      style={[
        styles.skeleton,
        {
          width,
          height,
          borderRadius: radius,
          opacity,
        },
        style,
      ]}
    />
  );
}

/**
 * Skeleton loader for scan cards in the History tab.
 */
export function ScanCardSkeleton() {
  return (
    <View style={styles.scanCard}>
      <View style={styles.scanRow}>
        {/* Image placeholder */}
        <Skeleton width={60} height={60} borderRadius={borderRadius.md} />
        
        {/* Info section */}
        <View style={styles.scanInfo}>
          <Skeleton width={70} height={18} style={styles.mb4} />
          <Skeleton width={100} height={20} style={styles.mb4} />
          <Skeleton width={80} height={14} style={styles.mb4} />
          <Skeleton width={90} height={12} />
        </View>
        
        {/* Confidence section */}
        <View style={styles.confidenceSection}>
          <Skeleton width={50} height={28} style={styles.mb4} />
          <Skeleton width={70} height={10} />
        </View>
      </View>
    </View>
  );
}

/**
 * Multiple scan card skeletons for list loading.
 */
export function ScanListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <View style={styles.listContainer}>
      {Array.from({ length: count }).map((_, index) => (
        <ScanCardSkeleton key={index} />
      ))}
    </View>
  );
}

/**
 * Skeleton loader for scan result detail page.
 */
export function ScanResultSkeleton() {
  return (
    <View style={styles.resultContainer}>
      {/* Image placeholder */}
      <Skeleton width="100%" height={250} borderRadius={borderRadius.lg} style={styles.mb16} />
      
      {/* Summary card */}
      <View style={styles.summaryCard}>
        <View style={styles.summaryRow}>
          <View style={styles.summaryLeft}>
            <Skeleton width={80} height={14} style={styles.mb8} />
            <Skeleton width={120} height={32} style={styles.mb4} />
            <Skeleton width={100} height={14} />
          </View>
          <View style={styles.summaryRight}>
            <Skeleton width={60} height={48} borderRadius={borderRadius.lg} />
          </View>
        </View>
      </View>
      
      {/* Details section */}
      <View style={styles.detailsCard}>
        <Skeleton width={100} height={18} style={styles.mb12} />
        <View style={styles.detailRow}>
          <Skeleton width="45%" height={40} borderRadius={borderRadius.md} />
          <Skeleton width="45%" height={40} borderRadius={borderRadius.md} />
        </View>
        <View style={[styles.detailRow, styles.mt8]}>
          <Skeleton width="45%" height={40} borderRadius={borderRadius.md} />
          <Skeleton width="45%" height={40} borderRadius={borderRadius.md} />
        </View>
      </View>
      
      {/* Reasoning section */}
      <View style={styles.detailsCard}>
        <Skeleton width={80} height={18} style={styles.mb12} />
        <Skeleton width="100%" height={16} style={styles.mb8} />
        <Skeleton width="90%" height={16} style={styles.mb8} />
        <Skeleton width="95%" height={16} />
      </View>
    </View>
  );
}

/**
 * Skeleton loader for profile page stats.
 */
export function ProfileStatsSkeleton() {
  return (
    <View style={styles.statsContainer}>
      <View style={styles.statItem}>
        <Skeleton width={40} height={32} style={styles.mb4} />
        <Skeleton width={60} height={12} />
      </View>
      <View style={styles.statItem}>
        <Skeleton width={40} height={32} style={styles.mb4} />
        <Skeleton width={60} height={12} />
      </View>
      <View style={styles.statItem}>
        <Skeleton width={40} height={32} style={styles.mb4} />
        <Skeleton width={60} height={12} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  skeleton: {
    backgroundColor: colors.border,
  },
  
  // Scan card skeleton
  scanCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  scanRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  scanInfo: {
    flex: 1,
  },
  confidenceSection: {
    alignItems: 'flex-end',
  },
  listContainer: {
    paddingHorizontal: spacing.md,
  },
  
  // Scan result skeleton
  resultContainer: {
    padding: spacing.md,
  },
  summaryCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  summaryLeft: {
    flex: 1,
  },
  summaryRight: {
    alignItems: 'flex-end',
  },
  detailsCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  
  // Profile stats skeleton
  statsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: spacing.md,
  },
  statItem: {
    alignItems: 'center',
  },
  
  // Spacing helpers
  mb4: { marginBottom: 4 },
  mb8: { marginBottom: 8 },
  mb12: { marginBottom: 12 },
  mb16: { marginBottom: 16 },
  mt8: { marginTop: 8 },
});

export default Skeleton;
