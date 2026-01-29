import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { WifiOff, CloudOff, RefreshCw, Upload, Check } from 'lucide-react-native';
import { colors, spacing, borderRadius } from '../constants/theme';
import { useOfflineQueue } from '../hooks/useOfflineQueue';

interface OfflineIndicatorProps {
  showSyncButton?: boolean;
  compact?: boolean;
}

/**
 * Component to show offline status and pending queue count
 */
export function OfflineIndicator({ showSyncButton = true, compact = false }: OfflineIndicatorProps) {
  const { 
    isOnline, 
    pendingCount, 
    isSyncing, 
    syncNow,
  } = useOfflineQueue();

  // Don't show anything if online and no pending scans
  if (isOnline && pendingCount === 0) {
    return null;
  }

  const handleSync = async () => {
    if (!isSyncing && isOnline && pendingCount > 0) {
      await syncNow();
    }
  };

  if (compact) {
    // Compact mode - just show a small indicator
    return (
      <View style={styles.compactContainer}>
        {!isOnline && (
          <View style={styles.compactOffline}>
            <WifiOff size={14} color={colors.white} />
          </View>
        )}
        {pendingCount > 0 && (
          <View style={styles.compactPending}>
            <Text style={styles.compactPendingText}>{pendingCount}</Text>
          </View>
        )}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Offline indicator */}
      {!isOnline && (
        <View style={styles.offlineBanner}>
          <WifiOff size={16} color={colors.white} />
          <Text style={styles.offlineText}>You're offline</Text>
        </View>
      )}

      {/* Pending scans indicator */}
      {pendingCount > 0 && (
        <View style={styles.pendingBanner}>
          <View style={styles.pendingInfo}>
            <CloudOff size={16} color={colors.primary} />
            <Text style={styles.pendingText}>
              {pendingCount} scan{pendingCount > 1 ? 's' : ''} waiting to upload
            </Text>
          </View>
          
          {showSyncButton && isOnline && (
            <TouchableOpacity 
              style={styles.syncButton}
              onPress={handleSync}
              disabled={isSyncing}
            >
              {isSyncing ? (
                <ActivityIndicator size="small" color={colors.primary} />
              ) : (
                <>
                  <RefreshCw size={14} color={colors.primary} />
                  <Text style={styles.syncButtonText}>Sync</Text>
                </>
              )}
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Syncing indicator */}
      {isSyncing && (
        <View style={styles.syncingBanner}>
          <ActivityIndicator size="small" color={colors.white} />
          <Text style={styles.syncingText}>Syncing scans...</Text>
        </View>
      )}
    </View>
  );
}

/**
 * Full-width banner for main screens
 */
export function OfflineBanner() {
  const { isOnline, pendingCount, isSyncing, syncNow } = useOfflineQueue();

  if (isOnline && pendingCount === 0) {
    return null;
  }

  return (
    <View style={styles.fullBanner}>
      {!isOnline ? (
        <View style={styles.fullBannerOffline}>
          <WifiOff size={18} color={colors.white} />
          <View style={styles.fullBannerTextContainer}>
            <Text style={styles.fullBannerTitle}>You're offline</Text>
            <Text style={styles.fullBannerSubtitle}>
              Scans will be saved and uploaded when you're back online
            </Text>
          </View>
        </View>
      ) : pendingCount > 0 ? (
        <View style={styles.fullBannerPending}>
          <Upload size={18} color={colors.primary} />
          <View style={styles.fullBannerTextContainer}>
            <Text style={styles.fullBannerTitlePending}>
              {pendingCount} scan{pendingCount > 1 ? 's' : ''} ready to upload
            </Text>
            {isSyncing ? (
              <View style={styles.syncingRow}>
                <ActivityIndicator size="small" color={colors.primary} />
                <Text style={styles.fullBannerSubtitlePending}>Uploading...</Text>
              </View>
            ) : (
              <TouchableOpacity onPress={syncNow}>
                <Text style={styles.fullBannerLink}>Tap to sync now</Text>
              </TouchableOpacity>
            )}
          </View>
          {!isSyncing && (
            <Check size={18} color={colors.harvest} style={styles.readyIcon} />
          )}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  // Compact indicator
  compactContainer: {
    flexDirection: 'row',
    gap: spacing.xs,
  },
  compactOffline: {
    backgroundColor: colors.error || '#ef4444',
    borderRadius: borderRadius.full,
    padding: 4,
  },
  compactPending: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.full,
    minWidth: 20,
    height: 20,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 6,
  },
  compactPendingText: {
    color: colors.white,
    fontSize: 11,
    fontWeight: '700',
  },

  // Standard container
  container: {
    gap: spacing.xs,
  },
  offlineBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.error || '#ef4444',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
  },
  offlineText: {
    color: colors.white,
    fontSize: 13,
    fontWeight: '500',
  },
  pendingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.primary + '15',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  pendingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flex: 1,
  },
  pendingText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '500',
  },
  syncButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    backgroundColor: colors.primary + '20',
    borderRadius: borderRadius.sm,
  },
  syncButtonText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
  },
  syncingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
  },
  syncingText: {
    color: colors.white,
    fontSize: 13,
    fontWeight: '500',
  },

  // Full-width banner
  fullBanner: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  fullBannerOffline: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
    backgroundColor: '#78716c',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.lg,
  },
  fullBannerPending: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
    backgroundColor: colors.primary + '10',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  fullBannerTextContainer: {
    flex: 1,
  },
  fullBannerTitle: {
    color: colors.white,
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 2,
  },
  fullBannerTitlePending: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 2,
  },
  fullBannerSubtitle: {
    color: colors.white + 'cc',
    fontSize: 12,
  },
  fullBannerSubtitlePending: {
    color: colors.textSecondary,
    fontSize: 12,
    marginLeft: spacing.xs,
  },
  fullBannerLink: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
  },
  syncingRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  readyIcon: {
    marginLeft: 'auto',
  },
});

export default OfflineIndicator;
