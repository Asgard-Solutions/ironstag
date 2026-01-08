import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
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
} from 'lucide-react-native';
import { useAuthStore } from '../../stores/authStore';
import { useImageStore } from '../../stores/imageStore';
import { subscriptionAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';

export default function ProfileScreen() {
  const insets = useSafeAreaInsets();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { images, clearAllImages, getStorageSize } = useImageStore();
  const [upgradeLoading, setUpgradeLoading] = useState(false);

  const isPremium = user?.subscription_tier === 'master_stag';

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0.00 MB';
    const k = 1024;
    const mb = bytes / (k * k);
    return mb.toFixed(2) + ' MB';
  };

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

  const handleCleanupOldImages = () => {
    Alert.alert(
      'Clean Up Old Images',
      'This will delete images older than 90 days.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clean Up',
          onPress: () => Alert.alert('Done', 'Old images have been cleaned up.'),
        },
      ]
    );
  };

  const handleClearAllImages = () => {
    Alert.alert(
      'Clear All Local Images',
      'This will delete all locally stored deer images. Your scan history will be preserved.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear All',
          style: 'destructive',
          onPress: async () => {
            await clearAllImages();
            Alert.alert('Done', 'All local images have been cleared.');
          },
        },
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
      'Delete Account',
      'This will permanently delete your account and all associated data. This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Account',
          style: 'destructive',
          onPress: () => {
            Alert.alert('Account Deletion', 'Please contact support@ironstag.com to delete your account.');
          },
        },
      ]
    );
  };

  const handleRequestDataDeletion = () => {
    Alert.alert(
      'Request Data Deletion',
      'This will request deletion of all your data from our servers. This process may take up to 30 days.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Request Deletion',
          style: 'destructive',
          onPress: () => {
            Alert.alert('Request Submitted', 'Your data deletion request has been submitted.');
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
        {/* User Info Card */}
        <View style={styles.userCard}>
          <View style={styles.avatarLarge}>
            <User size={40} color={colors.primary} />
          </View>
          
          <Text style={styles.labelText}>Full Name</Text>
          <Text style={styles.valueText}>{user?.name || 'User'}</Text>
          
          <View style={styles.infoRow}>
            <AtSign size={14} color={colors.textMuted} />
            <View style={styles.infoContent}>
              <Text style={styles.labelText}>Username</Text>
              <Text style={styles.valueText}>{user?.username || 'username'}</Text>
            </View>
          </View>
          
          <View style={styles.infoRow}>
            <Mail size={14} color={colors.textMuted} />
            <View style={styles.infoContent}>
              <Text style={styles.labelText}>Email</Text>
              <Text style={styles.valueText}>{user?.email}</Text>
            </View>
          </View>
        </View>

        {/* Subscription Card */}
        <View style={[styles.subscriptionCard, isPremium && styles.subscriptionCardActive]}>
          <View style={styles.subscriptionIcon}>
            <Crown size={24} color={isPremium ? colors.background : colors.primary} />
          </View>
          <View style={styles.subscriptionInfo}>
            <Text style={[styles.subscriptionTitle, isPremium && styles.subscriptionTitleActive]}>
              {isPremium ? 'Master Stag' : 'Scout'}
            </Text>
            <Text style={styles.subscriptionSubtitle}>
              {isPremium ? 'Unlimited scans • Premium features' : 'Free tier • 3 scans/day'}
            </Text>
          </View>
        </View>

        {/* Tagline */}
        <Text style={styles.tagline}>
          Precision AI-powered deer aging for ethical hunters
        </Text>

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
            <HardDrive size={18} color={colors.background} />
            <Text style={styles.storageTitle}>Local Storage</Text>
          </View>
          <Text style={styles.storageInfo}>{Object.keys(images).length} images stored</Text>
          <Text style={styles.storageInfo}>{formatBytes(getStorageSize())} used</Text>
          
          <View style={styles.cleanupRow}>
            <Clock size={16} color={colors.textMuted} />
            <Text style={styles.cleanupLabel}>Cleanup Interval</Text>
            <Text style={styles.cleanupValue}>90 days</Text>
          </View>

          <TouchableOpacity style={styles.cleanupButton} onPress={handleCleanupOldImages}>
            <Trash2 size={16} color={colors.primary} />
            <Text style={styles.cleanupButtonText}>Clean Up Old Images (90+ days)</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.clearAllButton} onPress={handleClearAllImages}>
            <Trash2 size={16} color={colors.error} />
            <Text style={styles.clearAllButtonText}>Clear All Local Images</Text>
          </TouchableOpacity>

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
          <TouchableOpacity style={styles.menuItem} onPress={() => Alert.alert('Privacy Policy', 'Your images are stored locally and never uploaded to our servers without your explicit consent.')}>
            <View style={[styles.menuIcon, styles.menuIconGold]}>
              <FileText size={18} color={colors.primary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Privacy Policy</Text>
              <Text style={styles.menuSubtitle}>How we protect your data</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem} onPress={() => Alert.alert('Terms of Service', 'By using Iron Stag, you agree to our terms of service and acceptable use policies.')}>
            <View style={[styles.menuIcon, styles.menuIconGold]}>
              <FileText size={18} color={colors.primary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Terms of Service</Text>
              <Text style={styles.menuSubtitle}>Usage terms and conditions</Text>
            </View>
          </TouchableOpacity>

          <TouchableOpacity style={styles.menuItem} onPress={handleRequestDataDeletion}>
            <View style={[styles.menuIcon, styles.menuIconWarning]}>
              <Trash2 size={18} color={colors.primary} />
            </View>
            <View style={styles.menuContent}>
              <Text style={styles.menuTitle}>Request Data Deletion</Text>
              <Text style={styles.menuSubtitle}>Delete your data from our servers</Text>
            </View>
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

  // User Card
  userCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    alignItems: 'center',
  },
  avatarLarge: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.background,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  labelText: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: spacing.sm,
  },
  valueText: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    width: '100%',
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  infoContent: {
    flex: 1,
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

  // Tagline
  tagline: {
    fontSize: 13,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.md,
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
    color: colors.background,
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
  },
  cleanupButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF',
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  cleanupButtonText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.primary,
  },
  clearAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF',
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
  storageNote: {
    fontSize: 11,
    color: '#888',
    textAlign: 'center',
    marginTop: spacing.xs,
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
});
