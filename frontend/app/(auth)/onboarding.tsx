import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { AlertCircle, Sparkles, Check, ArrowRight, Target } from 'lucide-react-native';
import { Card } from '../../components/Card';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { useAuthStore } from '../../stores/authStore';
import { authAPI } from '../../utils/api';
import { DEFAULT_HARVEST_AGE, HARVEST_AGE_OPTIONS } from '../../utils/ageEstimate';

export default function OnboardingScreen() {
  const insets = useSafeAreaInsets();
  const { user, updateUser } = useAuthStore();
  const [harvestAge, setHarvestAge] = useState<number>(user?.harvest_age_threshold ?? DEFAULT_HARVEST_AGE);

  const handleContinue = () => {
    if (harvestAge !== (user?.harvest_age_threshold ?? DEFAULT_HARVEST_AGE)) {
      updateUser({ harvest_age_threshold: harvestAge });
      // Non-blocking: hunters can always change this later in Profile
      authAPI.updateProfile({ harvest_age_threshold: harvestAge }).catch((error) =>
        console.error('Failed to save harvest age:', error)
      );
    }
    router.push('/(auth)/privacy');
  };

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* App Icon */}
        <View style={styles.iconContainer}>
          <View style={styles.appIcon}>
            <View style={styles.iconRing}>
              <View style={styles.iconRingInner}>
                <View style={styles.iconDot} />
              </View>
            </View>
          </View>
        </View>

        {/* Title */}
        <Text style={styles.title}>Iron Stag</Text>
        <Text style={styles.subtitle}>AI estimation tool for informational purposes only</Text>

        {/* Important Notice */}
        <Card style={styles.noticeCard}>
          <View style={styles.noticeHeader}>
            <AlertCircle size={20} color="#E67E22" />
            <Text style={styles.noticeTitle}>Important Notice</Text>
          </View>
          <Text style={styles.noticeText}>
            This app provides AI-generated estimations for informational purposes only. It does NOT provide professional advice. You are solely responsible for all hunting decisions.
          </Text>
        </Card>

        {/* Harvest Age */}
        <Card style={styles.harvestCard}>
          <View style={styles.noticeHeader}>
            <Target size={20} color={colors.primary} />
            <Text style={styles.harvestTitle}>Your Harvest Age</Text>
          </View>
          <Text style={styles.harvestText}>
            Deer this age or older are marked HARVEST. You can change this anytime in Profile.
          </Text>
          <View style={styles.harvestChips}>
            {HARVEST_AGE_OPTIONS.map((age) => {
              const selected = harvestAge === age;
              return (
                <TouchableOpacity
                  key={age}
                  testID={`onboarding-harvest-age-${age.toFixed(1)}`}
                  style={[styles.harvestChip, selected && styles.harvestChipSelected]}
                  onPress={() => setHarvestAge(age)}
                >
                  <Text style={[styles.harvestChipText, selected && styles.harvestChipTextSelected]}>
                    {age === 6.5 ? '6.5+' : age.toFixed(1)}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </Card>

        {/* Example Estimation */}
        <View style={styles.exampleSection}>
          <View style={styles.exampleHeader}>
            <Sparkles size={16} color={colors.primary} />
            <Text style={styles.exampleLabel}>EXAMPLE ESTIMATION</Text>
          </View>
          
          <Card style={styles.exampleCard}>
            <Text style={styles.exampleTitle}>See What You'll Get</Text>
            
            <View style={styles.exampleRow}>
              <Text style={styles.exampleKey}>Estimated Age</Text>
              <Text style={styles.exampleValue}>3.5 years</Text>
            </View>
            
            <View style={styles.divider} />
            
            <View style={styles.exampleRow}>
              <Text style={styles.exampleKey}>Confidence</Text>
              <Text style={styles.exampleConfidence}>87%</Text>
            </View>
            
            <View style={styles.insightBadge}>
              <Check size={16} color={colors.harvest} />
              <Text style={styles.insightText}>AI Insight: May Benefit from Growth</Text>
            </View>
            
            <Text style={styles.exampleFooter}>
              Get AI-generated estimations and insights for every deer you scan
            </Text>
          </Card>
        </View>
      </ScrollView>

      {/* Continue Button */}
      <View style={[styles.buttonContainer, { paddingBottom: insets.bottom + spacing.md }]}>
        <TouchableOpacity style={styles.continueButton} onPress={handleContinue}>
          <Text style={styles.continueButtonText}>Continue</Text>
          <ArrowRight size={20} color={colors.background} />
        </TouchableOpacity>
      </View>
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
    paddingBottom: 100,
  },
  iconContainer: {
    alignItems: 'center',
    marginTop: spacing.xl,
    marginBottom: spacing.lg,
  },
  appIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'transparent',
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  iconRing: {
    width: 50,
    height: 50,
    borderRadius: 25,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  iconRingInner: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  iconDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  noticeCard: {
    backgroundColor: colors.warningBg,
    marginBottom: spacing.xl,
  },
  noticeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  noticeTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#E67E22',
  },
  noticeText: {
    fontSize: 14,
    color: '#7D5A3C',
    lineHeight: 22,
  },
  harvestCard: {
    backgroundColor: colors.backgroundCard,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.xl,
  },
  harvestTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  harvestText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: spacing.md,
  },
  harvestChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  harvestChip: {
    minWidth: 56,
    minHeight: 44,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  harvestChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  harvestChipText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  harvestChipTextSelected: {
    color: colors.background,
  },
  exampleSection: {
    marginBottom: spacing.lg,
  },
  exampleHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    marginBottom: spacing.md,
  },
  exampleLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
    letterSpacing: 1,
  },
  exampleCard: {
    backgroundColor: colors.backgroundCard,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  exampleTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  exampleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
  },
  exampleKey: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  exampleValue: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  exampleConfidence: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
  },
  insightBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: 'rgba(76, 175, 80, 0.1)',
    borderWidth: 1,
    borderColor: colors.harvest,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginTop: spacing.md,
  },
  insightText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.harvest,
  },
  exampleFooter: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.md,
  },
  buttonContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: spacing.lg,
    backgroundColor: colors.background,
  },
  continueButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
  },
  continueButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
});
