import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  RefreshControl,
  Share,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Picker } from '@react-native-picker/picker';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import ViewShot from 'react-native-view-shot';
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
  ChevronRight,
  Shield,
  Eye,
} from 'lucide-react-native';
import { Card } from '../../components/Card';
import { Badge } from '../../components/Badge';
import { Button } from '../../components/Button';
import { LabelFeedbackModal } from '../../components/LabelFeedbackModal';
import { ScanResultSkeleton } from '../../components/Skeleton';
import { TagsEditor } from '../../components/TagsEditor';
import {
  ScanSummaryCard,
  getConfidenceLabel,
  parseReasoning,
} from '../../components/ScanSummaryCard';
import { useImageStore } from '../../stores/imageStore';
import { scanAPI } from '../../utils/api';
import { colors, spacing, borderRadius, typography, shadows } from '../../constants/theme';
import { format, differenceInDays } from 'date-fns';

// ============ CONFIDENCE CALIBRATION CONSTANTS ============
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
  image_url?: string | null;
  tags?: string[];
}

// ============ CONFIDENCE & AGE UNCERTAINTY HELPERS ============

function isAgeUncertain(age: number | null | undefined): boolean {
  return age === null || age === undefined || age === 0;
}

function getCalibratedConfidence(rawConfidence: number | null, age: number | null): number {
  const confidence = rawConfidence || 0;
  if (isAgeUncertain(age)) {
    return Math.min(confidence, UNCERTAIN_AGE_CONFIDENCE_CAP);
  }
  return confidence;
}

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
  const [refreshing, setRefreshing] = useState(false);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState('');
  const [isSharing, setIsSharing] = useState(false);

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editDeerSex, setEditDeerSex] = useState<string>('');
  const [editDeerType, setEditDeerType] = useState<string>('');
  const [editPointsLeft, setEditPointsLeft] = useState<string>('');
  const [editPointsRight, setEditPointsRight] = useState<string>('');
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);

  // Feedback modal state
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [hasLabel, setHasLabel] = useState(false);
  const [labelCheckDone, setLabelCheckDone] = useState(false);

  // Share card ref
  const shareCardRef = useRef<ViewShot>(null);

  useEffect(() => {
    loadScan();
  }, [id]);

  const loadScan = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const response = await scanAPI.getScan(id);
      setScan(response.data);
      setNotes(response.data.notes || '');

      if (response.data.local_image_id) {
        const uri = await getImage(response.data.local_image_id);
        if (uri) {
          setImageUri(uri);
        } else if (response.data.image_url) {
          setImageUri(response.data.image_url);
        }
      } else if (response.data.image_url) {
        setImageUri(response.data.image_url);
      }

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
      setRefreshing(false);
    }
  };

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadScan();
  }, [id]);

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

      if (imageUri) {
        try {
          let base64Image: string;

          if (imageUri.startsWith('http://') || imageUri.startsWith('https://')) {
            const response = await fetch(imageUri);
            const blob = await response.blob();
            const reader = new FileReader();
            base64Image = await new Promise<string>((resolve, reject) => {
              reader.onloadend = () => {
                const result = reader.result as string;
                resolve(result);
              };
              reader.onerror = reject;
              reader.readAsDataURL(blob);
            });
          } else {
            const base64Data = await FileSystem.readAsStringAsync(imageUri, {
              encoding: 'base64' as FileSystem.EncodingType,
            });
            base64Image = `data:image/jpeg;base64,${base64Data}`;
          }

          editData.image_base64 = base64Image;
          console.log('Image included for re-analysis, length:', base64Image.length);
        } catch (imgError) {
          console.log('Could not include image for re-analysis:', imgError);
          Alert.alert(
            'Image Not Available',
            'Unable to access the original image. The scan will be updated without re-analysis.',
            [{ text: 'OK' }]
          );
        }
      }

      if (editData.image_base64) {
        Alert.alert('Re-analyzing', 'Sending image to AI for new analysis...');
      }

      const response = await scanAPI.editScan(scan.id, editData);
      setScan(response.data);
      setShowEditModal(false);

      if (editData.image_base64) {
        Alert.alert('Success', 'Scan re-analyzed with your corrections!');
      } else {
        Alert.alert('Success', 'Scan details updated');
      }
    } catch (error: any) {
      console.error('Failed to update scan:', error);
      const message = error.response?.data?.detail || 'Failed to update scan';
      Alert.alert('Error', message);
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  // ────────── SHARE FEATURE ──────────
  const handleShare = async () => {
    if (!scan) return;
    setIsSharing(true);

    try {
      // Try to capture the share card as an image
      if (shareCardRef.current && typeof shareCardRef.current.capture === 'function') {
        const uri = await shareCardRef.current.capture();
        const isAvailable = await Sharing.isAvailableAsync();
        if (isAvailable && uri) {
          await Sharing.shareAsync(uri, {
            mimeType: 'image/png',
            dialogTitle: 'Share Iron Stag Result',
            UTI: 'public.png',
          });
          setIsSharing(false);
          return;
        }
      }
    } catch (captureError) {
      console.log('ViewShot capture failed, falling back to text share:', captureError);
    }

    // Fallback: text-based share
    try {
      const displayConfidence = getCalibratedConfidence(scan.confidence, scan.deer_age);
      const ageText = getAgeDisplayText(scan.deer_age);

      const shareText = [
        `Iron Stag Result`,
        ``,
        `RECOMMENDATION: ${scan.recommendation || 'UNKNOWN'}`,
        `Estimated Age: ${ageText}`,
        `Confidence: ${displayConfidence}%`,
        scan.deer_type ? `Type: ${scan.deer_type}` : null,
        scan.antler_points ? `Points: ${scan.antler_points}` : null,
        ``,
        `Analyzed with Iron Stag`,
      ]
        .filter(Boolean)
        .join('\n');

      await Share.share({
        message: shareText,
        title: 'Iron Stag Scan Result',
      });
    } catch (shareError) {
      if ((shareError as any)?.message !== 'User did not share') {
        Alert.alert('Share Failed', 'Unable to share this scan result.');
      }
    } finally {
      setIsSharing(false);
    }
  };

  // ────────── LOADING STATE ──────────
  if (loading) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <View style={styles.header}>
          <TouchableOpacity
            onPress={() => router.replace('/(tabs)/scan')}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            <ArrowLeft size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Scan Results</Text>
          <View style={{ width: 24 }} />
        </View>
        <ScanResultSkeleton />
      </View>
    );
  }

  if (!scan) {
    return (
      <View style={[styles.container, styles.centered]}>
        <Text style={styles.errorText}>Scan not found</Text>
        <Button title="Go Back" onPress={() => router.replace('/(tabs)/scan')} />
      </View>
    );
  }

  // ────────── DERIVED DATA ──────────
  const ageIsUncertain = isAgeUncertain(scan.deer_age);
  const displayConfidence = getCalibratedConfidence(scan.confidence, scan.deer_age);
  const ageDisplayText = getAgeDisplayText(scan.deer_age);
  const confLabel = getConfidenceLabel(displayConfidence);
  const { summary: reasoningSummary, cues: reasoningCues } = parseReasoning(scan.reasoning);

  const analysisData = [
    {
      label: 'Deer Type',
      value: scan.deer_type || 'Unknown',
    },
    {
      label: 'Sex',
      value: scan.deer_sex || 'Unknown',
    },
    {
      label: 'Antler Points',
      value: scan.antler_points ? `${scan.antler_points} pts` : 'N/A',
    },
    {
      label: 'Left / Right',
      value:
        scan.antler_points_left !== null || scan.antler_points_right !== null
          ? `${scan.antler_points_left ?? '—'}L / ${scan.antler_points_right ?? '—'}R`
          : 'N/A',
    },
    {
      label: 'Body Condition',
      value: scan.body_condition || 'Unknown',
    },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* ────── HEADER ────── */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.replace('/(tabs)/scan')}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
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
        contentContainerStyle={[styles.scrollContent, { paddingBottom: insets.bottom + spacing.xxl + 20 }]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={[colors.primary]}
            tintColor={colors.primary}
          />
        }
      >
        {/* ────── 1. DEER IMAGE ────── */}
        {imageUri ? (
          <Image source={{ uri: imageUri }} style={styles.image} resizeMode="cover" />
        ) : (
          <View style={styles.imagePlaceholder}>
            <Target size={48} color={colors.textMuted} />
            <Text style={styles.placeholderText}>Image not available locally</Text>
          </View>
        )}

        {/* Date + Share row */}
        <View style={styles.metaRow}>
          <View style={styles.dateContainer}>
            <Calendar size={14} color={colors.textMuted} />
            <Text style={styles.dateText}>
              {format(new Date(scan.created_at), 'MMM d, yyyy h:mm a')}
            </Text>
          </View>
          <TouchableOpacity
            style={styles.shareButton}
            onPress={handleShare}
            disabled={isSharing}
          >
            {isSharing ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <>
                <Share2 size={16} color={colors.primary} />
                <Text style={styles.shareButtonText}>Share</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* ────── 2. RECOMMENDATION HERO ────── */}
        <ScanSummaryCard
          imageUri={null}
          recommendation={scan.recommendation}
          deerAge={scan.deer_age}
          confidence={scan.confidence}
          deerType={scan.deer_type}
          deerSex={scan.deer_sex}
          antlerPoints={scan.antler_points}
          reasoning={scan.reasoning}
          shareMode={false}
        />

        {/* ────── 3. ESTIMATED AGE + CONFIDENCE ────── */}
        <View style={styles.ageConfRow}>
          {/* Age */}
          <Card style={styles.ageCard}>
            <Text style={styles.ageCardLabel}>ESTIMATED AGE</Text>
            <View style={styles.ageValueRow}>
              <Text
                style={[
                  styles.ageCardValue,
                  ageIsUncertain && styles.uncertainAge,
                ]}
              >
                {ageDisplayText}
              </Text>
              {ageIsUncertain && (
                <AlertCircle size={14} color={colors.textMuted} style={{ marginLeft: 4 }} />
              )}
            </View>
            {scan.deer_type && (
              <Text style={styles.ageCardSub}>
                {scan.deer_type} • {scan.deer_sex || 'Unknown'}
              </Text>
            )}
          </Card>

          {/* Confidence */}
          <Card style={styles.confCard}>
            <Text style={styles.confCardLabel}>CONFIDENCE</Text>
            <Text style={[styles.confCardValue, { color: confLabel.color }]}>
              {displayConfidence}%
            </Text>
            <Text style={[styles.confCardBand, { color: confLabel.color }]}>
              {confLabel.label}
            </Text>
            <Text style={styles.confCardGuidance} numberOfLines={2}>
              {confLabel.guidance}
            </Text>
          </Card>
        </View>

        {/* ────── 4. WHY WE THINK THIS ────── */}
        {scan.reasoning && (
          <Card style={styles.whyCard}>
            <View style={styles.whyHeader}>
              <Eye size={18} color={colors.precision} />
              <Text style={styles.whyTitle}>Why we think this</Text>
            </View>

            {/* Summary */}
            {reasoningSummary ? (
              <Text style={styles.whySummary}>{reasoningSummary}</Text>
            ) : null}

            {/* Top Cues */}
            {reasoningCues.length > 0 ? (
              <View style={styles.cuesContainer}>
                <Text style={styles.cuesLabel}>TOP CUES</Text>
                <View style={styles.cuesChipRow}>
                  {reasoningCues.map((cue, idx) => (
                    <View key={idx} style={styles.cueChip}>
                      <Text style={styles.cueChipText}>{cue}</Text>
                    </View>
                  ))}
                </View>
              </View>
            ) : null}

            {/* Full Analysis (collapsed by default if cues are shown) */}
            {reasoningCues.length > 0 && scan.reasoning && reasoningSummary !== scan.reasoning && (
              <ExpandableText
                label="Full analysis"
                text={scan.reasoning}
              />
            )}

            {/* If no cues were extracted, show full reasoning */}
            {reasoningCues.length === 0 && scan.reasoning && (
              <Text style={styles.whyFullText}>{scan.reasoning}</Text>
            )}
          </Card>
        )}

        {/* ────── 5. ANALYSIS DETAILS GRID ────── */}
        <Text style={styles.sectionTitle}>Analysis Details</Text>
        <View style={styles.dataGrid}>
          {analysisData.map((item, index) => (
            <View key={index} style={styles.dataItem}>
              <Text style={styles.dataLabel}>{item.label}</Text>
              <Text style={styles.dataValue}>{item.value}</Text>
            </View>
          ))}
        </View>

        {/* ────── 6. NOTES ────── */}
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

        {/* ────── 7. TAGS ────── */}
        <TagsEditor
          scanId={scan.id}
          initialTags={scan.tags || []}
          onTagsUpdated={(newTags) => {
            setScan((prev) => (prev ? { ...prev, tags: newTags } : null));
          }}
        />

        {/* ────── 8. FEEDBACK (Improved Copy) ────── */}
        {labelCheckDone && (
          <View style={styles.feedbackSection}>
            {hasLabel ? (
              <View style={styles.feedbackSubmitted}>
                <Check size={16} color={colors.harvest} />
                <Text style={styles.feedbackSubmittedText}>
                  Feedback submitted — thanks for helping improve accuracy!
                </Text>
              </View>
            ) : isFeedbackEligible() ? (
              <TouchableOpacity
                style={styles.feedbackButton}
                onPress={() => setShowFeedbackModal(true)}
              >
                <View style={styles.feedbackButtonLeft}>
                  <MessageSquare size={18} color={colors.primary} />
                  <View style={styles.feedbackButtonTextWrap}>
                    <Text style={styles.feedbackButtonTitle}>Did we get it right?</Text>
                    <Text style={styles.feedbackButtonSub}>
                      Help improve future estimates
                    </Text>
                  </View>
                </View>
                <ChevronRight size={18} color={colors.textMuted} />
              </TouchableOpacity>
            ) : null}
          </View>
        )}

        {/* ────── 9. ETHICAL REMINDER ────── */}
        <Card style={styles.disclaimerCard}>
          <View style={styles.disclaimerHeader}>
            <Shield size={16} color={colors.precision} />
            <Text style={styles.disclaimerTitle}>Iron Stag supports your judgment</Text>
          </View>
          <Text style={styles.disclaimerText}>
            AI analysis is a decision-support tool, not a substitute for field experience.
            Always follow local regulations and practice ethical hunting.
          </Text>
        </Card>
      </ScrollView>

      {/* ────── OFFSCREEN: SHARE CARD ────── */}
      <View style={styles.offscreen}>
        <ViewShot
          ref={shareCardRef}
          options={{ format: 'png', quality: 0.9 }}
        >
          <ScanSummaryCard
            imageUri={imageUri}
            recommendation={scan.recommendation}
            deerAge={scan.deer_age}
            confidence={scan.confidence}
            deerType={scan.deer_type}
            deerSex={scan.deer_sex}
            antlerPoints={scan.antler_points}
            reasoning={scan.reasoning}
            shareMode={true}
          />
        </ViewShot>
      </View>

      {/* ────── EDIT MODAL ────── */}
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

              <Text style={styles.inputLabel}>Left Antler Points</Text>
              <TextInput
                style={styles.textInput}
                value={editPointsLeft}
                onChangeText={setEditPointsLeft}
                placeholder="e.g., 4"
                placeholderTextColor={colors.textMuted}
                keyboardType="numeric"
              />

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

      {/* ────── FEEDBACK MODAL ────── */}
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

