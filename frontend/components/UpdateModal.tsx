/**
 * App Update Modal Component
 * 
 * Displays update prompts to users when a new version is available.
 * Supports both soft (dismissible) and force (blocking) update modes.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  Platform,
  BackHandler,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Download, AlertTriangle, Sparkles, X } from 'lucide-react-native';
import { colors, spacing, borderRadius } from '../constants/theme';

interface UpdateModalProps {
  visible: boolean;
  updateMode: 'soft' | 'force';
  latestVersion: string;
  currentVersion: string;
  releaseNotes: string | null;
  message: string | null;
  storeName: string;
  onUpdate: () => void;
  onDismiss: () => void;
}

export function UpdateModal({
  visible,
  updateMode,
  latestVersion,
  currentVersion,
  releaseNotes,
  message,
  storeName,
  onUpdate,
  onDismiss,
}: UpdateModalProps) {
  const insets = useSafeAreaInsets();
  const isForceUpdate = updateMode === 'force';

  // Handle back button on Android for force updates
  React.useEffect(() => {
    if (Platform.OS === 'android' && isForceUpdate && visible) {
      const backHandler = BackHandler.addEventListener('hardwareBackPress', () => {
        // Prevent back button from dismissing force update modal
        return true;
      });
      return () => backHandler.remove();
    }
  }, [isForceUpdate, visible]);

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent={true}
      onRequestClose={isForceUpdate ? undefined : onDismiss}
    >
      <View style={styles.overlay}>
        <View style={[
          styles.container,
          { marginTop: insets.top + spacing.xl, marginBottom: insets.bottom + spacing.xl }
        ]}>
          {/* Close button for soft updates only */}
          {!isForceUpdate && (
            <TouchableOpacity 
              style={styles.closeButton} 
              onPress={onDismiss}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <X size={20} color={colors.textMuted} />
            </TouchableOpacity>
          )}

          {/* Icon */}
          <View style={[
            styles.iconContainer,
            isForceUpdate ? styles.iconContainerForce : styles.iconContainerSoft
          ]}>
            {isForceUpdate ? (
              <AlertTriangle size={40} color={colors.error} />
            ) : (
              <Sparkles size={40} color={colors.primary} />
            )}
          </View>

          {/* Title */}
          <Text style={styles.title}>
            {isForceUpdate ? 'Update Required' : 'Update Available'}
          </Text>

          {/* Version info */}
          <View style={styles.versionContainer}>
            <Text style={styles.versionText}>
              Current: v{currentVersion}
            </Text>
            <Text style={styles.versionArrow}>→</Text>
            <Text style={[styles.versionText, styles.versionNew]}>
              v{latestVersion}
            </Text>
          </View>

          {/* Message */}
          <Text style={styles.message}>
            {message || (isForceUpdate 
              ? 'A critical update is required to continue using Iron Stag. Please update now.'
              : 'A new version is available with improvements and bug fixes.'
            )}
          </Text>

          {/* Release notes */}
          {releaseNotes && (
            <View style={styles.releaseNotesContainer}>
              <Text style={styles.releaseNotesTitle}>What's New:</Text>
              <Text style={styles.releaseNotesText}>{releaseNotes}</Text>
            </View>
          )}

          {/* Update button */}
          <TouchableOpacity 
            style={[
              styles.updateButton,
              isForceUpdate ? styles.updateButtonForce : styles.updateButtonSoft
            ]} 
            onPress={onUpdate}
            activeOpacity={0.8}
          >
            <Download size={20} color={colors.background} />
            <Text style={styles.updateButtonText}>
              Update on {storeName}
            </Text>
          </TouchableOpacity>

          {/* Dismiss button for soft updates */}
          {!isForceUpdate && (
            <TouchableOpacity 
              style={styles.dismissButton} 
              onPress={onDismiss}
            >
              <Text style={styles.dismissButtonText}>Maybe Later</Text>
            </TouchableOpacity>
          )}

          {/* Force update notice */}
          {isForceUpdate && (
            <Text style={styles.forceNotice}>
              You cannot continue without updating.
            </Text>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  container: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    width: '100%',
    maxWidth: 360,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    position: 'relative',
  },
  closeButton: {
    position: 'absolute',
    top: spacing.md,
    right: spacing.md,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.lg,
    borderWidth: 2,
  },
  iconContainerSoft: {
    backgroundColor: 'rgba(200, 162, 74, 0.15)',
    borderColor: colors.primary,
  },
  iconContainerForce: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: colors.error,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  versionContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  versionText: {
    fontSize: 14,
    color: colors.textMuted,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  versionArrow: {
    fontSize: 14,
    color: colors.textMuted,
  },
  versionNew: {
    color: colors.primary,
    fontWeight: '600',
  },
  message: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  releaseNotesContainer: {
    backgroundColor: colors.background,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    width: '100%',
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  releaseNotesTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  releaseNotesText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  updateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.md,
    width: '100%',
    gap: spacing.sm,
  },
  updateButtonSoft: {
    backgroundColor: colors.primary,
  },
  updateButtonForce: {
    backgroundColor: colors.error,
  },
  updateButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
  dismissButton: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
  },
  dismissButtonText: {
    fontSize: 14,
    color: colors.textMuted,
  },
  forceNotice: {
    marginTop: spacing.md,
    fontSize: 12,
    color: colors.error,
    textAlign: 'center',
    fontStyle: 'italic',
  },
});
