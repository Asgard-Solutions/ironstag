import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  User,
  Crown,
  Settings,
  HardDrive,
  LogOut,
  ChevronRight,
  Edit2,
  CreditCard,
  Shield,
  Info,
} from 'lucide-react-native';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { useAuthStore } from '../../stores/authStore';
import { useImageStore } from '../../stores/imageStore';
import { subscriptionAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';

export default function ProfileScreen() {
  const insets = useSafeAreaInsets();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { images, clearAllImages, getStorageSize } = useImageStore();
  const [upgradeLoading, setUpgradeLoading] = useState(false);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleUpgrade = async () => {
    setUpgradeLoading(true);
    try {
      const response = await subscriptionAPI.createCheckout();
      // In a real app, this would open the Stripe checkout URL
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

  const handleClearStorage = () => {
    Alert.alert(
      'Clear Local Images',
      'This will delete all locally stored deer images. Your scan history will be preserved, but images will no longer be viewable. Continue?',
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

  if (!isAuthenticated) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <View style={styles.authRequired}>
          <User size={64} color={colors.textMuted} />
          <Text style={styles.authTitle}>Sign In Required</Text>
          <Text style={styles.authText}>
            Sign in to manage your profile and subscription.
          </Text>
          <Button
            title="Sign In"
            onPress={() => router.push('/(auth)/login')}
          />
        </View>
      </View>
    );
  }

  const menuItems = [
    {
      icon: Edit2,
      title: 'Edit Profile',
      subtitle: 'Update your name and username',
      onPress: () => Alert.alert('Coming Soon', 'Profile editing will be available soon.'),
    },
    {
      icon: CreditCard,
      title: 'Subscription',
      subtitle: user?.subscription_tier === 'master_stag' ? 'Master Stag (Premium)' : 'Scout (Free)',
      onPress: handleUpgrade,
      badge: user?.subscription_tier !== 'master_stag' ? 'Upgrade' : null,
    },
    {
      icon: HardDrive,
      title: 'Storage',
      subtitle: `${Object.keys(images).length} images (${formatBytes(getStorageSize())})`,
      onPress: handleClearStorage,
    },
    {
      icon: Shield,
      title: 'Privacy Policy',
      subtitle: 'How we protect your data',
      onPress: () => Alert.alert('Privacy', 'Your images are stored locally and never uploaded to our servers.'),
    },
    {
      icon: Info,
      title: 'About Iron Stag',
      subtitle: 'Version 1.0.0',
      onPress: () => Alert.alert('Iron Stag', 'Hunt Smarter. Harvest Responsibly.\n\nForged in Asgard, Tested in the Field.'),
    },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile Header */}
        <View style={styles.header}>
          <View style={styles.avatarContainer}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>
                {user?.name?.charAt(0).toUpperCase() || 'U'}
              </Text>
            </View>
            {user?.subscription_tier === 'master_stag' && (
              <View style={styles.crownBadge}>
                <Crown size={16} color={colors.primary} />
              </View>
            )}
          </View>
          <Text style={styles.userName}>{user?.name}</Text>
          <Text style={styles.userEmail}>{user?.email}</Text>
          <Badge
            text={user?.subscription_tier === 'master_stag' ? 'Master Stag' : 'Scout'}
            variant={user?.subscription_tier === 'master_stag' ? 'harvest' : 'info'}
            style={styles.tierBadge}
          />
        </View>

        {/* Stats Card */}
        <Card style={styles.statsCard}>
          <View style={styles.statRow}>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{user?.scans_remaining || 0}</Text>
              <Text style={styles.statLabel}>Scans Left Today</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.stat}>
              <Text style={styles.statValue}>{Object.keys(images).length}</Text>
              <Text style={styles.statLabel}>Saved Images</Text>
            </View>
          </View>
        </Card>

        {/* Upgrade Card (for free users) */}
        {user?.subscription_tier !== 'master_stag' && (
          <Card style={styles.upgradeCard}>
            <View style={styles.upgradeContent}>
              <Crown size={32} color={colors.primary} />
              <View style={styles.upgradeText}>
                <Text style={styles.upgradeTitle}>Upgrade to Master Stag</Text>
                <Text style={styles.upgradeSubtitle}>
                  Unlimited scans • Premium features
                </Text>
              </View>
            </View>
            <Button
              title="$9.99/month"
              onPress={handleUpgrade}
              loading={upgradeLoading}
              style={styles.upgradeButton}
            />
          </Card>
        )}

        {/* Menu Items */}
        <View style={styles.menuContainer}>
          {menuItems.map((item, index) => (
            <TouchableOpacity
              key={index}
              style={styles.menuItem}
              onPress={item.onPress}
              activeOpacity={0.7}
            >
              <View style={styles.menuIcon}>
                <item.icon size={20} color={colors.primary} />
              </View>
              <View style={styles.menuContent}>
                <Text style={styles.menuTitle}>{item.title}</Text>
                <Text style={styles.menuSubtitle}>{item.subtitle}</Text>
              </View>
              {item.badge ? (
                <Badge text={item.badge} variant="harvest" size="small" />
              ) : (
                <ChevronRight size={20} color={colors.textMuted} />
              )}
            </TouchableOpacity>
          ))}
        </View>

        {/* Sign Out Button */}
        <TouchableOpacity style={styles.signOutButton} onPress={handleLogout}>
          <LogOut size={20} color={colors.error} />
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>

        {/* Footer */}
        <Text style={styles.footer}>
          Iron Stag v1.0.0 • Forged in Asgard
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
  header: {
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  avatarContainer: {
    position: 'relative',
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: colors.primary,
  },
  avatarText: {
    fontSize: 32,
    fontWeight: '700',
    color: colors.primary,
  },
  crownBadge: {
    position: 'absolute',
    bottom: 0,
    right: -4,
    backgroundColor: colors.backgroundCard,
    borderRadius: 12,
    padding: 4,
    borderWidth: 2,
    borderColor: colors.primary,
  },
  userName: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
    marginTop: spacing.md,
  },
  userEmail: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  tierBadge: {
    marginTop: spacing.md,
  },
  statsCard: {
    marginBottom: spacing.md,
  },
  statRow: {
    flexDirection: 'row',
    alignItems: 'center',
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
  statLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },
  statDivider: {
    width: 1,
    height: 40,
    backgroundColor: colors.border,
  },
  upgradeCard: {
    marginBottom: spacing.md,
    backgroundColor: 'rgba(200, 162, 74, 0.1)',
    borderWidth: 1,
    borderColor: colors.primaryDark,
  },
  upgradeContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  upgradeText: {
    flex: 1,
  },
  upgradeTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  upgradeSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  upgradeButton: {
    width: '100%',
  },
  menuContainer: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
    marginBottom: spacing.lg,
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
    backgroundColor: 'rgba(200, 162, 74, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  menuContent: {
    flex: 1,
  },
  menuTitle: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.textPrimary,
  },
  menuSubtitle: {
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 2,
  },
  signOutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
    marginBottom: spacing.lg,
  },
  signOutText: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.error,
  },
  footer: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
  },
  authRequired: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  authTitle: {
    fontSize: 24,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  authText: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
});