// ════════════════════════════════════
// Expandable text sub-component
// ════════════════════════════════════
function ExpandableText({ label, text }: { label: string; text: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <View style={styles.expandableContainer}>
      <TouchableOpacity
        style={styles.expandableToggle}
        onPress={() => setExpanded(!expanded)}
      >
        <Text style={styles.expandableLabel}>{label}</Text>
        <ChevronRight
          size={14}
          color={colors.textMuted}
          style={{ transform: [{ rotate: expanded ? '90deg' : '0deg' }] }}
        />
      </TouchableOpacity>
      {expanded && <Text style={styles.expandableText}>{text}</Text>}
    </View>
  );
}

// ════════════════════════════════════
// STYLES
// ════════════════════════════════════
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centered: {
    justifyContent: 'center',
    alignItems: 'center',
  },

  // ── Header ──
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

  // ── Image ──
  image: {
    width: '100%',
    height: 260,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.sm,
  },
  imagePlaceholder: {
    width: '100%',
    height: 200,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  placeholderText: {
    color: colors.textMuted,
    marginTop: spacing.sm,
  },

  // ── Meta row (date + share) ──
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
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
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.primaryMuted,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.borderBrass,
  },
  shareButtonText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.primary,
  },

  // ── Age + Confidence Row ──
  ageConfRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  ageCard: {
    flex: 1,
    padding: spacing.md,
    alignItems: 'center',
  },
  ageCardLabel: {
    ...typography.sectionHeader,
    color: colors.textMuted,
    marginBottom: spacing.xs,
    fontSize: 11,
  },
  ageValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  ageCardValue: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  uncertainAge: {
    color: colors.textMuted,
    fontStyle: 'italic',
  },
  ageCardSub: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  confCard: {
    flex: 1,
    padding: spacing.md,
    alignItems: 'center',
  },
  confCardLabel: {
    ...typography.sectionHeader,
    color: colors.textMuted,
    marginBottom: spacing.xs,
    fontSize: 11,
  },
  confCardValue: {
    fontSize: 22,
    fontWeight: '700',
  },
  confCardBand: {
    fontSize: 12,
    fontWeight: '600',
    marginTop: 2,
  },
  confCardGuidance: {
    fontSize: 10,
    color: colors.textMuted,
    marginTop: 4,
    textAlign: 'center',
    lineHeight: 14,
  },

  // ── Why We Think This ──
  whyCard: {
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  whyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  whyTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.precision,
    letterSpacing: 0.3,
  },
  whySummary: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 21,
    marginBottom: spacing.sm,
  },
  cuesContainer: {
    marginTop: spacing.xs,
  },
  cuesLabel: {
    ...typography.sectionHeader,
    color: colors.textMuted,
    fontSize: 10,
    marginBottom: spacing.xs,
  },
  cuesChipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  cueChip: {
    backgroundColor: colors.precisionMuted,
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.precision + '30',
  },
  cueChipText: {
    fontSize: 12,
    fontWeight: '500',
    color: colors.precision,
  },
  whyFullText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 21,
  },

  // ── Expandable ──
  expandableContainer: {
    marginTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    paddingTop: spacing.sm,
  },
  expandableToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  expandableLabel: {
    fontSize: 12,
    fontWeight: '500',
    color: colors.textMuted,
  },
  expandableText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 19,
    marginTop: spacing.sm,
  },

  // ── Section title ──
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },

  // ── Data Grid ──
  dataGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: spacing.md,
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.lg,
    padding: spacing.sm,
    ...shadows.card,
  },
  dataItem: {
    width: '50%',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
  },
  dataLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginBottom: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  dataValue: {
    fontSize: 15,
    color: colors.textPrimary,
    fontWeight: '500',
  },

  // ── Notes ──
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

  // ── Feedback ──
  feedbackSection: {
    marginBottom: spacing.md,
  },
  feedbackButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.backgroundCard,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.primary + '25',
    ...shadows.card,
  },
  feedbackButtonLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flex: 1,
  },
  feedbackButtonTextWrap: {
    flex: 1,
  },
  feedbackButtonTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  feedbackButtonSub: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 1,
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

  // ── Disclaimer ──
  disclaimerCard: {
    backgroundColor: colors.precisionMuted,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.precision + '20',
  },
  disclaimerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  disclaimerTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.precision,
  },
  disclaimerText: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 18,
  },

  // ── Error ──
  errorText: {
    color: colors.error,
    fontSize: 16,
    marginBottom: spacing.md,
  },

  // ── Offscreen share card ──
  offscreen: {
    position: 'absolute',
    left: -9999,
    top: -9999,
  },

  // ── Modal ──
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

  title: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
});
