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
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
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

  const handleClearStorage = () => {
    Alert.alert(
      'Clear Local Images',
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

  if (!isAuthenticated) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
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

  // Menu items - flat list, no sections
  const menuItems = [
    {
      icon: Edit2,
      title: 'Edit Profile',
      subtitle: 'Name and username',
      onPress: () => Alert.alert('Coming Soon', 'Profile editing will be available soon.'),
    },
    {
      icon: CreditCard,
      title: 'Subscription',
      subtitle: isPremium ? 'Master Stag Active' : 'Scout (Free)',
      onPress: isPremium ? handleManageSubscription : handleUpgrade,
    },
    {
      icon: HardDrive,
      title: 'Storage',
      subtitle: `${Object.keys(images).length} images • ${formatBytes(getStorageSize())}`,
      onPress: handleClearStorage,
    },
    {
      icon: Shield,
      title: 'Privacy Policy',
      subtitle: 'Data protection info',
      onPress: () => Alert.alert('Privacy', 'Your images are stored locally and never uploaded to our servers.'),
    },
    {
      icon: Info,
      title: 'About Iron Stag',
      subtitle: 'v1.0.0',
      onPress: () => Alert.alert('Iron Stag', 'Hunt Smarter. Harvest Responsibly.\n\nForged in Asgard, Tested in the Field.'),
    },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Compact Profile Header */}
        <View style={styles.header}>
          <View style={styles.headerRow}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>
                {user?.name?.charAt(0).toUpperCase() || 'U'}
              </Text>
            </View>
            <View style={styles.headerInfo}>
              <Text style={styles.userName}>{user?.name}</Text>
              <Text style={styles.userEmail}>{user?.email}</Text>
            </View>
            <View style={[styles.tierBadge, isPremium && styles.premiumBadge]}>
              {isPremium && <Crown size={12} color={colors.primary} />}
              <Text style={[styles.tierText, isPremium && styles.premiumText]}>
                {isPremium ? 'Master Stag' : 'Scout'}
              </Text>
            </View>
          </View>
        </View>

        {/* Primary CTA: Subscription Card */}
        <View style={[styles.subscriptionCard, isPremium && styles.subscriptionCardPremium]}>
          <View style={styles.subscriptionHeader}>
            <Crown size={28} color={isPremium ? colors.primary : colors.textMuted} />
            <View style={styles.subscriptionInfo}>
              <Text style={styles.subscriptionTitle}>
                {isPremium ? 'Master Stag Active' : 'Upgrade to Master Stag'}
              </Text>
              <Text style={styles.subscriptionSubtitle}>
                {isPremium ? 'Unlimited scans • Premium features' : 'Unlimited scans • No daily limits'}
              </Text>
            </View>
          </View>
          <TouchableOpacity
            style={[styles.subscriptionButton, isPremium && styles.subscriptionButtonSecondary]}
            onPress={isPremium ? handleManageSubscription : handleUpgrade}
            disabled={upgradeLoading}
          >
            <Text style={[styles.subscriptionButtonText, isPremium && styles.subscriptionButtonTextSecondary]}>
              {upgradeLoading ? 'Loading...' : isPremium ? 'Manage Subscription' : '$9.99/month'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Usage Snapshot - Minimal */}
        <View style={styles.usageRow}>
          <View style={styles.usageStat}>
            <Text style={styles.usageValue}>{user?.scans_remaining || 0}</Text>
            <Text style={styles.usageLabel}>Scans Left Today</Text>
          </View>
          <View style={styles.usageDivider} />
          <View style={styles.usageStat}>
            <Text style={styles.usageValue}>{Object.keys(images).length}</Text>
            <Text style={styles.usageLabel}>Saved Images</Text>
          </View>
        </View>

        {/* Single Flat Menu List */}
        <View style={styles.menuContainer}>
          {menuItems.map((item, index) => (
            <TouchableOpacity
              key={index}
              style={[
                styles.menuItem,
                index === menuItems.length - 1 && styles.menuItemLast
              ]}
              onPress={item.onPress}
              activeOpacity={0.7}
            >
              <View style={styles.menuIcon}>
                <item.icon size={18} color={colors.primary} />
              </View>
              <View style={styles.menuContent}>
                <Text style={styles.menuTitle}>{item.title}</Text>
                <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
              </View>
              <ChevronRight size={18} color={colors.textMuted} />
            </TouchableOpacity>
          ))}
        </View>

        {/* Destructive Actions - De-emphasized */}
        <View style={styles.destructiveActions}>
          <TouchableOpacity onPress={handleLogout}>
            <Text style={styles.signOutText}>Sign Out</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={handleDeleteAccount}>
            <Text style={styles.deleteText}>Delete Account</Text>
          </TouchableOpacity>
        </View>

        {/* Minimal Footer */}
        <Text style={styles.footer}>
          Iron Stag v1.0 • Forged in Asgard
        </Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  
  // Compact Header
  header: {
    marginBottom: spacing.lg,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: colors.primary,
  },
  avatarText: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.primary,
  },
  headerInfo: {
    flex: 1,
    marginLeft: spacing.md,
  },
  userName: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  userEmail: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  tierBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.backgroundCard,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    gap: 4,
  },
  premiumBadge: {
    backgroundColor: 'rgba(200, 162, 74, 0.15)',
    borderWidth: 1,
    borderColor: colors.primaryDark,
  },
  tierText: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
  },
  premiumText: {
    color: colors.primary,
  },

  // Subscription Card - Primary CTA
  subscriptionCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  subscriptionCardPremium: {
    backgroundColor: 'rgba(200, 162, 74, 0.08)',
    borderColor: colors.primaryDark,
  },
  subscriptionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  subscriptionInfo: {
    flex: 1,
    marginLeft: spacing.md,
  },
  subscriptionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  subscriptionSubtitle: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  subscriptionButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm + 2,
    borderRadius: borderRadius.md,
    alignItems: 'center',
  },
  subscriptionButtonSecondary: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  subscriptionButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.background,
  },
  subscriptionButtonTextSecondary: {
    color: colors.primary,
  },

  // Usage Row - Minimal
  usageRow: {
    flexDirection: 'row',
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  usageStat: {
    flex: 1,
    alignItems: 'center',
  },
  usageValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  usageLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 4,
  },
  usageDivider: {
    width: 1,
    backgroundColor: colors.border,
    marginHorizontal: spacing.md,
  },

  // Menu Container
  menuContainer: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.lg,
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
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(200, 162, 74, 0.12)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.textPrimary,
  },
  menuSubtitle: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 2,
  },

  // Destructive Actions
  destructiveActions: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: spacing.xl,
    marginBottom: spacing.lg,
    paddingTop: spacing.sm,
  },
  signOutText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.error,
  },
  deleteText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textMuted,
  },

  // Footer
  footer: {
    fontSize: 11,
    color: colors.textMuted,
    textAlign: 'center',
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
