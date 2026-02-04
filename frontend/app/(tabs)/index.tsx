import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Camera, History, BookOpen, User, Target, XCircle, Sparkles } from 'lucide-react-native';
import { Card } from '../../components/Card';
import { Button } from '../../components/Button';
import { useAuthStore } from '../../stores/authStore';
import { scanAPI, subscriptionAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const { user, isAuthenticated } = useAuthStore();
  const [stats, setStats] = useState({ total_scans: 0, harvest_count: 0, pass_count: 0 });
  const [subscription, setSubscription] = useState({ tier: 'tracker', scans_remaining: 3, total_scans_used: 0, is_premium: false });
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    if (!isAuthenticated) return;
    try {
      const [statsRes, subRes] = await Promise.all([
        scanAPI.getStats(),
        subscriptionAPI.getStatus(),
      ]);
      setStats(statsRes.data);
      setSubscription(subRes.data);
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  useEffect(() => {
    loadData();
  }, [isAuthenticated]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  // Get status header content
  const getStatusHeader = () => {
    if (subscription.is_premium) {
      return {
        primary: 'Master Stag • Unlimited scans',
        secondary: "You're fully unlocked",
        isPremium: true,
      };
    }
    const scansText = subscription.scans_remaining === 1 
      ? '1 free scan remaining' 
      : `${subscription.scans_remaining} free scans remaining`;
    return {
      primary: `Tracker • ${scansText}`,
      secondary: 'Upgrade anytime for unlimited scans',
      isPremium: false,
    };
  };

  const statusHeader = getStatusHeader();

  const quickActions = [
    { icon: Camera, label: 'Scan Deer', route: '/(tabs)/scan', primary: true },
    { icon: History, label: 'History', route: '/(tabs)/history', primary: false },
    { icon: BookOpen, label: 'Learn', route: '/(tabs)/learn', primary: false },
    { icon: User, label: 'Profile', route: '/(tabs)/profile', primary: false },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xxl + 20 }]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.primary}
          />
        }
      >
        {/* Status Header */}
        <View style={styles.statusHeader}>
          <Text style={[
            styles.statusPrimary,
            statusHeader.isPremium && styles.statusPremium
          ]}>
            {statusHeader.primary}
          </Text>
          <Text style={styles.statusSecondary}>
            {statusHeader.secondary}
          </Text>
          {!subscription.is_premium && (
            <TouchableOpacity 
              style={styles.upgradeLink} 
              onPress={() => router.push('/(tabs)/profile')}
            >
              <Sparkles size={14} color={colors.primary} />
              <Text style={styles.upgradeLinkText}>Upgrade to Master Stag</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionsGrid}>
          {quickActions.map((action, index) => (
            <TouchableOpacity
              key={index}
              style={[styles.actionCard, action.primary && styles.primaryAction]}
              onPress={() => router.push(action.route as any)}
              activeOpacity={0.8}
            >
              <action.icon
                size={28}
                color={action.primary ? colors.background : colors.primary}
              />
              <Text style={[styles.actionLabel, action.primary && styles.primaryActionLabel]}>
                {action.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Activity Stats */}
        {isAuthenticated && stats.total_scans > 0 ? (
          <>
            <Text style={styles.sectionTitle}>Activity Stats</Text>
            <View style={styles.statsRow}>
              <Card style={styles.statCard}>
                <Target size={24} color={colors.primary} />
                <Text style={styles.statValue}>{stats.total_scans}</Text>
                <Text style={styles.statLabel}>Total Scans</Text>
              </Card>
              <Card style={styles.statCard}>
                <View style={[styles.statIcon, { backgroundColor: colors.harvestBg }]}>
                  <Text style={styles.harvestIcon}>H</Text>
                </View>
                <Text style={styles.statValue}>{stats.harvest_count}</Text>
                <Text style={styles.statLabel}>Harvest</Text>
              </Card>
              <Card style={styles.statCard}>
                <View style={[styles.statIcon, { backgroundColor: colors.passBg }]}>
                  <XCircle size={20} color={colors.pass} />
                </View>
                <Text style={styles.statValue}>{stats.pass_count}</Text>
                <Text style={styles.statLabel}>Pass</Text>
              </Card>
            </View>
          </>
        ) : (
          <Card style={styles.welcomeCard}>
            <Text style={styles.welcomeTitle}>Welcome to Iron Stag!</Text>
            <Text style={styles.welcomeText}>
              Get started by scanning your first deer. Our AI will analyze the image and provide
              age estimates and harvest recommendations.
            </Text>
            <Button
              title="Scan Your First Deer"
              onPress={() => router.push('/(tabs)/scan')}
              style={styles.welcomeButton}
            />
          </Card>
        )}

        {/* Tips */}
        <Card style={styles.tipCard}>
          <Text style={styles.tipTitle}>Pro Tip</Text>
          <Text style={styles.tipText}>
            For best results, capture clear photos showing the deer's body profile. 
            Side angles work best for accurate age estimation.
          </Text>
        </Card>
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
  statusHeader: {
    marginBottom: spacing.lg,
  },
  statusPrimary: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  statusPremium: {
    color: colors.primary,
  },
  statusSecondary: {
    fontSize: 13,
    color: colors.textMuted,
  },
  upgradeLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  upgradeLinkText: {
    fontSize: 13,
    fontWeight: '500',
    color: colors.primary,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  actionCard: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    gap: spacing.sm,
  },
  primaryAction: {
    backgroundColor: colors.primary,
  },
  actionLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textPrimary,
  },
  primaryActionLabel: {
    color: colors.background,
  },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    padding: spacing.md,
  },
  statIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  harvestIcon: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.harvest,
  },
  statValue: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  statLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },
  welcomeCard: {
    marginBottom: spacing.lg,
    alignItems: 'center',
  },
  welcomeTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  welcomeText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.md,
  },
  welcomeButton: {
    width: '100%',
  },
  tipCard: {
    backgroundColor: 'rgba(200, 162, 74, 0.1)',
    borderWidth: 1,
    borderColor: colors.primaryDark,
  },
  tipTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary,
    marginBottom: spacing.xs,
  },
  tipText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
  },
});
