import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Shield, Check, AlertTriangle } from 'lucide-react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { useAuthStore } from '../../stores/authStore';
import { authAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';

export default function DisclaimerScreen() {
  const insets = useSafeAreaInsets();
  const { updateUser } = useAuthStore();
  const [loading, setLoading] = useState(false);

  const handleAccept = async () => {
    setLoading(true);
    try {
      await authAPI.acceptDisclaimer(true);
      updateUser({ disclaimer_accepted: true });
      router.replace('/(tabs)');
    } catch (error) {
      Alert.alert('Error', 'Failed to save. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const guidelines = [
    'AI analysis is a tool to assist, not replace, your judgment as a hunter',
    'Always follow local hunting regulations and seasons',
    'Practice ethical shot selection and wildlife conservation',
    'Respect private property and obtain proper permissions',
    'Never harvest deer solely based on AI recommendations',
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.iconContainer}>
          <Shield size={64} color={colors.primary} />
        </View>

        <Text style={styles.title}>Ethical Hunting Disclaimer</Text>
        <Text style={styles.subtitle}>
          Before using Iron Stag, please read and accept our commitment to ethical hunting.
        </Text>

        <Card style={styles.warningCard}>
          <View style={styles.warningHeader}>
            <AlertTriangle size={24} color={colors.warning} />
            <Text style={styles.warningTitle}>Important Notice</Text>
          </View>
          <Text style={styles.warningText}>
            Iron Stag uses AI to estimate deer age and provide harvest recommendations. 
            These are estimates only and should never be the sole factor in your harvest decision. 
            You are responsible for all hunting decisions and must comply with all applicable laws.
          </Text>
        </Card>

        <Text style={styles.sectionTitle}>By using Iron Stag, you agree to:</Text>

        {guidelines.map((guideline, index) => (
          <View key={index} style={styles.guidelineItem}>
            <View style={styles.checkIcon}>
              <Check size={16} color={colors.harvest} />
            </View>
            <Text style={styles.guidelineText}>{guideline}</Text>
          </View>
        ))}

        <View style={styles.buttonContainer}>
          <Button
            title="I Accept & Understand"
            onPress={handleAccept}
            loading={loading}
            size="large"
            style={styles.acceptButton}
          />
          <Text style={styles.footerText}>
            By accepting, you acknowledge that you have read and understood these guidelines.
          </Text>
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
  scrollContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  iconContainer: {
    alignItems: 'center',
    marginVertical: spacing.xl,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: spacing.xl,
  },
  warningCard: {
    backgroundColor: 'rgba(255, 193, 7, 0.1)',
    borderWidth: 1,
    borderColor: colors.warning,
    marginBottom: spacing.xl,
  },
  warningHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  warningTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.warning,
  },
  warningText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },
  guidelineItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
  },
  checkIcon: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.harvestBg,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  guidelineText: {
    flex: 1,
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  buttonContainer: {
    marginTop: spacing.xl,
  },
  acceptButton: {
    width: '100%',
  },
  footerText: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.md,
    lineHeight: 18,
  },
});
