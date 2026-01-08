import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Linking,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Database, Eye, Lock, ArrowRight } from 'lucide-react-native';
import { Card } from '../../components/Card';
import { useAuthStore } from '../../stores/authStore';
import { authAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';

export default function PrivacyScreen() {
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

  const sections = [
    {
      icon: Database,
      title: 'What We Collect',
      items: [
        'Email and name (for your account)',
        'Deer scan images and analysis results',
        'Subscription status',
        'App usage data',
      ],
    },
    {
      icon: Eye,
      title: 'How We Use It',
      items: [
        'Provide AI deer analysis',
        'Save your scan history',
        'Manage your subscription',
        'Improve our AI models (anonymized)',
        'Improve our service',
      ],
    },
    {
      icon: Lock,
      title: 'Your Control',
      items: [
        'We never sell your data',
        'You can delete your account anytime',
        'All data is encrypted and secure',
        'Request data export or deletion anytime',
      ],
    },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <Text style={styles.title}>Privacy & Data Usage</Text>
        <Text style={styles.subtitle}>How we collect and use your information</Text>

        {/* Sections */}
        {sections.map((section, index) => (
          <Card key={index} style={styles.sectionCard}>
            <View style={styles.sectionHeader}>
              <View style={styles.iconContainer}>
                <section.icon size={20} color={colors.primary} />
              </View>
              <Text style={styles.sectionTitle}>{section.title}</Text>
            </View>
            <View style={styles.itemList}>
              {section.items.map((item, itemIndex) => (
                <View key={itemIndex} style={styles.itemRow}>
                  <Text style={styles.bullet}>•</Text>
                  <Text style={styles.itemText}>{item}</Text>
                </View>
              ))}
            </View>
          </Card>
        ))}

        {/* Links */}
        <TouchableOpacity style={styles.linkButton}>
          <Text style={styles.linkText}>Read our full Privacy Policy</Text>
        </TouchableOpacity>

        <View style={styles.linksRow}>
          <TouchableOpacity>
            <Text style={styles.linkText}>Privacy Policy</Text>
          </TouchableOpacity>
          <Text style={styles.linkDivider}>•</Text>
          <TouchableOpacity>
            <Text style={styles.linkText}>Terms</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.agreementText}>
          By continuing, you agree to our Privacy Policy and Terms of Service
        </Text>
      </ScrollView>

      {/* Accept Button */}
      <View style={[styles.buttonContainer, { paddingBottom: insets.bottom + spacing.md }]}>
        <TouchableOpacity 
          style={[styles.acceptButton, loading && styles.acceptButtonDisabled]} 
          onPress={handleAccept}
          disabled={loading}
        >
          <Text style={styles.acceptButtonText}>
            {loading ? 'Saving...' : 'Accept & Continue'}
          </Text>
          {!loading && <ArrowRight size={20} color={colors.background} />}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0E1A14',
  },
  scrollContent: {
    padding: spacing.lg,
    paddingBottom: 100,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
    marginTop: spacing.lg,
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  sectionCard: {
    backgroundColor: colors.backgroundCard,
    marginBottom: spacing.md,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(200, 162, 74, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  itemList: {
    gap: spacing.xs,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  bullet: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  itemText: {
    flex: 1,
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  linkButton: {
    alignItems: 'center',
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  linkText: {
    fontSize: 14,
    color: colors.primary,
    textDecorationLine: 'underline',
  },
  linksRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  linkDivider: {
    color: colors.textMuted,
  },
  agreementText: {
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 20,
  },
  buttonContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: spacing.lg,
    backgroundColor: '#0E1A14',
  },
  acceptButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
  },
  acceptButtonDisabled: {
    opacity: 0.7,
  },
  acceptButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
});
