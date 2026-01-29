import React, { useState, useEffect, useCallback } from 'react';
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
  Modal,
  Platform,
  KeyboardAvoidingView,
  BackHandler,
} from 'react-native';
import { router, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Picker } from '@react-native-picker/picker';
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
  Pencil,
  AlertCircle,
  MessageSquare,
} from 'lucide-react-native';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { LabelFeedbackModal } from '../../components/LabelFeedbackModal';
import { ScanResultSkeleton } from '../../components/Skeleton';
import { useImageStore } from '../../stores/imageStore';
import { scanAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { format, differenceInDays } from 'date-fns';

// ============ CONFIDENCE CALIBRATION CONSTANTS ============
// Cap confidence at this value when age is uncertain/unknown
const UNCERTAIN_AGE_CONFIDENCE_CAP = 60;

interface ScanResult {
  id: string;
  local_image_id: string;
  deer_age: number | null;
  deer_type: string | null;
  deer_sex: string | null;
  antler_points: number | null;
  antler_points_left: number | null;
  antler_points_right: number | null;
  body_condition: string | null;
  confidence: number | null;
  recommendation: string | null;
  reasoning: string | null;
  notes: string | null;
  created_at: string;
  // Cloud image storage (R2) - for cross-device access
  image_url?: string | null;
}

// ============ CONFIDENCE & AGE UNCERTAINTY HELPERS ============

/**
 * Check if the age is uncertain/unknown
 */
function isAgeUncertain(age: number | null | undefined): boolean {
  return age === null || age === undefined || age === 0;
}

/**
 * Get display-calibrated confidence value
 */
function getCalibratedConfidence(rawConfidence: number | null, age: number | null): number {
  const confidence = rawConfidence || 0;
  
  if (isAgeUncertain(age)) {
    return Math.min(confidence, UNCERTAIN_AGE_CONFIDENCE_CAP);
  }
  
  return confidence;
}

/**
 * Get age display text with uncertainty handling
 */
function getAgeDisplayText(age: number | null): string {
  if (isAgeUncertain(age)) {
    return 'Uncertain';
  }
  return `${age} years`;
}

const DEER_TYPES = ['Whitetail', 'Mule Deer', 'Elk', 'Red Deer', 'Fallow Deer', 'Axis Deer', 'Unknown'];
const DEER_SEX_OPTIONS = ['Buck', 'Doe', 'Unknown'];

export default function ScanResultScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { getImage, deleteImage } = useImageStore();

  const [scan, setScan] = useState<ScanResult | null>(null);
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState('');
  
  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editDeerSex, setEditDeerSex] = useState<string>('');
  const [editDeerType, setEditDeerType] = useState<string>('');
  const [editPointsLeft, setEditPointsLeft] = useState<string>('');
  const [editPointsRight, setEditPointsRight] = useState<string>('');
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);
  
  // Feedback modal state (Phase 2 Empirical Calibration)
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [hasLabel, setHasLabel] = useState(false);
  const [labelCheckDone, setLabelCheckDone] = useState(false);

  useEffect(() => {
    loadScan();
  }, [id]);

  // Handle Android hardware back button - navigate to scan tab instead of back through stack
  useFocusEffect(
    useCallback(() => {
      const onBackPress = () => {
        // Navigate to scan tab using replace to avoid stuck states
        router.replace('/(tabs)/scan');
        return true; // Prevent default back behavior
      };

      // Only add listener on Android
      if (Platform.OS === 'android') {
        BackHandler.addEventListener('hardwareBackPress', onBackPress);
        return () => BackHandler.removeEventListener('hardwareBackPress', onBackPress);
      }
      return undefined;
    }, [])
  );
  const loadScan = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const response = await scanAPI.getScan(id);
      setScan(response.data);
      setNotes(response.data.notes || '');

      // Try to get local image first, fall back to cloud URL (R2)
      if (response.data.local_image_id) {
        const uri = await getImage(response.data.local_image_id);
        if (uri) {
          setImageUri(uri);
        } else if (response.data.image_url) {
          // Local image not found, use cloud URL (cross-device access)
          setImageUri(response.data.image_url);
        }
      } else if (response.data.image_url) {
        // No local image ID, use cloud URL directly
        setImageUri(response.data.image_url);
      }
      
      // Check if scan already has a label (for feedback feature)
      try {
        const labelResponse = await scanAPI.getLabel(id);
        setHasLabel(!!labelResponse.data);
      } catch {
        setHasLabel(false);
      }
      setLabelCheckDone(true);
    } catch (error) {
      console.error('Failed to load scan:', error);
      Alert.alert('Error', 'Failed to load scan details');
    } finally {
      setLoading(false);
    }
  };
  
  // Check if scan is eligible for feedback (7+ days old)
  const isFeedbackEligible = (): boolean => {
    if (!scan || hasLabel) return false;
    const scanDate = new Date(scan.created_at);
    const daysSinceScan = differenceInDays(new Date(), scanDate);
    return daysSinceScan >= 7;
  };
  
  const handleLabelSubmitted = () => {
    setHasLabel(true);
  };

  const handleDelete = () => {
    Alert.alert(
      'Delete Scan',
      'Are you sure you want to delete this scan? This action cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await scanAPI.deleteScan(scan!.id);
              if (scan?.local_image_id) {
                await deleteImage(scan.local_image_id);
              }
              router.replace('/(tabs)/history');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete scan');
            }
          },
        },
      ]
    );
  };

  const handleSaveNotes = async () => {
    try {
      await scanAPI.updateScan(scan!.id, { notes });
      setScan((prev) => (prev ? { ...prev, notes } : null));
      setEditingNotes(false);
      Alert.alert('Success', 'Notes saved');
    } catch (error) {
      Alert.alert('Error', 'Failed to save notes');
    }
  };

  const openEditModal = () => {
    if (!scan) return;
    setEditDeerSex(scan.deer_sex || '');
    setEditDeerType(scan.deer_type || '');
    setEditPointsLeft(scan.antler_points_left?.toString() || '');
    setEditPointsRight(scan.antler_points_right?.toString() || '');
    setShowEditModal(true);
  };

  const handleSubmitEdit = async () => {
    if (!scan) return;
    
    setIsSubmittingEdit(true);
    try {
      // Prepare edit data
      const editData: any = {};
      
      if (editDeerSex && editDeerSex !== scan.deer_sex) {
        editData.deer_sex = editDeerSex;
      }
      if (editDeerType && editDeerType !== scan.deer_type) {
        editData.deer_type = editDeerType;
      }
      if (editPointsLeft !== '') {
        editData.antler_points_left = parseInt(editPointsLeft, 10);
      }
      if (editPointsRight !== '') {
        editData.antler_points_right = parseInt(editPointsRight, 10);
      }
      
      // Include image for re-analysis if available
      if (imageUri) {
        // Convert image URI to base64
        try {
          const response = await fetch(imageUri);
          const blob = await response.blob();
          const reader = new FileReader();
          const base64Promise = new Promise<string>((resolve) => {
            reader.onloadend = () => {
              const base64 = reader.result as string;
              resolve(base64);
            };
            reader.readAsDataURL(blob);
          });
          editData.image_base64 = await base64Promise;
        } catch (imgError) {
          console.log('Could not include image for re-analysis:', imgError);
          // Continue without image - will just update fields
        }
      }
      
      const response = await scanAPI.editScan(scan.id, editData);
      setScan(response.data);
      setShowEditModal(false);
      Alert.alert('Success', 'Scan updated successfully');
    } catch (error) {
      console.error('Failed to update scan:', error);
      Alert.alert('Error', 'Failed to update scan');
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.replace('/(tabs)/scan')}>
            <ArrowLeft size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.title}>Scan Results</Text>
          <View style={{ width: 24 }} />
        </View>
        
        {/* Skeleton loading state */}
        <ScanResultSkeleton />
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

  // Build analysis data with left/right antler points
  // Apply confidence calibration for uncertain ages
  const ageIsUncertain = isAgeUncertain(scan.deer_age);
  const displayConfidence = getCalibratedConfidence(scan.confidence, scan.deer_age);
  const ageDisplayText = getAgeDisplayText(scan.deer_age);
  
  const analysisData = [
    { 
      label: 'Age Estimate', 
      value: ageDisplayText,
      isUncertain: ageIsUncertain,
    },
    { label: 'Deer Type', value: scan.deer_type || 'Unknown' },
    { label: 'Sex', value: scan.deer_sex || 'Unknown' },
    { label: 'Antler Points (Total)', value: scan.antler_points ? `${scan.antler_points} pts` : 'N/A' },
    { label: 'Left Antler', value: scan.antler_points_left !== null ? `${scan.antler_points_left} pts` : 'N/A' },
    { label: 'Right Antler', value: scan.antler_points_right !== null ? `${scan.antler_points_right} pts` : 'N/A' },
    { label: 'Body Condition', value: scan.body_condition || 'Unknown' },
    { 
      label: 'Model Confidence', 
      value: `${displayConfidence}%`,
      isUncertain: ageIsUncertain,
      helpText: ageIsUncertain ? 'Capped due to age uncertainty' : undefined,
    },
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
          <TouchableOpacity style={styles.headerAction} onPress={openEditModal}>
            <Pencil size={20} color={colors.primary} />
          </TouchableOpacity>
          <TouchableOpacity style={styles.headerAction} onPress={handleDelete}>
            <Trash2 size={20} color={colors.error} />
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xl }]}
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
          <View style={styles.summaryRow}>
            <Text style={[styles.summarySubtitle, ageIsUncertain && styles.summarySubtitleUncertain]}>
              Est. Age: {ageDisplayText}
            </Text>
            {ageIsUncertain && (
              <AlertCircle size={14} color={colors.textMuted} style={styles.uncertainIconSmall} />
            )}
          </View>
          {scan.antler_points !== null && (
            <Text style={styles.summarySubtitle}>
              {scan.antler_points} points
              {(scan.antler_points_left !== null || scan.antler_points_right !== null) && 
                ` (${scan.antler_points_left || 0}L / ${scan.antler_points_right || 0}R)`}
            </Text>
          )}
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

        {/* Feedback Section (Phase 2 Empirical Calibration) */}
        {labelCheckDone && (
          <View style={styles.feedbackSection}>
            {hasLabel ? (
              <View style={styles.feedbackSubmitted}>
                <Check size={16} color={colors.harvest} />
                <Text style={styles.feedbackSubmittedText}>Feedback submitted — thanks!</Text>
              </View>
            ) : isFeedbackEligible() ? (
              <TouchableOpacity 
                style={styles.feedbackButton}
                onPress={() => setShowFeedbackModal(true)}
              >
                <MessageSquare size={18} color={colors.primary} />
                <Text style={styles.feedbackButtonText}>How did this estimate hold up?</Text>
              </TouchableOpacity>
            ) : null}
          </View>
        )}

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

      {/* Edit Modal */}
      <Modal
        visible={showEditModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowEditModal(false)}
      >
        <KeyboardAvoidingView 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Edit Analysis</Text>
              <TouchableOpacity onPress={() => setShowEditModal(false)}>
                <X size={24} color={colors.textPrimary} />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody}>
              {/* Deer Sex */}
              <Text style={styles.inputLabel}>Deer Sex</Text>
              <View style={styles.pickerContainer}>
                <Picker
                  selectedValue={editDeerSex}
                  onValueChange={(value) => setEditDeerSex(value)}
                  style={styles.picker}
                  dropdownIconColor={colors.textPrimary}
                >
                  <Picker.Item label="Select..." value="" />
                  {DEER_SEX_OPTIONS.map((sex) => (
                    <Picker.Item key={sex} label={sex} value={sex} />
                  ))}
                </Picker>
              </View>

              {/* Deer Type */}
              <Text style={styles.inputLabel}>Deer Type</Text>
              <View style={styles.pickerContainer}>
                <Picker
                  selectedValue={editDeerType}
                  onValueChange={(value) => setEditDeerType(value)}
                  style={styles.picker}
                  dropdownIconColor={colors.textPrimary}
                >
                  <Picker.Item label="Select..." value="" />
                  {DEER_TYPES.map((type) => (
                    <Picker.Item key={type} label={type} value={type} />
                  ))}
                </Picker>
              </View>

              {/* Antler Points Left */}
              <Text style={styles.inputLabel}>Left Antler Points</Text>
              <TextInput
                style={styles.textInput}
                value={editPointsLeft}
                onChangeText={setEditPointsLeft}
                placeholder="e.g., 4"
                placeholderTextColor={colors.textMuted}
                keyboardType="numeric"
              />

              {/* Antler Points Right */}
              <Text style={styles.inputLabel}>Right Antler Points</Text>
              <TextInput
                style={styles.textInput}
                value={editPointsRight}
                onChangeText={setEditPointsRight}
                placeholder="e.g., 5"
                placeholderTextColor={colors.textMuted}
                keyboardType="numeric"
              />

              <Text style={styles.editNote}>
                Your corrections will be used to re-analyze this deer with updated information.
              </Text>
            </ScrollView>

            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => setShowEditModal(false)}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.submitButton, isSubmittingEdit && styles.disabledButton]}
                onPress={handleSubmitEdit}
                disabled={isSubmittingEdit}
              >
                {isSubmittingEdit ? (
                  <ActivityIndicator size="small" color={colors.white} />
                ) : (
                  <Text style={styles.submitButtonText}>Update & Re-analyze</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Feedback Modal (Phase 2 Empirical Calibration) */}
      <LabelFeedbackModal
        visible={showFeedbackModal}
        onClose={() => setShowFeedbackModal(false)}
        scanId={id || ''}
        predictedAge={scan?.deer_age || null}
        onLabelSubmitted={handleLabelSubmitted}
      />
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
    padding: spacing.xs,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  headerActions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  headerAction: {
    padding: spacing.xs,
  },
  scrollContent: {
    padding: spacing.md,
  },
  image: {
    width: '100%',
    height: 250,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.md,
  },
  imagePlaceholder: {
    width: '100%',
    height: 200,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  placeholderText: {
    color: colors.textMuted,
    marginTop: spacing.sm,
  },
  recommendationContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  recommendationBadge: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
  },
  harvestBadge: {
    backgroundColor: colors.harvest + '20',
  },
  passBadge: {
    backgroundColor: colors.pass + '20',
  },
  recommendationText: {
    fontSize: 16,
    fontWeight: 'bold',
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
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  summaryTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  summarySubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  summarySubtitleUncertain: {
    color: colors.textMuted,
    fontStyle: 'italic',
  },
  uncertainIconSmall: {
    marginLeft: 4,
  },
  insightCard: {
    marginBottom: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.primary + '10',
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
    lineHeight: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  dataGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: spacing.md,
  },
  dataItem: {
    width: '50%',
    paddingVertical: spacing.sm,
    paddingRight: spacing.sm,
  },
  dataLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: 2,
  },
  dataValue: {
    fontSize: 16,
    color: colors.textPrimary,
    fontWeight: '500',
  },
  notesSection: {
    marginBottom: spacing.md,
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
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    color: colors.textPrimary,
    fontSize: 14,
    minHeight: 100,
    textAlignVertical: 'top',
    borderWidth: 1,
    borderColor: colors.border,
  },
  notesText: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
  },
  // Feedback section (Phase 2 Empirical Calibration)
  feedbackSection: {
    marginBottom: spacing.md,
  },
  feedbackButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary + '10',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.primary + '30',
  },
  feedbackButtonText: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.primary,
  },
  feedbackSubmitted: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.harvest + '10',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
  },
  feedbackSubmittedText: {
    fontSize: 13,
    color: colors.harvest,
  },
  disclaimerCard: {
    backgroundColor: colors.warning + '10',
    padding: spacing.md,
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
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  errorText: {
    color: colors.error,
    fontSize: 16,
    marginBottom: spacing.md,
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: colors.background,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    maxHeight: '85%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  modalBody: {
    padding: spacing.md,
    maxHeight: 400,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
    marginTop: spacing.md,
  },
  pickerContainer: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  picker: {
    color: colors.textPrimary,
    height: 50,
  },
  textInput: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    color: colors.textPrimary,
    fontSize: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  editNote: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: spacing.lg,
    fontStyle: 'italic',
    textAlign: 'center',
  },
  modalFooter: {
    flexDirection: 'row',
    padding: spacing.md,
    gap: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surface,
    alignItems: 'center',
  },
  cancelButtonText: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '500',
  },
  submitButton: {
    flex: 2,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.primary,
    alignItems: 'center',
  },
  submitButtonText: {
    color: colors.white,
    fontSize: 16,
    fontWeight: '600',
  },
  disabledButton: {
    opacity: 0.6,
  },
});
