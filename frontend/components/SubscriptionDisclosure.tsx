import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  ScrollView,
  TouchableOpacity,
  Platform,
  Linking,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { X, Check, AlertCircle } from 'lucide-react-native';
import { Button } from './Button';
import { colors, spacing, borderRadius } from '../constants/theme';

interface SubscriptionDisclosureProps {
  visible: boolean;
  onClose: () => void;
  onConfirm: () => void;
  plan: 'monthly' | 'annual';
  loading?: boolean;
}

// Prices - These will be fetched from RevenueCat in production
const PRICES = {
  monthly: {
    price: '$4.99',
    period: 'month',
    description: 'Billed monthly',
  },
  annual: {
    price: '$39.99',
    period: 'year',
    description: 'Billed annually (Save 33%)',
  },
};

export function SubscriptionDisclosure({
  visible,
  onClose,
  onConfirm,
  plan,
  loading = false,
}: SubscriptionDisclosureProps) {
  const insets = useSafeAreaInsets();
  const planDetails = PRICES[plan];
  const isIOS = Platform.OS === 'ios';

  const features = [
    'Unlimited deer scans',
    'AI-powered age estimation',
    'Harvest recommendations',
    'Full scan history',
    'Priority support',
  ];

  const openPrivacyPolicy = () => {
    Linking.openURL('https://www.asgardsolution.io/iron-stag/privacy');
  };

  const openTermsOfService = () => {
    Linking.openURL('https://www.asgardsolution.io/iron-stag/terms');
  };

  const openManageSubscriptions = () => {
    if (Platform.OS === 'ios') {
      Linking.openURL('https://apps.apple.com/account/subscriptions');
    } else if (Platform.OS === 'android') {
      Linking.openURL('https://play.google.com/store/account/subscriptions');
    }
  };

  // Platform-specific terms
  const getTerms = () => {
    if (isIOS) {
      return {
        paymentMethod: 'Apple ID account',
        storeName: 'Apple',
        settingsName: 'Apple ID Account Settings',
      };
    }
    return {
      paymentMethod: 'Google Play account',
      storeName: 'Google Play',
      settingsName: 'Google Play Store settings',
    };
  };

  const terms = getTerms();

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={[styles.container, { paddingBottom: insets.bottom + spacing.md }]}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.headerTitle}>Master Stag Subscription</Text>
            <TouchableOpacity style={styles.closeButton} onPress={onClose}>
              <X size={24} color={colors.textPrimary} />
            </TouchableOpacity>
          </View>

          <ScrollView 
            style={styles.content}
            showsVerticalScrollIndicator={false}
          >
            {/* Price Section */}
            <View style={styles.priceSection}>
              <Text style={styles.price}>{planDetails.price}</Text>
              <Text style={styles.period}>per {planDetails.period}</Text>
              <Text style={styles.billingNote}>{planDetails.description}</Text>
            </View>

            {/* Features */}
            <View style={styles.featuresSection}>
              <Text style={styles.sectionTitle}>What's Included:</Text>
              {features.map((feature, index) => (
                <View key={index} style={styles.featureRow}>
                  <Check size={18} color={colors.primary} />
                  <Text style={styles.featureText}>{feature}</Text>
                </View>
              ))}
            </View>

            {/* Subscription Terms - Store-specific */}
            <View style={styles.termsSection}>
              <View style={styles.termsHeader}>
                <AlertCircle size={18} color={colors.info} />
                <Text style={styles.termsSectionTitle}>Subscription Terms</Text>
              </View>

              <Text style={styles.termsText}>
                • <Text style={styles.termsBold}>Payment:</Text> Payment will be charged to your {terms.paymentMethod} at confirmation of purchase.
              </Text>

              <Text style={styles.termsText}>
                • <Text style={styles.termsBold}>Auto-Renewal:</Text> Subscription automatically renews unless auto-renew is turned off at least 24 hours before the end of the current period.
              </Text>

              <Text style={styles.termsText}>
                • <Text style={styles.termsBold}>Renewal Charge:</Text> Your account will be charged for renewal within 24 hours prior to the end of the current period at the cost of the chosen plan.
              </Text>

              <Text style={styles.termsText}>
                • <Text style={styles.termsBold}>Manage Subscription:</Text> You can manage and cancel your subscription in your {terms.settingsName} after purchase.
              </Text>

              <Text style={styles.termsText}>
                • <Text style={styles.termsBold}>Free Trial:</Text> Any unused portion of a free trial period will be forfeited when purchasing a subscription.
              </Text>
            </View>

            {/* Links */}
            <View style={styles.linksSection}>
              <TouchableOpacity onPress={openTermsOfService}>
                <Text style={styles.linkText}>Terms of Service</Text>
              </TouchableOpacity>
              <Text style={styles.linkDivider}>•</Text>
              <TouchableOpacity onPress={openPrivacyPolicy}>
                <Text style={styles.linkText}>Privacy Policy</Text>
              </TouchableOpacity>
              <Text style={styles.linkDivider}>•</Text>
              <TouchableOpacity onPress={openManageSubscriptions}>
                <Text style={styles.linkText}>Manage Subscriptions</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>

          {/* Confirm Button */}
          <View style={styles.buttonSection}>
            <Button
              title={`Subscribe for ${planDetails.price}/${planDetails.period}`}
              onPress={onConfirm}
              loading={loading}
              size="large"
              style={styles.subscribeButton}
            />
            <Text style={styles.cancelNote}>
              Cancel anytime in your {terms.settingsName}
            </Text>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'flex-end',
  },
  container: {
    backgroundColor: colors.backgroundCard,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    maxHeight: '90%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  closeButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    paddingHorizontal: spacing.lg,
  },
  priceSection: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  price: {
    fontSize: 48,
    fontWeight: '700',
    color: colors.primary,
  },
  period: {
    fontSize: 18,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  billingNote: {
    fontSize: 14,
    color: colors.textMuted,
    marginTop: spacing.sm,
  },
  featuresSection: {
    paddingVertical: spacing.md,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  featureText: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  termsSection: {
    backgroundColor: colors.background,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginVertical: spacing.md,
  },
  termsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  termsSectionTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  termsText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
    marginBottom: spacing.sm,
  },
  termsBold: {
    fontWeight: '600',
    color: colors.textPrimary,
  },
  linksSection: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: spacing.md,
    flexWrap: 'wrap',
  },
  linkText: {
    fontSize: 13,
    color: colors.primary,
    textDecorationLine: 'underline',
  },
  linkDivider: {
    color: colors.textMuted,
    marginHorizontal: spacing.sm,
  },
  buttonSection: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  subscribeButton: {
    width: '100%',
  },
  cancelNote: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
});

export default SubscriptionDisclosure;
