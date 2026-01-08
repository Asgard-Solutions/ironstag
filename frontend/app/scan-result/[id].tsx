import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Image,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  ArrowLeft,
  Share2,
  Trash2,
  Edit3,
  Check,
  X,
  Target,
  Calendar,
  AlertTriangle,
} from 'lucide-react-native';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { useImageStore } from '../../stores/imageStore';
import { scanAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { format } from 'date-fns';

interface ScanResult {
  id: string;
  local_image_id: string;
  deer_age: number | null;
  deer_type: string | null;
  deer_sex: string | null;
  antler_points: number | null;
  body_condition: string | null;
  confidence: number | null;
  recommendation: string | null;
  reasoning: string | null;
  notes: string | null;
  created_at: string;
}

export default function ScanResultScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { getImage, deleteImage } = useImageStore();

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState('');

  useEffect(() => {
    loadScan();
  }, [id]);

  const loadScan = async () => {
    if (!id) return;
    try {
      const response = await scanAPI.getScan(id);
      setScan(response.data);
      setNotes(response.data.notes || '');
      
      // Load the image from local storage
      if (response.data.local_image_id) {
        const uri = await getImage(response.data.local_image_id);
        setImageUri(uri);
      }
    } catch (error) {
      console.error('Failed to load scan:', error);
      Alert.alert('Error', 'Failed to load scan details.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveNotes = async () => {
    if (!scan) return;
    try {
      await scanAPI.updateScan(scan.id, { notes });
      setScan({ ...scan, notes });
      setEditingNotes(false);
    } catch (error) {
      Alert.alert('Error', 'Failed to save notes.');
    }
  };

  const handleDelete = () => {
    Alert.alert(
      'Delete Scan',
      'Are you sure you want to delete this scan? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            if (!scan) return;
            try {
              await scanAPI.deleteScan(scan.id);
              await deleteImage(scan.local_image_id);
              router.back();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete scan.');
            }
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (!scan) {
    return (
      <View style={[styles.container, styles.centered]}>
        <Text style={styles.errorText}>Scan not found</Text>
        <Button title="Go Back" onPress={() => router.back()} />
      </View>
    );
  }

  const analysisData = [
    { label: 'Age Estimate', value: scan.deer_age ? `${scan.deer_age} years` : 'Unknown' },
    { label: 'Deer Type', value: scan.deer_type || 'Unknown' },
    { label: 'Sex', value: scan.deer_sex || 'Unknown' },
    { label: 'Antler Points', value: scan.antler_points ? `${scan.antler_points} pts` : 'N/A' },
    { label: 'Body Condition', value: scan.body_condition || 'Unknown' },
    { label: 'Confidence', value: scan.confidence ? `${scan.confidence}%` : 'N/A' },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.replace('/(tabs)/scan')}>
          <ArrowLeft size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Scan Result</Text>
        <View style={styles.headerActions}>
          <TouchableOpacity style={styles.headerAction} onPress={handleDelete}>
            <Trash2 size={20} color={colors.error} />
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Image */}
        {imageUri ? (
          <Image source={{ uri: imageUri }} style={styles.image} resizeMode="cover" />
        ) : (
          <View style={styles.imagePlaceholder}>
            <Target size={48} color={colors.textMuted} />
            <Text style={styles.placeholderText}>Image not available locally</Text>
          </View>
        )}

        {/* Recommendation Badge */}
        <View style={styles.recommendationContainer}>
          <View
            style={[
              styles.recommendationBadge,
              scan.recommendation === 'HARVEST'
                ? styles.harvestBadge
                : styles.passBadge,
            ]}
          >
            <Text
              style={[
                styles.recommendationText,
                scan.recommendation === 'HARVEST'
                  ? styles.harvestText
                  : styles.passText,
              ]}
            >
              {scan.recommendation || 'UNKNOWN'}
            </Text>
          </View>
          <View style={styles.dateContainer}>
            <Calendar size={14} color={colors.textMuted} />
            <Text style={styles.dateText}>
              {format(new Date(scan.created_at), 'MMM d, yyyy h:mm a')}
            </Text>
          </View>
        </View>

        {/* Quick Summary */}
        <Card style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>
            {scan.deer_type || 'Unknown Deer'} • {scan.deer_sex || 'Unknown'}
          </Text>
          <Text style={styles.summarySubtitle}>
            Est. Age: {scan.deer_age || '?'} years
            {scan.antler_points && ` • ${scan.antler_points} points`}
          </Text>
        </Card>

        {/* AI Insight */}
        {scan.reasoning && (
          <Card style={styles.insightCard}>
            <View style={styles.insightHeader}>
              <Target size={20} color={colors.primary} />
              <Text style={styles.insightTitle}>AI Analysis</Text>
            </View>
            <Text style={styles.insightText}>{scan.reasoning}</Text>
          </Card>
        )}

        {/* Analysis Data Grid */}
        <Text style={styles.sectionTitle}>Analysis Details</Text>
        <View style={styles.dataGrid}>
          {analysisData.map((item, index) => (
            <View key={index} style={styles.dataItem}>
              <Text style={styles.dataLabel}>{item.label}</Text>
              <Text style={styles.dataValue}>{item.value}</Text>
            </View>
          ))}
        </View>

        {/* Notes Section */}
        <View style={styles.notesSection}>
          <View style={styles.notesHeader}>
            <Text style={styles.sectionTitle}>Notes</Text>
            {!editingNotes ? (
              <TouchableOpacity onPress={() => setEditingNotes(true)}>
                <Edit3 size={18} color={colors.primary} />
              </TouchableOpacity>
            ) : (
              <View style={styles.notesActions}>
                <TouchableOpacity onPress={() => setEditingNotes(false)}>
                  <X size={20} color={colors.textMuted} />
                </TouchableOpacity>
                <TouchableOpacity onPress={handleSaveNotes}>
                  <Check size={20} color={colors.harvest} />
                </TouchableOpacity>
              </View>
            )}
          </View>
          {editingNotes ? (
            <TextInput
              style={styles.notesInput}
              value={notes}
              onChangeText={setNotes}
              placeholder="Add notes about this scan..."
              placeholderTextColor={colors.textMuted}
              multiline
              numberOfLines={4}
            />
          ) : (
            <Text style={styles.notesText}>
              {scan.notes || 'No notes added. Tap the edit icon to add notes.'}
            </Text>
          )}
        </View>

        {/* Disclaimer */}
        <Card style={styles.disclaimerCard}>
          <View style={styles.disclaimerHeader}>
            <AlertTriangle size={18} color={colors.warning} />
            <Text style={styles.disclaimerTitle}>Remember</Text>
          </View>
          <Text style={styles.disclaimerText}>
            AI analysis is a tool to assist your judgment, not replace it. Always follow
            local regulations, practice ethical hunting, and make decisions based on
            multiple factors.
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backButton: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'flex-start',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  headerActions: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  headerAction: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollContent: {
    paddingBottom: spacing.xxl,
  },
  image: {
    width: '100%',
    height: 300,
    backgroundColor: colors.backgroundCard,
  },
  imagePlaceholder: {
    width: '100%',
    height: 200,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
  },
  placeholderText: {
    color: colors.textMuted,
    marginTop: spacing.sm,
  },
  recommendationContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.md,
  },
  recommendationBadge: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.full,
  },
  harvestBadge: {
    backgroundColor: colors.harvestBg,
  },
  passBadge: {
    backgroundColor: colors.passBg,
  },
  recommendationText: {
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: 1,
  },
  harvestText: {
    color: colors.harvest,
  },
  passText: {
    color: colors.pass,
  },
  dateContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  dateText: {
    color: colors.textMuted,
    fontSize: 12,
  },
  summaryCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    alignItems: 'center',
  },
  summaryTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  summarySubtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  insightCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    backgroundColor: 'rgba(200, 162, 74, 0.1)',
    borderWidth: 1,
    borderColor: colors.primaryDark,
  },
  insightHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  insightTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary,
  },
  insightText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    marginTop: spacing.md,
  },
  dataGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  dataItem: {
    width: '48%',
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  dataLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  dataValue: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  notesSection: {
    paddingHorizontal: spacing.md,
    marginTop: spacing.lg,
  },
  notesHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  notesActions: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  notesInput: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    color: colors.textPrimary,
    fontSize: 14,
    minHeight: 100,
    textAlignVertical: 'top',
  },
  notesText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  disclaimerCard: {
    marginHorizontal: spacing.md,
    marginTop: spacing.xl,
    backgroundColor: 'rgba(255, 193, 7, 0.1)',
    borderWidth: 1,
    borderColor: colors.warning,
  },
  disclaimerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  disclaimerTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.warning,
  },
  disclaimerText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  errorText: {
    fontSize: 18,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
  },
});
