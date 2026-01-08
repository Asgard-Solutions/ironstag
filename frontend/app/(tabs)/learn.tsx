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
import { 
  ArrowLeft, 
  Calendar, 
  TrendingUp, 
  Award, 
  Target,
  ChevronDown, 
  ChevronUp, 
  BookOpen, 
  Shield, 
  Trees,
  Sparkles,
  Lock,
  AlertCircle,
} from 'lucide-react-native';
import { Card } from '../../components/Card';
import { colors, spacing, borderRadius } from '../../constants/theme';

interface AgeClass {
  age: string;
  title: string;
  icon: any;
  iconColor: string;
  description: string;
  recommendation: string;
  recommendationColor: string;
}

interface FieldIndicator {
  title: string;
  items: string[];
}

export default function LearnScreen() {
  const insets = useSafeAreaInsets();
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['aging']));

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const ageClasses: AgeClass[] = [
    {
      age: '1.5 years',
      title: 'Yearling',
      icon: Calendar,
      iconColor: '#4CAF50',
      description: 'Small body, thin neck, legs appear long for body size. Antlers typically spikes or small forks with minimal mass. Limited potential shown.',
      recommendation: 'PASS — ALLOW MATURATION FOR HERD QUALITY',
      recommendationColor: '#4CAF50',
    },
    {
      age: '2.5 years',
      title: 'Young Buck',
      icon: TrendingUp,
      iconColor: '#4CAF50',
      description: 'Medium body, moderate neck development, proportionate legs. Antlers developing but well below genetic potential. Shows promise but needs time.',
      recommendation: 'PASS — FUTURE HERD CONTRIBUTOR',
      recommendationColor: '#4CAF50',
    },
    {
      age: '3.5 years',
      title: 'Mature Buck',
      icon: Award,
      iconColor: '#9E9E9E',
      description: 'Full body mass, thick neck during rut, well-proportioned. Good antler development with 8+ points typical. Approaching peak potential.',
      recommendation: 'MANAGEMENT DECISION BASED ON GOALS',
      recommendationColor: '#9E9E9E',
    },
    {
      age: '4.5+ years',
      title: 'Trophy Class',
      icon: Target,
      iconColor: '#E53935',
      description: 'Large body, very thick neck, may show sagging belly. Maximum antler potential achieved with heavy mass and impressive spread. Prime specimen.',
      recommendation: 'HARVEST — IF MEETS YOUR CRITERIA',
      recommendationColor: '#C8A24A',
    },
  ];

  const fieldIndicators: FieldIndicator[] = [
    {
      title: 'Body Characteristics',
      items: [
        'Chest depth vs. leg length ratio',
        'Overall body mass and muscle tone',
        'Belly line (sagging indicates older age)',
        'Back line (swayed back on mature deer)',
      ],
    },
    {
      title: 'Neck Development',
      items: [
        'Thin, proportional neck = younger deer',
        'Thick, muscular neck during rut = mature',
        'Neck-to-chest angle at 90° = 4.5+ years',
        'Visible neck-shoulder separation',
      ],
    },
    {
      title: 'Antler Analysis',
      items: [
        'Main beam thickness and mass',
        'Tine length, spacing, and symmetry',
        'Overall spread and height',
        'Brow tine development',
      ],
    },
    {
      title: 'Behavioral Indicators',
      items: [
        'Mature bucks exhibit heightened caution',
        'Dominant body language and posture',
        'Peak breeding activity patterns',
        'Territorial marking behavior',
      ],
    },
  ];

  const ethicalGuidelines = [
    {
      title: 'Fair Chase Principles',
      description: 'Hunt in a manner that does not give the hunter improper advantage over game animals.',
    },
    {
      title: 'Clean Harvest',
      description: 'Practice regularly to ensure clean, ethical kills. Know your effective range.',
    },
    {
      title: 'Respect for the Animal',
      description: 'Use all usable parts of harvested game. Waste nothing and honor the animal.',
    },
    {
      title: 'Land Stewardship',
      description: 'Leave the land better than you found it. Practice habitat conservation.',
    },
  ];

  const wildlifeManagement = [
    {
      title: 'Age Structure',
      description: 'Healthy deer populations have balanced age structures. Passing on young bucks allows them to reach maturity.',
    },
    {
      title: 'Population Control',
      description: 'Doe harvest is crucial for population management. An overpopulated herd leads to habitat destruction.',
    },
    {
      title: 'Habitat Management',
      description: 'Quality deer management includes food plots, water sources, and cover.',
    },
    {
      title: 'Record Keeping',
      description: 'Track harvest data, trail camera photos, and observations for informed decisions.',
    },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <ArrowLeft size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.headerText}>
          <Text style={styles.title}>Aging Guide</Text>
          <Text style={styles.subtitle}>Learn to assess deer age in the field</Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Introduction */}
        <View style={styles.introCard}>
          <View style={styles.introAccent} />
          <Text style={styles.introText}>
            Aging deer on the hoof is a critical skill for ethical hunting and quality deer management. This guide provides field-tested indicators to help you make informed harvest decisions.
          </Text>
        </View>

        {/* Age Classes Section */}
        <Text style={styles.sectionTitle}>Age Classes</Text>
        {ageClasses.map((ageClass, index) => (
          <Card key={index} style={styles.ageCard}>
            <View style={styles.ageHeader}>
              <View style={[styles.ageIcon, { backgroundColor: `${ageClass.iconColor}20` }]}>
                <ageClass.icon size={20} color={ageClass.iconColor} />
              </View>
              <View style={styles.ageTitleContainer}>
                <Text style={styles.ageTitle}>{ageClass.age}</Text>
                <Text style={styles.ageSubtitle}>{ageClass.title}</Text>
              </View>
            </View>
            <Text style={styles.ageDescription}>{ageClass.description}</Text>
            <View style={[styles.recommendationBadge, { backgroundColor: `${ageClass.recommendationColor}15` }]}>
              <Text style={[styles.recommendationText, { color: ageClass.recommendationColor }]}>
                {ageClass.recommendation}
              </Text>
            </View>
          </Card>
        ))}

        {/* Premium Insight Card */}
        <Card style={styles.premiumCard}>
          <View style={styles.premiumHeader}>
            <View style={styles.premiumIconContainer}>
              <Sparkles size={20} color={colors.primary} />
            </View>
            <Text style={styles.premiumTitle}>Premium Insight</Text>
            <View style={styles.premiumBadge}>
              <Lock size={14} color={colors.textMuted} />
            </View>
          </View>
          <Text style={styles.premiumText}>
            Premium members get detailed body scoring breakdowns and advanced antler metrics that go beyond basic age estimation—including main beam measurements, tine positioning analysis, and comparative scoring against regional averages.
          </Text>
          <TouchableOpacity style={styles.upgradeButton}>
            <Text style={styles.upgradeButtonText}>Upgrade to Unlock</Text>
          </TouchableOpacity>
        </Card>

        {/* Field Indicators Section */}
        <Text style={styles.sectionTitle}>Field Indicators</Text>
        {fieldIndicators.map((indicator, index) => (
          <Card key={index} style={styles.indicatorCard}>
            <Text style={styles.indicatorTitle}>{indicator.title}</Text>
            {indicator.items.map((item, itemIndex) => (
              <View key={itemIndex} style={styles.indicatorRow}>
                <Text style={styles.bullet}>•</Text>
                <Text style={styles.indicatorItem}>{item}</Text>
              </View>
            ))}
          </Card>
        ))}

        {/* Premium Historical Tracking Card */}
        <Card style={styles.premiumCard}>
          <View style={styles.premiumHeader}>
            <View style={styles.premiumIconContainer}>
              <Lock size={20} color={colors.primary} />
            </View>
            <Text style={styles.premiumTitle}>Premium: Historical Tracking</Text>
            <View style={styles.premiumBadge}>
              <Lock size={14} color={colors.textMuted} />
            </View>
          </View>
          <Text style={styles.premiumText}>
            Track the same deer across multiple seasons. Premium members get year-over-year growth analysis, maturation predictions, and property-specific herd health metrics to support long-term management goals.
          </Text>
          <TouchableOpacity style={styles.upgradeButton}>
            <Text style={styles.upgradeButtonText}>Learn More</Text>
          </TouchableOpacity>
        </Card>

        {/* Ethical Reminder */}
        <Card style={styles.ethicalCard}>
          <View style={styles.ethicalHeader}>
            <AlertCircle size={18} color={colors.primary} />
            <Text style={styles.ethicalTitle}>Ethical Reminder</Text>
          </View>
          <Text style={styles.ethicalText}>
            AI analysis assists judgment—it doesn't replace field experience. Always verify with local regulations, consider property management goals, and make decisions that support sustainable hunting practices and herd health.
          </Text>
        </Card>

        {/* Ethical Hunting Guidelines */}
        <TouchableOpacity 
          style={styles.expandableSection}
          onPress={() => toggleSection('ethics')}
        >
          <View style={styles.expandableHeader}>
            <View style={styles.expandableIcon}>
              <Shield size={20} color={colors.primary} />
            </View>
            <Text style={styles.expandableTitle}>Ethical Hunting Guidelines</Text>
          </View>
          {expandedSections.has('ethics') ? (
            <ChevronUp size={24} color={colors.textMuted} />
          ) : (
            <ChevronDown size={24} color={colors.textMuted} />
          )}
        </TouchableOpacity>
        {expandedSections.has('ethics') && (
          <View style={styles.expandableContent}>
            {ethicalGuidelines.map((item, index) => (
              <Card key={index} style={styles.guidelineCard}>
                <Text style={styles.guidelineTitle}>{item.title}</Text>
                <Text style={styles.guidelineDescription}>{item.description}</Text>
              </Card>
            ))}
          </View>
        )}

        {/* Wildlife Management */}
        <TouchableOpacity 
          style={styles.expandableSection}
          onPress={() => toggleSection('management')}
        >
          <View style={styles.expandableHeader}>
            <View style={styles.expandableIcon}>
              <Trees size={20} color={colors.primary} />
            </View>
            <Text style={styles.expandableTitle}>Wildlife Management</Text>
          </View>
          {expandedSections.has('management') ? (
            <ChevronUp size={24} color={colors.textMuted} />
          ) : (
            <ChevronDown size={24} color={colors.textMuted} />
          )}
        </TouchableOpacity>
        {expandedSections.has('management') && (
          <View style={styles.expandableContent}>
            {wildlifeManagement.map((item, index) => (
              <Card key={index} style={styles.guidelineCard}>
                <Text style={styles.guidelineTitle}>{item.title}</Text>
                <Text style={styles.guidelineDescription}>{item.description}</Text>
              </Card>
            ))}
          </View>
        )}

        {/* Pro Tip */}
        <Card style={styles.proTipCard}>
          <Text style={styles.proTipTitle}>Pro Tip</Text>
          <Text style={styles.proTipText}>
            The best hunters are lifelong learners. Take time to study deer behavior, practice ethical hunting, and contribute to conservation efforts in your area.
          </Text>
        </Card>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0E1A14',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  headerText: {
    flex: 1,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
  },
  scrollContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl + 80,
  },
  introCard: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.xl,
    flexDirection: 'row',
    overflow: 'hidden',
  },
  introAccent: {
    width: 4,
    backgroundColor: colors.primary,
    marginRight: spacing.md,
    borderRadius: 2,
  },
  introText: {
    flex: 1,
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.md,
    marginTop: spacing.md,
  },
  ageCard: {
    backgroundColor: colors.backgroundCard,
    marginBottom: spacing.md,
  },
  ageHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  ageIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  ageTitleContainer: {
    flex: 1,
  },
  ageTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  ageSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  ageDescription: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: spacing.md,
  },
  recommendationBadge: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.sm,
  },
  recommendationText: {
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
    letterSpacing: 0.5,
  },
  premiumCard: {
    backgroundColor: 'rgba(200, 162, 74, 0.08)',
    borderWidth: 1,
    borderColor: colors.primary,
    marginBottom: spacing.md,
    marginTop: spacing.md,
  },
  premiumHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  premiumIconContainer: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(200, 162, 74, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.sm,
  },
  premiumTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary,
  },
  premiumBadge: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
  },
  premiumText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: spacing.md,
  },
  upgradeButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    alignSelf: 'flex-start',
  },
  upgradeButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.background,
  },
  indicatorCard: {
    backgroundColor: colors.backgroundCard,
    marginBottom: spacing.md,
  },
  indicatorTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  indicatorRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: spacing.xs,
  },
  bullet: {
    fontSize: 14,
    color: colors.primary,
    marginRight: spacing.sm,
    lineHeight: 22,
  },
  indicatorItem: {
    flex: 1,
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  ethicalCard: {
    backgroundColor: 'rgba(200, 162, 74, 0.08)',
    borderWidth: 1,
    borderColor: colors.primaryDark,
    marginBottom: spacing.lg,
    marginTop: spacing.md,
  },
  ethicalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  ethicalTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary,
  },
  ethicalText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  expandableSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  expandableHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  expandableIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(200, 162, 74, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: spacing.md,
  },
  expandableTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  expandableContent: {
    marginBottom: spacing.md,
  },
  guidelineCard: {
    backgroundColor: colors.background,
    marginBottom: spacing.sm,
  },
  guidelineTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  guidelineDescription: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  proTipCard: {
    backgroundColor: 'rgba(200, 162, 74, 0.1)',
    borderWidth: 1,
    borderColor: colors.primaryDark,
    marginTop: spacing.lg,
  },
  proTipTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary,
    marginBottom: spacing.sm,
  },
  proTipText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
});
