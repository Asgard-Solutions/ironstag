import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Linking,
  ActivityIndicator,
  ActionSheetIOS,
  Platform,
  Modal,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  User,
  Crown,
  HardDrive,
  ChevronRight,
  Edit2,
  Shield,
  Info,
  Trash2,
  ChevronLeft,
  AtSign,
  Mail,
  Clock,
  Camera,
  BookOpen,
  Settings,
  FileText,
  ExternalLink,
  Check,
  X,
} from 'lucide-react-native';
import { useAuthStore } from '../../stores/authStore';
import { useImageStore } from '../../stores/imageStore';
import { subscriptionAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';

// Constants for Privacy & Legal URLs
const PRIVACY_POLICY_URL = 'https://www.asgardsolution.io/iron-stag/privacy';
const TERMS_OF_SERVICE_URL = 'https://www.asgardsolution.io/iron-stag/terms';
const PRIVACY_EMAIL = 'privacy@asgardsolutions.io';

// Available cleanup intervals
const CLEANUP_INTERVALS = [
  { label: '30 days', value: 30 },
  { label: '60 days', value: 60 },
  { label: '90 days (recommended)', value: 90 },
  { label: '180 days', value: 180 },
];

export default function ProfileScreen() {
  const insets = useSafeAreaInsets();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { 
    stats, 
    cleanupInterval, 
    isLoaded,
    initialize,
    cleanupOldImages, 
    clearAllImages, 
    setCleanupInterval,
    refreshStats 
  } = useImageStore();
  const [upgradeLoading, setUpgradeLoading] = useState(false);
  const [isCleaningUp, setIsCleaningUp] = useState(false);
  const [showIntervalPicker, setShowIntervalPicker] = useState(false);

  const isPremium = user?.subscription_tier === 'master_stag';

  // Initialize image store on mount
  useEffect(() => {
    initialize();
  }, []);

  // Format date for display
  const formatDate = (date: Date | null): string | null => {
    if (!date) return null;
    return date.toLocaleDateString('en-US', {
      month: '2-digit',
      day: '2-digit',
      year: 'numeric',
    });
  };

  // Calculate next cleanup date based on oldest image and cleanup interval
  const getNextCleanupDate = (): Date | null => {
    if (!stats.oldestImage) return null;
    
    // Next cleanup date = oldest image date + cleanup interval days
    const nextCleanup = new Date(stats.oldestImage);
    nextCleanup.setDate(nextCleanup.getDate() + cleanupInterval);
    
    return nextCleanup;
  };

  // Check if cleanup is due (oldest image is older than interval)
  const isCleanupDue = (): boolean => {
    if (!stats.oldestImage) return false;
    
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - cleanupInterval);
    
    return stats.oldestImage < cutoffDate;
  };

  const nextCleanupDate = getNextCleanupDate();
  const cleanupIsDue = isCleanupDue();

  const handleUpgrade = async () => {
    setUpgradeLoading(true);
    try {
      const response = await subscriptionAPI.createCheckout();
      Alert.alert(
        'Upgrade to Master Stag',
        'Stripe checkout would open here. Session ID: ' + response.data.session_id
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to start upgrade process.');
    } finally {
      setUpgradeLoading(false);
    }
  };

  const handleManageSubscription = () => {
    Alert.alert(
      'Manage Subscription',
      'Subscription management portal would open here.'
    );
  };

  // Cleanup Interval Selector
  const handleSelectCleanupInterval = () => {
    setShowIntervalPicker(true);
  };

  const handleIntervalSelect = async (value: number) => {
    try {
      await setCleanupInterval(value);
      setShowIntervalPicker(false);
      Alert.alert(
        'Cleanup Interval Updated',
        `Images older than ${value} days will be cleaned up when you tap "Clean Up Old Images".`
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to save cleanup interval.');
    }
  };

  // Clean Up Old Images
  const handleCleanupOldImages = () => {
    if (stats.totalImages === 0) {
      Alert.alert('No Images', 'There are no images to clean up.');
      return;
    }

    Alert.alert(
      'Clean Up Old Images?',
      `This will delete images older than ${cleanupInterval} days from your device. Your scan history will remain intact.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clean Up',
          style: 'destructive',
          onPress: async () => {
            setIsCleaningUp(true);
            try {
              const deletedCount = await cleanupOldImages();
              Alert.alert(
                'Cleanup Complete',
                `Cleaned up ${deletedCount} images older than ${cleanupInterval} days.`
              );
            } catch (error) {
              Alert.alert('Error', 'Failed to clean up images.');
            } finally {
              setIsCleaningUp(false);
            }
          },
        },
      ]
    );
  };

  // Clear All Local Images
  const handleClearAllImages = () => {
    Alert.alert(
      'Clear All Local Images?',
      stats.totalImages === 0 
        ? 'There are currently no images stored on your device.'
        : `This will delete ALL ${stats.totalImages} image${stats.totalImages !== 1 ? 's' : ''} from your device. Your scan history will remain intact, but images will need to be re-scanned to view.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: stats.totalImages === 0 ? 'OK' : 'Clear All',
          style: stats.totalImages === 0 ? 'default' : 'destructive',
          onPress: async () => {
            if (stats.totalImages === 0) return;
            
            setIsCleaningUp(true);
            try {
              const deletedCount = await clearAllImages();
              Alert.alert('Storage Cleared', `Deleted ${deletedCount} local image${deletedCount !== 1 ? 's' : ''}.`);
            } catch (error) {
              Alert.alert('Error', 'Failed to clear images.');
            } finally {
              setIsCleaningUp(false);
            }
          },
        },
      ]
    );
  };

  // Privacy Policy
  const openPrivacyPolicy = async () => {
    try {
      const canOpen = await Linking.canOpenURL(PRIVACY_POLICY_URL);
      if (canOpen) {
        await Linking.openURL(PRIVACY_POLICY_URL);
      } else {
        Alert.alert(
          'Cannot Open Link',
          'Please visit asgardsolution.io to view the Privacy Policy.'
        );
      }
    } catch (error) {
      Alert.alert('Error', 'Could not open Privacy Policy. Please try again.');
    }
  };

  // Terms of Service
  const openTermsOfService = async () => {
    try {
      const canOpen = await Linking.canOpenURL(TERMS_OF_SERVICE_URL);
      if (canOpen) {
        await Linking.openURL(TERMS_OF_SERVICE_URL);
      } else {
        Alert.alert(
          'Cannot Open Link',
          'Please visit asgardsolution.io to view the Terms of Service.'
        );
      }
    } catch (error) {
      Alert.alert('Error', 'Could not open Terms of Service. Please try again.');
    }
  };

  // Request Data Deletion
  const handleRequestDataDeletion = () => {
    Alert.alert(
      'Request Data Deletion',
      `To request deletion of your data:\n\n` +
      `1. Delete your account using the "Delete Account" button below\n\n` +
      `2. Or email us at ${PRIVACY_EMAIL} with your account email\n\n` +
      `We will process your request within 30 days per our Privacy Policy.`,
      [
        {
          text: 'Email Us',
          onPress: async () => {
            const subject = encodeURIComponent('Iron Stag Data Deletion Request');
            const body = encodeURIComponent(
              'Please delete all my data associated with Iron Stag.\n\n' +
              `Account Email: ${user?.email || '[Your email here]'}\n\n` +
              'Reason (optional): '
            );
            try {
              await Linking.openURL(`mailto:${PRIVACY_EMAIL}?subject=${subject}&body=${body}`);
            } catch (error) {
              Alert.alert('Error', 'Could not open email app.');
            }
          },
        },
        { text: 'Cancel', style: 'cancel' },
      ]
    );
  };

  const handleLogout = () => {
    Alert.alert(
      'Sign Out',
      'Are you sure you want to sign out?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Sign Out',
          style: 'destructive',
          onPress: async () => {
            await logout();
            router.replace('/');
          },
        },
      ]
    );
  };

  const handleDeleteAccount = () => {
    Alert.alert(
      'Delete Account?',
      'This will permanently delete your account and all associated data. This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Account',
          style: 'destructive',
          onPress: () => {
            // Second confirmation
            Alert.alert(
              'Are you absolutely sure?',
              'All your scan history, analysis results, and subscription data will be permanently deleted.',
              [
                { text: 'Cancel', style: 'cancel' },
                {
                  text: 'Yes, Delete My Account',
                  style: 'destructive',
                  onPress: async () => {
                    // In production, this would call DELETE /api/profile
                    Alert.alert(
                      'Account Deletion Requested',
                      'Your account deletion request has been submitted. You will be signed out.'
                    );
                    await logout();
                    router.replace('/');
                  },
                },
              ]
            );
          },
        },
      ]
    );
  };

  if (!isAuthenticated) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
            <ChevronLeft size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Profile</Text>
          <View style={styles.headerRight} />
        </View>
        
        <View style={styles.authRequired}>
          <User size={64} color={colors.textMuted} />
          <Text style={styles.authTitle}>Sign In Required</Text>
          <Text style={styles.authText}>
            Sign in to manage your profile and subscription.
          </Text>
          <TouchableOpacity 
            style={styles.signInButton}
            onPress={() => router.push('/(auth)/login')}
          >
            <Text style={styles.signInButtonText}>Sign In</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.push('/(tabs)')}>
          <ChevronLeft size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Profile</Text>
        <TouchableOpacity style={styles.editButton}>
          <Edit2 size={18} color={colors.primary} />
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Compact Profile Header */}
        <View style={styles.profileHeader}>
          <View style={styles.avatarLarge}>
            <Text style={styles.avatarInitial}>
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </Text>
          </View>
          
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{user?.name || 'User'}</Text>
            {user?.username && (
              <Text style={styles.profileUsername}>@{user.username}</Text>
            )}
            <Text style={styles.profileEmail}>{user?.email}</Text>
          </View>
          
          <View style={[styles.tierBadge, isPremium && styles.tierBadgePremium]}>
            <Text style={[styles.tierBadgeText, isPremium && styles.tierBadgeTextPremium]}>
              {isPremium ? 'Master Stag' : 'Scout'}
            </Text>
          </View>
        </View>

        {/* Subscription Card */}
        <View style={[styles.subscriptionCard, isPremium && styles.subscriptionCardActive]}>
          <View style={styles.subscriptionIcon}>
            <Crown size={24} color={isPremium ? colors.background : colors.primary} />
          </View>
          <View style={styles.subscriptionInfo}>
            <Text style={[styles.subscriptionTitle, isPremium && styles.subscriptionTitleActive]}>
              {isPremium ? 'Master Stag Active' : 'Upgrade to Master Stag'}
            </Text>
            <Text style={styles.subscriptionSubtitle}>
              {isPremium ? 'Unlimited scans • Premium features' : 'Unlimited scans • No daily limits'}
            </Text>
          </View>
          {!isPremium && (
            <TouchableOpacity 
              style={styles.upgradeButton}
              onPress={handleUpgrade}
              disabled={upgradeLoading}
            >
              <Text style={styles.upgradeButtonText}>
                {upgradeLoading ? '...' : '$9.99/mo'}
              </Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Stats Row */}
        <View style={styles.statsCard}>
          <View style={styles.stat}>
            <Text style={styles.statValue}>0</Text>
            <Text style={styles.statLabel}>Ethical{'\n'}Decisions</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.stat}>
            <Text style={[styles.statValue, styles.harvestValue]}>0</Text>
            <Text style={styles.statLabel}>Harvest{'\n'}Recs</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.stat}>
            <Text style={[styles.statValue, styles.passValue]}>0</Text>
            <Text style={styles.statLabel}>Pass{'\n'}Recs</Text>
          </View>
        </View>

        {/* Local Storage Card */}
        <View style={styles.storageCard}>
          <View style={styles.storageHeader}>
            <HardDrive size={18} color="#333" />
            <Text style={styles.storageTitle}>Local Storage</Text>
          </View>
          
          {/* Storage Stats */}
          <Text style={styles.storageInfo}>
            {stats.totalImages} image{stats.totalImages !== 1 ? 's' : ''} stored
          </Text>
          <Text style={styles.storageInfo}>{stats.totalSizeMB} MB used</Text>
          {stats.oldestImage && (
            <Text style={styles.storageInfo}>
              Oldest: {formatDate(stats.oldestImage)}
            </Text>
          )}
          
          {/* Cleanup Interval Row */}
          <TouchableOpacity 
            style={styles.cleanupRow} 
            onPress={handleSelectCleanupInterval}
            activeOpacity={0.7}
          >
            <Clock size={16} color={colors.textMuted} />
            <Text style={styles.cleanupLabel}>Cleanup Interval</Text>
            <Text style={styles.cleanupValue}>{cleanupInterval} days</Text>
            <ChevronRight size={16} color={colors.textMuted} />
          </TouchableOpacity>

          {/* Clean Up Old Images Button */}
          <TouchableOpacity 
            style={[
              styles.cleanupButton,
              (stats.totalImages === 0 || isCleaningUp) && styles.buttonDisabled
            ]} 
            onPress={handleCleanupOldImages}
            disabled={stats.totalImages === 0 || isCleaningUp}
          >
            {isCleaningUp ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Trash2 size={16} color={stats.totalImages === 0 ? colors.textMuted : '#D97706'} />
            )}
            <View style={styles.cleanupButtonContent}>
              <Text style={[
                styles.cleanupButtonText,
                stats.totalImages === 0 && styles.buttonTextDisabled
              ]}>
                Clean Up Old Images ({cleanupInterval}+ days)
              </Text>
              {nextCleanupDate && stats.totalImages > 0 && (
                <Text style={[
                  styles.cleanupDateText,
                  cleanupIsDue && styles.cleanupDateDue
                ]}>
                  {cleanupIsDue 
                    ? 'Cleanup available now' 
                    : `Next cleanup: ${formatDate(nextCleanupDate)}`}
                </Text>
              )}
            </View>
          </TouchableOpacity>

          {/* Clear All Button - Always Active */}
          <TouchableOpacity 
            style={[
              styles.clearAllButton,
              isCleaningUp && styles.buttonDisabled
            ]} 
            onPress={handleClearAllImages}
            disabled={isCleaningUp}
          >
            {isCleaningUp ? (
              <ActivityIndicator size="small" color={colors.error} />
            ) : (
              <Trash2 size={16} color={colors.error} />
            )}
            <Text style={styles.clearAllButtonText}>
              Clear All Local Images
            </Text>
          </TouchableOpacity>

          {/* Privacy Disclaimer */}
          <Text style={styles.storageNote}>
            Images are stored only on your device. Deleting them does not affect your scan history or analysis results.
          </Text>
        </View>

        {/* Menu Items */}
        <View style={styles.menuSection}>
          <TouchableOpacity style={styles.menuItem} onPress={isPremium ? handleManageSubscription : handleUpgrade}>
            <View style={styles.menuIcon}>
              <Settings size={18} color={colors.textPrimary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Manage Subscription</Text>
              <Text style={styles.menuSubtitle}>Cancel anytime</Text>
            </View>
            <ChevronRight size={18} color={colors.textMuted} />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/(tabs)/learn')}>
            <View style={styles.menuIcon}>
              <BookOpen size={18} color={colors.textPrimary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Deer Aging Guide</Text>
              <Text style={styles.menuSubtitle}>Learn to age deer</Text>
            </View>
            <ChevronRight size={18} color={colors.textMuted} />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/(tabs)/history')}>
            <View style={styles.menuIcon}>
              <Camera size={18} color={colors.textPrimary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Scan History</Text>
              <Text style={styles.menuSubtitle}>0 total scans</Text>
            </View>
            <ChevronRight size={18} color={colors.textMuted} />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem} onPress={() => Alert.alert('Iron Stag', 'Hunt Smarter. Harvest Responsibly.\n\nVersion 1.0.0\nForged in Asgard, Tested in the Field.')}>
            <View style={styles.menuIcon}>
              <Info size={18} color={colors.textPrimary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>About Iron Stag</Text>
              <Text style={styles.menuSubtitle}>App information</Text>
            </View>
            <ChevronRight size={18} color={colors.textMuted} />
          </TouchableOpacity>
        </View>

        {/* Privacy & Legal */}
        <Text style={styles.sectionHeader}>Privacy & Legal</Text>
        <View style={styles.menuSection}>
          <TouchableOpacity style={styles.menuItem} onPress={openPrivacyPolicy}>
            <View style={[styles.menuIcon, styles.menuIconGold]}>
              <FileText size={18} color={colors.primary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Privacy Policy</Text>
              <Text style={styles.menuSubtitle}>How we protect your data</Text>
            </View>
            <ExternalLink size={16} color={colors.textMuted} />
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem} onPress={openTermsOfService}>
            <View style={[styles.menuIcon, styles.menuIconGold]}>
              <FileText size={18} color={colors.primary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Terms of Service</Text>
              <Text style={styles.menuSubtitle}>Usage terms and conditions</Text>
            </View>
            <ExternalLink size={16} color={colors.textMuted} />
          </TouchableOpacity>

          <TouchableOpacity style={[styles.menuItem, styles.menuItemLast]} onPress={handleRequestDataDeletion}>
            <View style={[styles.menuIcon, styles.menuIconWarning]}>
              <Trash2 size={18} color="#FFF" />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Request Data Deletion</Text>
              <Text style={styles.menuSubtitle}>Delete your data from our servers</Text>
            </View>
            <ChevronRight size={18} color={colors.textMuted} />
          </TouchableOpacity>
        </View>

        {/* Account Actions */}
        <TouchableOpacity style={styles.signOutBtn} onPress={handleLogout}>
          <Text style={styles.signOutBtnText}>Sign Out</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.deleteAccountBtn} onPress={handleDeleteAccount}>
          <Trash2 size={16} color={colors.error} />
          <Text style={styles.deleteAccountBtnText}>Delete Account</Text>
        </TouchableOpacity>

        {/* Footer */}
        <View style={styles.footer}>
          <Shield size={20} color={colors.textMuted} />
          <Text style={styles.footerText}>Forged in Asgard, Tested in the Field</Text>
          <Text style={styles.footerCopyright}>© 2025 Asgard Solutions LLC</Text>
        </View>
      </ScrollView>

      {/* Cleanup Interval Picker Modal */}
      <Modal
        visible={showIntervalPicker}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setShowIntervalPicker(false)}
      >
        <TouchableOpacity 
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowIntervalPicker(false)}
        >
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Cleanup Interval</Text>
              <TouchableOpacity onPress={() => setShowIntervalPicker(false)}>
                <X size={24} color={colors.textMuted} />
              </TouchableOpacity>
            </View>
            <Text style={styles.modalSubtitle}>
              Choose how old images should be before cleanup:
            </Text>
            {CLEANUP_INTERVALS.map((interval) => (
              <TouchableOpacity
                key={interval.value}
                style={[
                  styles.intervalOption,
                  cleanupInterval === interval.value && styles.intervalOptionSelected
                ]}
                onPress={() => handleIntervalSelect(interval.value)}
              >
                <Text style={[
                  styles.intervalOptionText,
                  cleanupInterval === interval.value && styles.intervalOptionTextSelected
                ]}>
                  {interval.label}
                </Text>
                {cleanupInterval === interval.value && (
                  <Check size={20} color={colors.primary} />
                )}
              </TouchableOpacity>
            ))}
          </View>
        </TouchableOpacity>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  
  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  headerRight: {
    width: 40,
  },
  editButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },

  scrollContent: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl * 2,
  },

  // Compact Profile Header
  profileHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  avatarLarge: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.background,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarInitial: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.primary,
  },
  profileInfo: {
    flex: 1,
    marginLeft: spacing.md,
  },
  profileName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  profileUsername: {
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 1,
  },
  profileEmail: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  tierBadge: {
    backgroundColor: colors.backgroundCard,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
  },
  tierBadgePremium: {
    backgroundColor: 'rgba(200, 162, 74, 0.15)',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  tierBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textMuted,
  },
  tierBadgeTextPremium: {
    color: colors.primary,
  },

  // Subscription Card
  subscriptionCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  subscriptionCardActive: {
    borderColor: colors.primary,
    backgroundColor: 'rgba(200, 162, 74, 0.08)',
  },
  subscriptionIcon: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: colors.background,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  subscriptionInfo: {
    flex: 1,
  },
  subscriptionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary,
  },
  subscriptionTitleActive: {
    color: colors.primary,
  },
  subscriptionSubtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  upgradeButton: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  upgradeButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.background,
  },

  // Stats Card
  statsCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  stat: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  harvestValue: {
    color: colors.error,
  },
  passValue: {
    color: colors.harvest,
  },
  statLabel: {
    fontSize: 11,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: 4,
  },
  statDivider: {
    width: 1,
    height: 40,
    backgroundColor: colors.border,
  },

  // Storage Card
  storageCard: {
    backgroundColor: '#F5F5F5',
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  storageHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  storageTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  storageInfo: {
    fontSize: 14,
    color: '#666',
    marginBottom: 2,
  },
  cleanupRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF',
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  cleanupLabel: {
    flex: 1,
    fontSize: 14,
    color: '#333',
    marginLeft: spacing.sm,
  },
  cleanupValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginRight: spacing.xs,
  },
  cleanupButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FEF3C7',
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  cleanupButtonContent: {
    flex: 1,
  },
  cleanupButtonText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#D97706',
  },
  cleanupDateText: {
    fontSize: 11,
    color: '#92400E',
    marginTop: 2,
  },
  cleanupDateDue: {
    color: '#059669',
    fontWeight: '600',
  },
  clearAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FEE2E2',
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  clearAllButtonText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.error,
  },
  buttonDisabled: {
    backgroundColor: '#F3F4F6',
    opacity: 0.6,
  },
  buttonTextDisabled: {
    color: colors.textMuted,
  },
  storageNote: {
    fontSize: 11,
    color: '#888',
    textAlign: 'center',
    marginTop: spacing.xs,
    lineHeight: 16,
  },

  // Menu Section
  menuSection: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  menuItemLast: {
    borderBottomWidth: 0,
  },
  menuIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  menuIconGold: {
    borderColor: colors.primary,
  },
  menuIconWarning: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  menuSubtitle: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 2,
  },

  // Section Header
  sectionHeader: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    marginTop: spacing.sm,
  },

  // Account Actions
  signOutBtn: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  signOutBtnText: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.textSecondary,
  },
  deleteAccountBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'transparent',
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.error,
    padding: spacing.md,
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  deleteAccountBtnText: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.error,
  },

  // Footer
  footer: {
    alignItems: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.xl,
  },
  footerText: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: spacing.sm,
    fontStyle: 'italic',
  },
  footerCopyright: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },

  // Auth Required
  authRequired: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  authTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  authText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  signInButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.full,
  },
  signInButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },

  // Modal Styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  modalContent: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    width: '100%',
    maxWidth: 340,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  modalSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  intervalOption: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.md,
    marginBottom: spacing.xs,
    backgroundColor: colors.background,
  },
  intervalOptionSelected: {
    backgroundColor: 'rgba(200, 162, 74, 0.15)',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  intervalOptionText: {
    fontSize: 16,
    color: colors.textPrimary,
  },
  intervalOptionTextSelected: {
    fontWeight: '600',
    color: colors.primary,
  },
});
