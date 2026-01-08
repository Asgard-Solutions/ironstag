import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ChevronDown, ChevronUp, BookOpen, Target, Shield, Trees } from 'lucide-react-native';
import { Card } from '../../components/Card';
import { learnAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';

interface ContentItem {
  title: string;
  description: string;
}

interface Section {
  id: string;
  title: string;
  content: ContentItem[];
}

const iconMap: Record<string, any> = {
  aging: Target,
  ethics: Shield,
  management: Trees,
};

export default function LearnScreen() {
  const insets = useSafeAreaInsets();
  const [sections, setSections] = useState<Section[]>([]);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadContent();
  }, []);

  const loadContent = async () => {
    try {
      const response = await learnAPI.getContent();
      setSections(response.data.sections);
      // Expand first section by default
      if (response.data.sections.length > 0) {
        setExpandedSections(new Set([response.data.sections[0].id]));
      }
    } catch (error) {
      console.error('Failed to load learn content:', error);
    } finally {
      setLoading(false);
    }
  };

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

  if (loading) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <BookOpen size={32} color={colors.primary} />
          <Text style={styles.title}>Learn</Text>
          <Text style={styles.subtitle}>
            Master the art of ethical deer hunting and wildlife management
          </Text>
        </View>

        {/* Sections */}
        {sections.map((section) => {
          const Icon = iconMap[section.id] || BookOpen;
          const isExpanded = expandedSections.has(section.id);

          return (
            <View key={section.id} style={styles.sectionContainer}>
              <TouchableOpacity
                style={styles.sectionHeader}
                onPress={() => toggleSection(section.id)}
                activeOpacity={0.8}
              >
                <View style={styles.sectionTitleRow}>
                  <View style={styles.sectionIcon}>
                    <Icon size={24} color={colors.primary} />
                  </View>
                  <Text style={styles.sectionTitle}>{section.title}</Text>
                </View>
                {isExpanded ? (
                  <ChevronUp size={24} color={colors.textMuted} />
                ) : (
                  <ChevronDown size={24} color={colors.textMuted} />
                )}
              </TouchableOpacity>

              {isExpanded && (
                <View style={styles.sectionContent}>
                  {section.content.map((item, index) => (
                    <Card key={index} style={styles.contentCard}>
                      <Text style={styles.contentTitle}>{item.title}</Text>
                      <Text style={styles.contentDescription}>
                        {item.description}
                      </Text>
                    </Card>
                  ))}
                </View>
              )}
            </View>
          );
        })}

        {/* Pro Tips */}
        <Card style={styles.proTipCard}>
          <Text style={styles.proTipTitle}>Pro Tip</Text>
          <Text style={styles.proTipText}>
            The best hunters are lifelong learners. Take time to study deer behavior, 
            practice ethical hunting, and contribute to conservation efforts in your area.
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
  centered: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
    marginTop: spacing.md,
  },
  subtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 20,
  },
  sectionContainer: {
    marginBottom: spacing.md,
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.md,
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  sectionIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(200, 162, 74, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  sectionContent: {
    padding: spacing.md,
    paddingTop: 0,
    gap: spacing.md,
  },
  contentCard: {
    backgroundColor: colors.background,
  },
  contentTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  contentDescription: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  proTipCard: {
    marginTop: spacing.lg,
    backgroundColor: 'rgba(200, 162, 74, 0.1)',
    borderWidth: 1,
    borderColor: colors.primaryDark,
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
