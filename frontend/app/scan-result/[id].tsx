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
  RefreshControl,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Picker } from '@react-native-picker/picker';
import * as FileSystem from 'expo-file-system';
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
import { TagsEditor } from '../../components/TagsEditor';
import { useImageStore } from '../../stores/imageStore';
import { scanAPI } from '../../utils/api';
import {
  BC_EIGHTH_OPTIONS,
  BC_H_FIELDS,
  BC_PAIR_LABELS,
  BC_SCORE_TYPE_OPTIONS,
  bcScoreTypeSupportsExtraNormalPoints,
  buildMeasurementInput,
  buildBcScorePreview,
  bcScoreRecordToFormState,
  createEmptyBcScoreFormState,
  formStateToBcScoreEntry,
  formatInchesToEighths,
  getBcScoreTypeLabel,
  getVisibleBcGFields,
  isNonTypicalBcScoreType,
  isBcScoreTypeCompatibleWithScan,
  isBcScoreTypeImplemented,
  splitMeasurementInput,
  type BcEighthOption,
  type BcPairField,
  type BcScoreFormState,
  type BcScoreRecord,
  type BcScoreType,
} from '../../utils/bcScoring';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { format, differenceInDays } from 'date-fns';

// ============ CONFIDENCE CALIBRATION CONSTANTS ============
// Cap confidence at this value when age is uncertain/unknown
const UNCERTAIN_AGE_CONFIDENCE_CAP = 60;
const HARVEST_RECOMMENDATION_MIN_AGE = 3.5;
const BC_DISCLAIMER =
  'Unofficial Boone & Crockett estimate. User-entered measurements only. Official Boone & Crockett scores require a certified official measurer.';
const BC_REFERENCE_NOTE =
  'Reference only. Use the official Boone & Crockett materials for authentic scoring guidance.';
const BC_REFERENCE_IMAGES_BY_TYPE: Record<BcScoreType, number[]> = {
  typical_whitetail_unofficial: [
    require('../../assets/images/TWT_0_1.png'),
    require('../../assets/images/TWT_0_2.png'),
    require('../../assets/images/TWT_0_3.png'),
  ],
  non_typical_whitetail_unofficial: [
    require('../../assets/images/NTWT_0_1.png'),
    require('../../assets/images/NTWT_0_2.png'),
    require('../../assets/images/NTWT_0_3.png'),
  ],
  typical_mule_deer_unofficial: [
    require('../../assets/images/Typ_Mule_Deer_1.png'),
    require('../../assets/images/Typ_Mule_Deer_2.png'),
    require('../../assets/images/Typ_Mule_Deer_3.png'),
  ],
  non_typical_mule_deer_unofficial: [
    require('../../assets/images/NT_Mule_Deer_1.png'),
    require('../../assets/images/NT_Mule_Deer_2.png'),
    require('../../assets/images/NT_Mule_Deer_3.png'),
  ],
};
const BC_SCORE_TYPE_REFERENCE_DETAILS: Partial<
  Record<BcScoreType, { note: string; minimumScores?: { awards: string; allTime: string } }>
> = {
  typical_whitetail_unofficial: {
    note: 'Typical Whitetail uses G-1 through G-7 on the main sheet, and the add section can capture additional normal points beyond G-7. Abnormal points still stay separate and Column 3 deducts both abnormalities and side-to-side differences.',
  },
  non_typical_whitetail_unofficial: {
    note: 'Non-Typical Whitetail uses G-1 through G-7 as the normal-point layout. Points entered beyond G-7 are counted in E. Total of Lengths of All Abnormal Points and added after the side-to-side deductions.',
    minimumScores: {
      awards: '185',
      allTime: '195',
    },
  },
  typical_mule_deer_unofficial: {
    note: 'Typical Mule Deer uses G-1 through G-4 as normal points. Any non-typical projections or points beyond the normal pattern belong in abnormal points, and their total is deducted through Column 3.',
    minimumScores: {
      awards: '180',
      allTime: '190',
    },
  },
  non_typical_mule_deer_unofficial: {
    note: 'Non-Typical Mule Deer uses G-1 through G-4 as the normal-point layout. Any points entered beyond G-4 are counted in E. Total of All Abnormal Points and added after the side-to-side deductions.',
    minimumScores: {
      awards: '215',
      allTime: '230',
    },
  },
};

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
  age_estimation_allowed?: boolean | null;
  retake_reason?: string | null;
  visible_age_cues?: string[];
  notes: string | null;
  created_at: string;
  // Cloud image storage (R2) - for cross-device access
  image_url?: string | null;
  // Tags for organization
  tags?: string[];
  harvest_confirmed?: boolean | null;
  harvested_at?: string | null;
  boone_crockett_score?: BcScoreRecord | null;
  boone_crockett_gross?: number | null;
  boone_crockett_net?: number | null;
  boone_crockett_final_score?: number | null;
  boone_crockett_status?: 'draft' | 'complete' | null;
  boone_crockett_calculated_at?: string | null;
  boone_crockett_updated_at?: string | null;
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

function getDisplayRecommendation(scan: ScanResult): 'HARVEST' | 'PASS' | null {
  const recommendation = scan.recommendation?.toUpperCase();
  const deerAge = scan.deer_age;
  if (recommendation === 'HARVEST' || recommendation === 'PASS') {
    return recommendation;
  }
  if (scan.age_estimation_allowed === false || deerAge === null || deerAge === undefined || deerAge === 0) {
    return null;
  }
  return deerAge >= HARVEST_RECOMMENDATION_MIN_AGE ? 'HARVEST' : 'PASS';
}

function getDefaultBcScoreType(scan?: Pick<ScanResult, 'deer_type'> | null): BcScoreType {
  const deerType = scan?.deer_type?.trim().toLowerCase();
  if (deerType === 'mule deer' || deerType === 'muledeer' || deerType === 'mule') {
    return 'typical_mule_deer_unofficial';
  }
  return 'typical_whitetail_unofficial';
}

function buildInitialBcScoreForm(scan?: Pick<ScanResult, 'deer_type'> | null, score?: BcScoreRecord | null): BcScoreFormState {
  if (score) {
    return bcScoreRecordToFormState(score);
  }
  const emptyForm = createEmptyBcScoreFormState();
  emptyForm.type = getDefaultBcScoreType(scan);
  return emptyForm;
}

function roundScoreMetric(value: number | null | undefined): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  return Math.round(value * 1000) / 1000;
}

function deriveScoreMetrics(score?: Pick<BcScoreRecord, 'type' | 'spread' | 'computed' | 'abnormalPoints'> | null) {
  if (!score) {
    return null;
  }
  const isNonTypical = isNonTypicalBcScoreType(score.type);
  const spreadCredit = score.spread.spreadCredit ?? null;
  const rightTotal = score.computed.rightTotal ?? null;
  const leftTotal = score.computed.leftTotal ?? null;
  const pairedDifferencesTotal = score.computed.pairedDifferencesTotal ?? null;
  const deductionsTotal = score.computed.deductionsTotal ?? null;
  const abnormalTotal = score.abnormalPoints.totalLength ?? score.computed.abnormalDeductionTotal ?? 0;
  const subtotalOne =
    score.computed.subtotalOne ??
    (spreadCredit === null && rightTotal === null && leftTotal === null
      ? null
      : roundScoreMetric((spreadCredit || 0) + (rightTotal || 0) + (leftTotal || 0)));
  const subtotalTwo =
    score.computed.subtotalTwo ??
    (subtotalOne === null ? null : roundScoreMetric((subtotalOne || 0) - (pairedDifferencesTotal || 0)));
  const grossScore =
    subtotalOne === null
      ? null
      : isNonTypical
        ? roundScoreMetric((subtotalOne || 0) + (abnormalTotal || 0))
        : roundScoreMetric(subtotalOne);
  const finalScore =
    subtotalTwo === null || subtotalOne === null
      ? null
      : isNonTypical
        ? roundScoreMetric((subtotalTwo || 0) + (abnormalTotal || 0))
        : roundScoreMetric((subtotalOne || 0) - (deductionsTotal || 0));

  return {
    spreadCredit,
    rightTotal,
    leftTotal,
    subtotalOne,
    pairedDifferencesTotal,
    deductionsTotal,
    subtotalTwo,
    abnormalTotal,
    grossScore,
    finalScore,
  };
}

interface ScoreMeasurementInputProps {
  value: string;
  onChange: (value: string) => void;
  wholePlaceholder?: string;
  compact?: boolean;
  wholeWidth?: number;
  fractionMinWidth?: number;
}

function ScoreMeasurementInput({
  value,
  onChange,
  wholePlaceholder = '0',
  compact = false,
  wholeWidth,
  fractionMinWidth,
}: ScoreMeasurementInputProps) {
  const parts = splitMeasurementInput(value);

  const handleWholeChange = (nextWhole: string) => {
    onChange(buildMeasurementInput(nextWhole, parts.eighth));
  };

  const handleEighthChange = (nextEighth: BcEighthOption) => {
    onChange(buildMeasurementInput(parts.whole, nextEighth));
  };

  return (
    <View style={[styles.scoreMeasurementField, compact && styles.scoreMeasurementFieldCompact]}>
      <TextInput
        style={[
          styles.scoreMeasurementWholeInput,
          compact && styles.scoreMeasurementWholeInputCompact,
          wholeWidth ? { width: wholeWidth } : null,
        ]}
        value={parts.whole}
        onChangeText={handleWholeChange}
        placeholder={wholePlaceholder}
        placeholderTextColor={colors.textMuted}
        keyboardType="number-pad"
      />
      <View
        style={[
          styles.scoreMeasurementFractionWrap,
          compact && styles.scoreMeasurementFractionWrapCompact,
          fractionMinWidth ? { minWidth: fractionMinWidth } : null,
        ]}
      >
        <Picker
          selectedValue={parts.eighth}
          onValueChange={(nextValue) => handleEighthChange(nextValue as BcEighthOption)}
          style={styles.scoreMeasurementFractionPicker}
          dropdownIconColor={colors.textPrimary}
        >
          {BC_EIGHTH_OPTIONS.map((option) => (
            <Picker.Item key={option} label={option} value={option} />
          ))}
        </Picker>
      </View>
    </View>
  );
}

interface ScorePairedMeasurementRowProps {
  label: string;
  rightValue: string;
  leftValue: string;
  onRightChange: (value: string) => void;
  onLeftChange: (value: string) => void;
  difference: number | null;
}

function ScorePairedMeasurementRow({
  label,
  rightValue,
  leftValue,
  onRightChange,
  onLeftChange,
  difference,
}: ScorePairedMeasurementRowProps) {
  return (
    <View style={styles.scoreMeasureCard}>
      <View style={styles.scoreMeasureMetaRow}>
        <Text style={styles.scoreMeasureCardLabel}>{label}</Text>
        <View style={styles.scoreDifferenceBadge}>
          <Text style={styles.scoreDifferenceBadgeLabel}>Difference</Text>
          <Text style={styles.scoreDifferenceBadgeValue}>{formatInchesToEighths(difference)}</Text>
        </View>
      </View>
      <View style={styles.scoreMeasureInputHeaderRow}>
        <Text style={styles.scoreMeasureSideHeader}>Right</Text>
        <Text style={styles.scoreMeasureSideHeader}>Left</Text>
      </View>
      <View style={styles.scoreMeasureInputsRow}>
        <ScoreMeasurementInput
          value={rightValue}
          onChange={onRightChange}
          compact
          wholeWidth={42}
          fractionMinWidth={88}
        />
        <ScoreMeasurementInput
          value={leftValue}
          onChange={onLeftChange}
          compact
          wholeWidth={42}
          fractionMinWidth={88}
        />
      </View>
    </View>
  );
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
  
  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editDeerSex, setEditDeerSex] = useState<string>('');
  const [editDeerType, setEditDeerType] = useState<string>('');
  const [editPointsLeft, setEditPointsLeft] = useState<string>('');
  const [editPointsRight, setEditPointsRight] = useState<string>('');
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);
  const [showScoreModal, setShowScoreModal] = useState(false);
  const [scoreForm, setScoreForm] = useState<BcScoreFormState>(createEmptyBcScoreFormState());
  const [isSavingScore, setIsSavingScore] = useState(false);
  
  // Feedback modal state (Phase 2 Empirical Calibration)
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [hasLabel, setHasLabel] = useState(false);
  const [labelCheckDone, setLabelCheckDone] = useState(false);

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
      setScoreForm(buildInitialBcScoreForm(response.data, response.data.boone_crockett_score));

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
      setRefreshing(false);
    }
  };
  
  // Pull-to-refresh handler
  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadScan();
  }, [id]);
  
  const isQuickFeedbackEligible = (): boolean => {
    if (!scan || hasLabel) return false;
    const scanDate = new Date(scan.created_at);
    const daysSinceScan = differenceInDays(new Date(), scanDate);
    return daysSinceScan >= 7;
  };

  const canOpenFeedbackModal = (): boolean => {
    return !!scan && !hasLabel;
  };
  
  const handleLabelSubmitted = () => {
    setHasLabel(true);
  };

  const handleHarvestToggle = async (nextValue: boolean) => {
    if (!scan) return;
    try {
      const response = await scanAPI.updateScan(scan.id, { harvest_confirmed: nextValue });
      setScan(response.data);
      if (nextValue) {
        setScoreForm(buildInitialBcScoreForm(response.data, response.data.boone_crockett_score));
        setShowScoreModal(true);
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to update harvest status.';
      Alert.alert('Error', message);
    }
  };

  const openScoreModal = () => {
    if (!scan) return;
    setScoreForm(buildInitialBcScoreForm(scan, scan.boone_crockett_score));
    setShowScoreModal(true);
  };

  const updatePointsSummaryField = (
    field: keyof BcScoreFormState['pointsSummary'],
    value: string
  ) => {
    setScoreForm((prev) => ({
      ...prev,
      pointsSummary: {
        ...prev.pointsSummary,
        [field]: value,
      },
    }));
  };

  const updateSpreadField = (
    field: keyof BcScoreFormState['spread'],
    value: string
  ) => {
    setScoreForm((prev) => ({
      ...prev,
      spread: {
        ...prev.spread,
        [field]: value,
      },
    }));
  };

  const updateAbnormalPointValue = (
    side: 'right' | 'left',
    index: number,
    value: string
  ) => {
    setScoreForm((prev) => ({
      ...prev,
      abnormalPoints: {
        ...prev.abnormalPoints,
        [side]: (() => {
          const nextValues = [...prev.abnormalPoints[side]];
          if (index >= nextValues.length) {
            nextValues.push(...Array.from({ length: index - nextValues.length + 1 }, () => ''));
          }
          nextValues[index] = value;
          return nextValues;
        })(),
      },
    }));
  };

  const updateSideField = (
    side: 'right' | 'left',
    field: BcPairField,
    value: string
  ) => {
    setScoreForm((prev) => ({
      ...prev,
      [side]: {
        ...prev[side],
        [field]: value,
      },
    }));
  };

  const updateExtraPointField = (
    side: 'right' | 'left',
    index: number,
    value: string
  ) => {
    setScoreForm((prev) => ({
      ...prev,
      [side]: {
        ...prev[side],
        extraPoints: (() => {
          const nextValues = [...prev[side].extraPoints];
          if (index >= nextValues.length) {
            nextValues.push(...Array.from({ length: index - nextValues.length + 1 }, () => ''));
          }
          nextValues[index] = value;
          return nextValues;
        })(),
      },
    }));
  };

  const addExtraPointRow = () => {
    setScoreForm((prev) => ({
      ...prev,
      right: {
        ...prev.right,
        extraPoints: [...prev.right.extraPoints, ''],
      },
      left: {
        ...prev.left,
        extraPoints: [...prev.left.extraPoints, ''],
      },
    }));
  };

  const addAbnormalPointRow = (side: 'right' | 'left') => {
    setScoreForm((prev) => ({
      ...prev,
      abnormalPoints: {
        ...prev.abnormalPoints,
        [side]: [...prev.abnormalPoints[side], ''],
      },
    }));
  };

  const handleSaveScore = async () => {
    if (!scan) return;
    const scoreEntry = formStateToBcScoreEntry(scoreForm);
    if (!scoreEntry.disclaimerAccepted) {
      Alert.alert('Disclaimer Required', 'Please confirm the unofficial scoring disclaimer before saving.');
      return;
    }
    setIsSavingScore(true);
    try {
      const response = await scanAPI.updateScan(scan.id, {
        boone_crockett_measurements: scoreEntry,
        boone_crockett_disclaimer_accepted: scoreEntry.disclaimerAccepted,
      });
      setScan(response.data);
      setScoreForm(buildInitialBcScoreForm(response.data, response.data.boone_crockett_score));
      setShowScoreModal(false);
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to save score measurements.';
      Alert.alert('Error', message);
    } finally {
      setIsSavingScore(false);
    }
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
        try {
          let base64Image: string;
          
          // Check if it's a cloud URL (R2) or local file
          if (imageUri.startsWith('http://') || imageUri.startsWith('https://')) {
            // Cloud URL - fetch and convert to base64
            const response = await fetch(imageUri);
            const blob = await response.blob();
            const reader = new FileReader();
            base64Image = await new Promise<string>((resolve, reject) => {
              reader.onloadend = () => {
                const result = reader.result as string;
                // Extract just the base64 part if it includes the data URI prefix
                resolve(result);
              };
              reader.onerror = reject;
              reader.readAsDataURL(blob);
            });
          } else {
            // Local file URI - use FileSystem to read
            const base64Data = await FileSystem.readAsStringAsync(imageUri, {
              encoding: 'base64' as any,
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
      } else {
        console.log('No image URI available for re-analysis');
      }
      
      // Show loading indicator for re-analysis
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

  if (loading) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        {/* Header */}
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
        
        {/* Skeleton loading state */}
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

  // Build analysis data with left/right antler points
  // Apply confidence calibration for uncertain ages
  const ageIsUncertain = isAgeUncertain(scan.deer_age);
  const displayConfidence = getCalibratedConfidence(scan.confidence, scan.deer_age);
  const ageDisplayText = getAgeDisplayText(scan.deer_age);
  const ageEstimateBlocked = scan.age_estimation_allowed === false;
  const displayRecommendation = getDisplayRecommendation(scan);
  const visibleAgeCueText = scan.visible_age_cues && scan.visible_age_cues.length > 0
    ? scan.visible_age_cues.map((cue) => cue.replace(/_/g, ' ')).join(', ')
    : null;
  const recommendationVariant =
    displayRecommendation === 'HARVEST'
      ? 'harvest'
      : displayRecommendation === 'PASS'
        ? 'pass'
        : 'unknown';
  const isHarvestedBuck = scan.deer_sex === 'Buck' && !!scan.harvest_confirmed;
  const scoreSummary = scan.boone_crockett_score;
  const liveScoreEntry = formStateToBcScoreEntry(scoreForm);
  const liveScorePreview = buildBcScorePreview(liveScoreEntry);
  const selectedScoreTypeLabel = getBcScoreTypeLabel(scoreForm.type);
  const summaryScoreTypeLabel = getBcScoreTypeLabel(scoreSummary?.type || scoreForm.type);
  const selectedScoreTypeImplemented = isBcScoreTypeImplemented(scoreForm.type);
  const selectedScoreTypeVisibleGFields = getVisibleBcGFields(scoreForm.type);
  const selectedScoreTypeSupportsExtraPoints = bcScoreTypeSupportsExtraNormalPoints(scoreForm.type);
  const selectedScoreTypeReferenceImages = BC_REFERENCE_IMAGES_BY_TYPE[scoreForm.type];
  const selectedScoreTypeReferenceDetails = BC_SCORE_TYPE_REFERENCE_DETAILS[scoreForm.type];
  const selectedScoreTypeIsNonTypical = isNonTypicalBcScoreType(scoreForm.type);
  const selectedScoreTypeOption =
    BC_SCORE_TYPE_OPTIONS.find((option) => option.type === scoreForm.type) || BC_SCORE_TYPE_OPTIONS[0];
  const selectedScoreTypeCompatible = isBcScoreTypeCompatibleWithScan(
    scoreForm.type,
    scan.deer_type,
    scan.deer_sex,
    scan.harvest_confirmed
  );
  const canEditScoreMeasurements = selectedScoreTypeImplemented && selectedScoreTypeCompatible;
  const selectedScoreTypeStatusText = !selectedScoreTypeCompatible
    ? `For ${selectedScoreTypeOption.deerType} bucks`
    : selectedScoreTypeImplemented
      ? 'Ready now'
      : 'Coming soon';
  const scorePointsLeft = scoreSummary?.pointsSummary.leftPointsCount ?? scan.antler_points_left;
  const scorePointsRight = scoreSummary?.pointsSummary.rightPointsCount ?? scan.antler_points_right;
  const hasScorePointCounts =
    (scorePointsLeft !== null && scorePointsLeft !== undefined) ||
    (scorePointsRight !== null && scorePointsRight !== undefined);
  const scorePointsTotal = hasScorePointCounts
    ? (scorePointsLeft || 0) + (scorePointsRight || 0)
    : scan.antler_points;
  const scoreFinalValue = scoreSummary?.computed.finalScore ?? scan.boone_crockett_final_score ?? scan.boone_crockett_net;
  const scoreStatus = scoreSummary?.status ?? scan.boone_crockett_status ?? 'draft';
  const scoreUpdatedAt = scan.boone_crockett_updated_at || scoreSummary?.updatedAt || null;
  const scoreSummaryMetrics = deriveScoreMetrics(scoreSummary);
  const liveScoreMetrics = deriveScoreMetrics(liveScorePreview);
  const livePointsTotal =
    liveScoreEntry.pointsSummary.rightPointsCount === null &&
    liveScoreEntry.pointsSummary.leftPointsCount === null
      ? null
      : (liveScoreEntry.pointsSummary.rightPointsCount || 0) +
        (liveScoreEntry.pointsSummary.leftPointsCount || 0);
  const summaryScoreIsNonTypical = isNonTypicalBcScoreType(scoreSummary?.type || scoreForm.type);
  const showHarvestRecordCard = scan.deer_sex === 'Buck' && !scan.harvest_confirmed;
  const scoreActionLabel = scoreSummary ? 'Edit Measurements' : 'Choose Score Type';
  const extraPointFormRowCount = selectedScoreTypeSupportsExtraPoints
    ? Math.max(scoreForm.right.extraPoints.length, scoreForm.left.extraPoints.length)
    : 0;
  
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
    ...(visibleAgeCueText ? [{ label: 'Visible Age Cues', value: visibleAgeCueText }] : []),
    { 
      label: 'Model Confidence', 
      value: `${displayConfidence}%`,
      isUncertain: ageIsUncertain,
      helpText: ageEstimateBlocked
        ? 'No age confidence because the image failed the quality gate'
        : ageIsUncertain
          ? 'Capped due to age uncertainty'
          : undefined,
    },
  ];

  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
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
              recommendationVariant === 'harvest'
                ? styles.harvestBadge
                : recommendationVariant === 'pass'
                  ? styles.passBadge
                  : styles.unknownBadge,
            ]}
          >
            <Text
              style={[
                styles.recommendationText,
                recommendationVariant === 'harvest'
                  ? styles.harvestText
                  : recommendationVariant === 'pass'
                    ? styles.passText
                    : styles.unknownText,
              ]}
            >
              {displayRecommendation || 'UNKNOWN'}
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
              {ageEstimateBlocked ? 'Best estimate unavailable' : `Est. Age: ${ageDisplayText}`}
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

        {scan.retake_reason && (
          <Card style={styles.retakeCard}>
            <View style={styles.retakeHeader}>
              <AlertCircle size={18} color={colors.warning} />
              <Text style={styles.retakeTitle}>Better Photo Needed</Text>
            </View>
            <Text style={styles.retakeText}>{scan.retake_reason}</Text>
            {visibleAgeCueText && (
              <Text style={styles.retakeCueText}>Visible cues captured: {visibleAgeCueText}</Text>
            )}
          </Card>
        )}

        {/* AI Insight */}
        {scan.reasoning && scan.reasoning !== scan.retake_reason && (
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

        {showHarvestRecordCard && (
          <Card style={styles.scoreCard}>
            <View style={styles.scoreCardHeader}>
              <View>
                <Text style={styles.scoreCardTitle}>Harvest Record</Text>
                <Text style={styles.scoreCardSubtitle}>Mark harvested to unlock manual scoring</Text>
              </View>
            </View>
            <Text style={styles.scoreHelperText}>
              Only harvested bucks can use the Unofficial B&amp;C Score workflow.
            </Text>
            <TouchableOpacity style={styles.scorePrimaryButton} onPress={() => handleHarvestToggle(true)}>
              <Text style={styles.scorePrimaryButtonText}>Mark Harvested</Text>
            </TouchableOpacity>
          </Card>
        )}

        {isHarvestedBuck && (
          <Card style={styles.scoreCard}>
            <View style={styles.scoreCardHeader}>
              <View>
                <Text style={styles.scoreCardTitle}>Unofficial B&amp;C Score</Text>
                <Text style={styles.scoreCardSubtitle}>User-entered estimate for harvested bucks</Text>
              </View>
              <View
                style={[
                  styles.scoreStatusBadge,
                  scoreStatus === 'complete' ? styles.scoreReadyBadge : styles.scoreIncompleteBadge,
                ]}
              >
                <Text
                  style={[
                    styles.scoreStatusText,
                    scoreStatus === 'complete' ? styles.scoreReadyText : styles.scoreIncompleteText,
                  ]}
                >
                  {scoreStatus === 'complete' ? 'Ready' : 'Incomplete'}
                </Text>
              </View>
            </View>

            <Text style={styles.scoreDisclaimer}>{BC_DISCLAIMER}</Text>
            <Text style={styles.scoreReferenceNote}>{BC_REFERENCE_NOTE}</Text>
            <Text style={styles.scoreHelperText}>Score Type: {summaryScoreTypeLabel}</Text>

            {scoreSummary ? (
              <>
                <View style={styles.scoreSummaryGrid}>
                  <View style={styles.scoreSummaryItem}>
                    <Text style={styles.scoreSummaryLabel}>Spread Credit</Text>
                    <Text style={styles.scoreSummaryValue}>
                      {formatInchesToEighths(scoreSummaryMetrics?.spreadCredit ?? scoreSummary.spread.spreadCredit)}
                    </Text>
                  </View>
                  <View style={styles.scoreSummaryItem}>
                    <Text style={styles.scoreSummaryLabel}>
                      {summaryScoreIsNonTypical ? 'Right Total' : 'Column 1 (Right Antler)'}
                    </Text>
                    <Text style={styles.scoreSummaryValue}>
                      {formatInchesToEighths(scoreSummaryMetrics?.rightTotal ?? scoreSummary.computed.rightTotal)}
                    </Text>
                  </View>
                  <View style={styles.scoreSummaryItem}>
                    <Text style={styles.scoreSummaryLabel}>
                      {summaryScoreIsNonTypical ? 'Left Total' : 'Column 2 (Left Antler)'}
                    </Text>
                    <Text style={styles.scoreSummaryValue}>
                      {formatInchesToEighths(scoreSummaryMetrics?.leftTotal ?? scoreSummary.computed.leftTotal)}
                    </Text>
                  </View>
                  {summaryScoreIsNonTypical ? (
                    <>
                      <View style={styles.scoreSummaryItem}>
                        <Text style={styles.scoreSummaryLabel}>Subtotal (1)</Text>
                        <Text style={styles.scoreSummaryValue}>
                          {formatInchesToEighths(scoreSummaryMetrics?.subtotalOne)}
                        </Text>
                      </View>
                      <View style={styles.scoreSummaryItem}>
                        <Text style={styles.scoreSummaryLabel}>Difference</Text>
                        <Text style={styles.scoreSummaryValue}>
                          {formatInchesToEighths(scoreSummaryMetrics?.pairedDifferencesTotal)}
                        </Text>
                      </View>
                      <View style={styles.scoreSummaryItem}>
                        <Text style={styles.scoreSummaryLabel}>Subtotal (2)</Text>
                        <Text style={styles.scoreSummaryValue}>
                          {formatInchesToEighths(scoreSummaryMetrics?.subtotalTwo)}
                        </Text>
                      </View>
                      <View style={styles.scoreSummaryItem}>
                        <Text style={styles.scoreSummaryLabel}>Abnormal</Text>
                        <Text style={styles.scoreSummaryValue}>
                          {formatInchesToEighths(scoreSummaryMetrics?.abnormalTotal)}
                        </Text>
                      </View>
                    </>
                  ) : (
                    <>
                      <View style={styles.scoreSummaryItem}>
                        <Text style={styles.scoreSummaryLabel}>Column 3 (Deductions)</Text>
                        <Text style={styles.scoreSummaryValue}>
                          {formatInchesToEighths(scoreSummaryMetrics?.deductionsTotal ?? scoreSummary.computed.deductionsTotal)}
                        </Text>
                      </View>
                      <View style={styles.scoreSummaryItem}>
                        <Text style={styles.scoreSummaryLabel}>Subtotal</Text>
                        <Text style={styles.scoreSummaryValue}>
                          {formatInchesToEighths(scoreSummaryMetrics?.subtotalOne)}
                        </Text>
                      </View>
                    </>
                  )}
                  <View style={styles.scoreSummaryItem}>
                    <Text style={styles.scoreSummaryLabel}>Last Updated</Text>
                    <Text style={styles.scoreSummaryValueSmall}>
                      {scoreUpdatedAt ? format(new Date(scoreUpdatedAt), 'MMM d, yyyy') : '—'}
                    </Text>
                  </View>
                  {summaryScoreIsNonTypical ? (
                    <View style={styles.scoreSummaryItem}>
                      <Text style={styles.scoreSummaryLabel}>Gross Score</Text>
                      <Text style={styles.scoreSummaryValue}>
                        {formatInchesToEighths(scoreSummaryMetrics?.grossScore ?? scoreSummary.computed.grossScore)}
                      </Text>
                    </View>
                  ) : null}
                  <View style={styles.scoreSummaryItem}>
                    <Text style={styles.scoreSummaryLabel}>Final Unofficial Score</Text>
                    <Text style={styles.scoreSummaryValue}>
                      {formatInchesToEighths(scoreSummaryMetrics?.finalScore ?? scoreFinalValue)}
                    </Text>
                  </View>
                  <View style={styles.scoreSummaryItem}>
                    <Text style={styles.scoreSummaryLabel}>Points (R / L / Total)</Text>
                    <Text style={styles.scoreSummaryValueSmall}>
                      {scorePointsRight ?? '—'} / {scorePointsLeft ?? '—'} / {scorePointsTotal ?? '—'}
                    </Text>
                  </View>
                </View>

                {scoreSummary.warnings.length > 0 && (
                  <View style={styles.scoreWarningsBox}>
                    {scoreSummary.warnings.map((warning) => (
                      <Text key={warning.code} style={styles.scoreWarningText}>
                        {warning.message}
                      </Text>
                    ))}
                  </View>
                )}
              </>
            ) : (
              <Text style={styles.scoreHelperText}>
                Choose a score type to begin. Typical Whitetail Deer, Non-Typical Whitetail Deer, Typical Mule Deer, and Non-Typical Mule Deer are implemented right now.
              </Text>
            )}

            <View style={styles.scoreActionRow}>
              <TouchableOpacity style={styles.scorePrimaryButton} onPress={openScoreModal}>
                <Text style={styles.scorePrimaryButtonText}>
                  {scoreActionLabel}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.scoreSecondaryButton} onPress={() => handleHarvestToggle(false)}>
                <Text style={styles.scoreSecondaryButtonText}>Unmark Harvested</Text>
              </TouchableOpacity>
            </View>
          </Card>
        )}

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

        {/* Tags Section */}
        <TagsEditor 
          scanId={scan.id}
          initialTags={scan.tags || []}
          onTagsUpdated={(newTags) => {
            setScan(prev => prev ? { ...prev, tags: newTags } : null);
          }}
        />

        {/* Feedback Section (Phase 2 Empirical Calibration) */}
        {labelCheckDone && (
          <View style={styles.feedbackSection}>
            {hasLabel ? (
              <View style={styles.feedbackSubmitted}>
                <Check size={16} color={colors.harvest} />
                <Text style={styles.feedbackSubmittedText}>Feedback submitted — thanks!</Text>
              </View>
            ) : canOpenFeedbackModal() ? (
              <TouchableOpacity 
                style={styles.feedbackButton}
                onPress={() => setShowFeedbackModal(true)}
              >
                <MessageSquare size={18} color={colors.primary} />
                <Text style={styles.feedbackButtonText}>
                  {isQuickFeedbackEligible() ? 'How did this estimate hold up?' : 'Add harvested age or feedback'}
                </Text>
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

            <View style={[styles.modalFooter, { paddingBottom: Math.max(insets.bottom, spacing.md) }]}>
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

      <Modal
        visible={showScoreModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowScoreModal(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Unofficial B&amp;C Score</Text>
              <TouchableOpacity onPress={() => setShowScoreModal(false)}>
                <X size={24} color={colors.textPrimary} />
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.modalBody}>
              <Text style={styles.scoreModalIntro}>
                Enter whole inches, then choose the matching eighth from `0/8` to `7/8` for every length measurement.
              </Text>
              <Text style={styles.scoreDisclaimer}>{BC_DISCLAIMER}</Text>
              <Text style={styles.scoreReferenceNote}>{BC_REFERENCE_NOTE}</Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.scoreReferenceGallery}
              >
                {selectedScoreTypeReferenceImages.map((source, index) => (
                  <Image
                    key={`bc-reference-${index}`}
                    source={source}
                    style={styles.scoreReferenceImage}
                    resizeMode="contain"
                  />
                ))}
              </ScrollView>

              <Text style={styles.scoreGroupTitle}>Section 1: Score Type</Text>
              <View style={styles.scoreTypePickerWrap}>
                <Picker
                  selectedValue={scoreForm.type}
                  onValueChange={(nextValue) =>
                    setScoreForm((prev) => ({ ...prev, type: nextValue as BcScoreType }))
                  }
                  style={styles.scoreTypePicker}
                  dropdownIconColor={colors.textPrimary}
                >
                  {BC_SCORE_TYPE_OPTIONS.map((option) => (
                    <Picker.Item key={option.type} label={option.label} value={option.type} />
                  ))}
                </Picker>
              </View>

              <View style={styles.scoreTypeNoticeBox}>
                <View style={styles.scoreTypeNoticeHeader}>
                  <Text style={styles.scoreTypeNoticeTitle}>{selectedScoreTypeLabel}</Text>
                  <View
                    style={[
                      styles.scoreTypePill,
                      !selectedScoreTypeCompatible
                        ? styles.scoreTypeMutedPill
                        : selectedScoreTypeImplemented
                          ? styles.scoreTypeReadyPill
                          : styles.scoreTypeSoonPill,
                    ]}
                  >
                    <Text
                      style={[
                        styles.scoreTypePillText,
                        !selectedScoreTypeCompatible
                          ? styles.scoreTypeMutedPillText
                          : selectedScoreTypeImplemented
                            ? styles.scoreTypeReadyPillText
                            : styles.scoreTypeSoonPillText,
                      ]}
                    >
                      {selectedScoreTypeStatusText}
                    </Text>
                  </View>
                </View>
                <Text style={styles.scoreTypeNoticeText}>
                  {!selectedScoreTypeCompatible
                    ? 'This score type does not match the current harvested buck record.'
                    : selectedScoreTypeImplemented
                      ? `This screen uses the completed ${selectedScoreTypeLabel} scorecard structure.`
                      : `${selectedScoreTypeLabel} is listed for selection now, but its calculator will be added after the implemented scorecards are finished.`}
                </Text>
                {selectedScoreTypeReferenceDetails?.note ? (
                  <Text style={styles.scoreTypeNoticeSubtext}>{selectedScoreTypeReferenceDetails.note}</Text>
                ) : null}
              </View>

              {selectedScoreTypeReferenceDetails?.minimumScores ? (
                <View style={styles.scoreMinimumsCard}>
                  <Text style={styles.scoreMinimumsTitle}>Minimum Scores</Text>
                  <View style={styles.scoreMinimumsRow}>
                    <Text style={styles.scoreMinimumsValue}>
                      Awards: {selectedScoreTypeReferenceDetails.minimumScores.awards}
                    </Text>
                    <Text style={styles.scoreMinimumsValue}>
                      All-Time: {selectedScoreTypeReferenceDetails.minimumScores.allTime}
                    </Text>
                  </View>
                </View>
              ) : null}

              {canEditScoreMeasurements ? (
                <>
                  <TouchableOpacity
                    style={styles.scoreCheckboxRow}
                    onPress={() =>
                      setScoreForm((prev) => ({
                        ...prev,
                        disclaimerAccepted: !prev.disclaimerAccepted,
                      }))
                    }
                  >
                    <View
                      style={[
                        styles.scoreCheckbox,
                        scoreForm.disclaimerAccepted && styles.scoreCheckboxChecked,
                      ]}
                    >
                      {scoreForm.disclaimerAccepted && <Check size={14} color={colors.white} />}
                    </View>
                    <Text style={styles.scoreCheckboxText}>
                      I understand this is an unofficial, user-entered estimate.
                    </Text>
                  </TouchableOpacity>

                  <Text style={styles.scoreGroupTitle}>Section 2: Antler Count / Spread Info</Text>
                  <View style={styles.scoreSplitRow}>
                    <View style={styles.scoreSplitColumn}>
                      <Text style={styles.inputLabel}>A. Right Points</Text>
                      <TextInput
                        style={styles.textInput}
                        value={scoreForm.pointsSummary.rightPointsCount}
                        onChangeText={(value) => updatePointsSummaryField('rightPointsCount', value)}
                        placeholder="e.g., 5"
                        placeholderTextColor={colors.textMuted}
                        keyboardType="number-pad"
                      />
                    </View>
                    <View style={styles.scoreSplitColumn}>
                      <Text style={styles.inputLabel}>A. Left Points</Text>
                      <TextInput
                        style={styles.textInput}
                        value={scoreForm.pointsSummary.leftPointsCount}
                        onChangeText={(value) => updatePointsSummaryField('leftPointsCount', value)}
                        placeholder="e.g., 5"
                        placeholderTextColor={colors.textMuted}
                        keyboardType="number-pad"
                      />
                    </View>
                  </View>
                  <View style={styles.scorePointsTotalCard}>
                    <Text style={styles.scorePointsTotalLabel}>A Total Points on Antlers</Text>
                    <Text style={styles.scorePointsTotalValue}>
                      {livePointsTotal === null ? '—' : String(livePointsTotal)}
                    </Text>
                  </View>
                  <Text style={styles.scoreSectionNote}>A, B, and C are recorded but are not part of the final score.</Text>
                  <Text style={styles.scoreSectionNote}>All length fields use whole inches plus a required eighth selection.</Text>

                  <View style={styles.scoreSpreadPairRow}>
                    <View style={styles.scoreSpreadPairColumn}>
                      <Text style={styles.inputLabel}>B. Tip to Tip Spread</Text>
                      <ScoreMeasurementInput
                        value={scoreForm.pointsSummary.tipToTipSpread}
                        onChange={(value) => updatePointsSummaryField('tipToTipSpread', value)}
                        wholePlaceholder="16"
                        wholeWidth={54}
                        fractionMinWidth={86}
                      />
                    </View>
                    <View style={styles.scoreSpreadPairColumn}>
                      <Text style={styles.inputLabel}>C. Greatest Spread</Text>
                      <ScoreMeasurementInput
                        value={scoreForm.pointsSummary.greatestSpread}
                        onChange={(value) => updatePointsSummaryField('greatestSpread', value)}
                        wholePlaceholder="18"
                        wholeWidth={54}
                        fractionMinWidth={86}
                      />
                    </View>
                  </View>

                  <Text style={styles.scoreGroupTitle}>Section 3: Spread Credit</Text>
                  <Text style={styles.inputLabel}>D. Inside Spread of Main Beams</Text>
                  <ScoreMeasurementInput
                    value={scoreForm.spread.insideSpreadOfMainBeams}
                    onChange={(value) => updateSpreadField('insideSpreadOfMainBeams', value)}
                    wholePlaceholder="17"
                  />
                  <Text style={styles.scoreSectionNote}>
                    Spread Credit is the lesser of Inside Spread of Main Beams and the longer Main Beam.
                  </Text>

                  <Text style={styles.scoreGroupTitle}>Section 4: Main Beams + Normal Points</Text>
                  <ScorePairedMeasurementRow
                    label={BC_PAIR_LABELS.mainBeam}
                    rightValue={scoreForm.right.mainBeam}
                    leftValue={scoreForm.left.mainBeam}
                    onRightChange={(value) => updateSideField('right', 'mainBeam', value)}
                    onLeftChange={(value) => updateSideField('left', 'mainBeam', value)}
                    difference={liveScorePreview.differences.mainBeam ?? null}
                  />

                  {selectedScoreTypeVisibleGFields.map((field) => (
                    <ScorePairedMeasurementRow
                      key={field}
                      label={BC_PAIR_LABELS[field]}
                      rightValue={scoreForm.right[field]}
                      leftValue={scoreForm.left[field]}
                      onRightChange={(value) => updateSideField('right', field, value)}
                      onLeftChange={(value) => updateSideField('left', field, value)}
                      difference={liveScorePreview.differences[field] ?? null}
                    />
                  ))}

                  {selectedScoreTypeSupportsExtraPoints ? (
                    <>
                      {Array.from({ length: extraPointFormRowCount }, (_, index) => (
                        <ScorePairedMeasurementRow
                          key={`extra-g-${index}`}
                          label={`G-${8 + index}`}
                          rightValue={scoreForm.right.extraPoints[index] || ''}
                          leftValue={scoreForm.left.extraPoints[index] || ''}
                          onRightChange={(nextValue) => updateExtraPointField('right', index, nextValue)}
                          onLeftChange={(nextValue) => updateExtraPointField('left', index, nextValue)}
                          difference={liveScorePreview.differences[`g${8 + index}`] ?? null}
                        />
                      ))}
                      <TouchableOpacity style={styles.scoreInlineButton} onPress={addExtraPointRow}>
                        <Text style={styles.scoreInlineButtonText}>Add Another G Point</Text>
                      </TouchableOpacity>
                    </>
                  ) : null}

                  <Text style={styles.scoreGroupTitle}>Section 5: Circumferences</Text>
                  {BC_H_FIELDS.map((field) => (
                    <ScorePairedMeasurementRow
                      key={field}
                      label={BC_PAIR_LABELS[field]}
                      rightValue={scoreForm.right[field]}
                      leftValue={scoreForm.left[field]}
                      onRightChange={(value) => updateSideField('right', field, value)}
                      onLeftChange={(value) => updateSideField('left', field, value)}
                      difference={liveScorePreview.differences[field] ?? null}
                    />
                  ))}

                  <Text style={styles.scoreGroupTitle}>Section 6: Abnormal Points</Text>
                  {scoreForm.abnormalPoints.right.map((value, index) => (
                    <View key={`abnormal-right-${index}`} style={styles.scoreMeasureRow}>
                      <Text style={styles.scoreMeasureLabel}>{`R-${index + 1}`}</Text>
                      <ScoreMeasurementInput
                        value={value}
                        onChange={(nextValue) => updateAbnormalPointValue('right', index, nextValue)}
                        compact
                        wholeWidth={42}
                        fractionMinWidth={88}
                      />
                    </View>
                  ))}
                  <TouchableOpacity style={styles.scoreInlineButton} onPress={() => addAbnormalPointRow('right')}>
                    <Text style={styles.scoreInlineButtonText}>Add Right Abnormal Point</Text>
                  </TouchableOpacity>

                  {scoreForm.abnormalPoints.left.map((value, index) => (
                    <View key={`abnormal-left-${index}`} style={styles.scoreMeasureRow}>
                      <Text style={styles.scoreMeasureLabel}>{`L-${index + 1}`}</Text>
                      <ScoreMeasurementInput
                        value={value}
                        onChange={(nextValue) => updateAbnormalPointValue('left', index, nextValue)}
                        compact
                        wholeWidth={42}
                        fractionMinWidth={88}
                      />
                    </View>
                  ))}
                  <TouchableOpacity style={styles.scoreInlineButton} onPress={() => addAbnormalPointRow('left')}>
                    <Text style={styles.scoreInlineButtonText}>Add Left Abnormal Point</Text>
                  </TouchableOpacity>

                  <Text style={styles.scoreSubgroupTitle}>Total of Lengths of Abnormal Points</Text>
                  <View style={styles.scoreTripleSummaryRow}>
                    <View style={styles.scoreTripleSummaryItem}>
                      <Text style={styles.scoreSummaryLabel}>Right</Text>
                      <Text style={styles.scoreSummaryValue}>
                        {formatInchesToEighths(liveScorePreview.abnormalPoints.rightTotalLength)}
                      </Text>
                    </View>
                    <View style={styles.scoreTripleSummaryItem}>
                      <Text style={styles.scoreSummaryLabel}>Left</Text>
                      <Text style={styles.scoreSummaryValue}>
                        {formatInchesToEighths(liveScorePreview.abnormalPoints.leftTotalLength)}
                      </Text>
                    </View>
                    <View style={styles.scoreTripleSummaryItem}>
                      <Text style={styles.scoreSummaryLabel}>Total</Text>
                      <Text style={styles.scoreSummaryValue}>
                        {formatInchesToEighths(liveScorePreview.abnormalPoints.totalLength)}
                      </Text>
                    </View>
                  </View>

                  <Text style={styles.scoreGroupTitle}>Section 7: Live Score Summary</Text>
                  <View
                    style={[
                      styles.scoreStatusBadge,
                      liveScorePreview.status === 'complete' ? styles.scoreReadyBadge : styles.scoreIncompleteBadge,
                    ]}
                  >
                    <Text
                      style={[
                        styles.scoreStatusText,
                        liveScorePreview.status === 'complete' ? styles.scoreReadyText : styles.scoreIncompleteText,
                      ]}
                    >
                      {liveScorePreview.status === 'complete' ? 'Ready' : 'Incomplete'}
                    </Text>
                  </View>

                  <View style={styles.scoreSummaryGrid}>
                    <View style={styles.scoreSummaryItem}>
                      <Text style={styles.scoreSummaryLabel}>Spread Credit</Text>
                      <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.spreadCredit ?? liveScorePreview.spread.spreadCredit)}</Text>
                    </View>
                    <View style={styles.scoreSummaryItem}>
                      <Text style={styles.scoreSummaryLabel}>
                        {selectedScoreTypeIsNonTypical ? 'Right Total' : 'Column 1 (Right Antler)'}
                      </Text>
                      <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.rightTotal ?? liveScorePreview.computed.rightTotal)}</Text>
                    </View>
                    <View style={styles.scoreSummaryItem}>
                      <Text style={styles.scoreSummaryLabel}>
                        {selectedScoreTypeIsNonTypical ? 'Left Total' : 'Column 2 (Left Antler)'}
                      </Text>
                      <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.leftTotal ?? liveScorePreview.computed.leftTotal)}</Text>
                    </View>
                    {selectedScoreTypeIsNonTypical ? (
                      <>
                        <View style={styles.scoreSummaryItem}>
                          <Text style={styles.scoreSummaryLabel}>Subtotal (1)</Text>
                          <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.subtotalOne)}</Text>
                        </View>
                        <View style={styles.scoreSummaryItem}>
                          <Text style={styles.scoreSummaryLabel}>Difference</Text>
                          <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.pairedDifferencesTotal)}</Text>
                        </View>
                        <View style={styles.scoreSummaryItem}>
                          <Text style={styles.scoreSummaryLabel}>Subtotal (2)</Text>
                          <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.subtotalTwo)}</Text>
                        </View>
                        <View style={styles.scoreSummaryItem}>
                          <Text style={styles.scoreSummaryLabel}>Abnormal</Text>
                          <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.abnormalTotal)}</Text>
                        </View>
                      </>
                    ) : (
                      <>
                        <View style={styles.scoreSummaryItem}>
                          <Text style={styles.scoreSummaryLabel}>Column 3 (Deductions)</Text>
                          <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.deductionsTotal ?? liveScorePreview.computed.deductionsTotal)}</Text>
                        </View>
                        <View style={styles.scoreSummaryItem}>
                          <Text style={styles.scoreSummaryLabel}>Subtotal</Text>
                          <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.subtotalOne)}</Text>
                        </View>
                      </>
                    )}
                    {selectedScoreTypeIsNonTypical ? (
                      <View style={styles.scoreSummaryItem}>
                        <Text style={styles.scoreSummaryLabel}>Gross Score</Text>
                        <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.grossScore ?? liveScorePreview.computed.grossScore)}</Text>
                      </View>
                    ) : null}
                    <View style={styles.scoreSummaryItem}>
                      <Text style={styles.scoreSummaryLabel}>Final Unofficial Score</Text>
                      <Text style={styles.scoreSummaryValue}>{formatInchesToEighths(liveScoreMetrics?.finalScore ?? liveScorePreview.computed.finalScore)}</Text>
                    </View>
                  </View>

                  {liveScorePreview.warnings.length > 0 && (
                    <View style={styles.scoreWarningsBox}>
                      {liveScorePreview.warnings.map((warning) => (
                        <Text key={warning.code} style={styles.scoreWarningText}>
                          {warning.message}
                        </Text>
                      ))}
                    </View>
                  )}
                </>
              ) : (
                <View style={styles.scoreComingSoonBox}>
                  <Text style={styles.scoreComingSoonTitle}>
                    {selectedScoreTypeCompatible ? 'Scorecard Coming Soon' : 'Pick a Matching Score Type'}
                  </Text>
                  <Text style={styles.scoreComingSoonText}>
                    {selectedScoreTypeCompatible
                      ? `${selectedScoreTypeLabel} is listed in the selector now, but only the implemented scorecards are available in this version.`
                      : 'Choose the score type that matches this harvested buck record to continue.'}
                  </Text>
                </View>
              )}
            </ScrollView>

            <View style={[styles.modalFooter, { paddingBottom: Math.max(insets.bottom, spacing.md) }]}>
              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => setShowScoreModal(false)}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.submitButton, (!canEditScoreMeasurements || isSavingScore) && styles.disabledButton]}
                onPress={handleSaveScore}
                disabled={!canEditScoreMeasurements || isSavingScore}
              >
                {isSavingScore ? (
                  <ActivityIndicator size="small" color={colors.white} />
                ) : (
                  <Text style={styles.submitButtonText}>
                    {canEditScoreMeasurements ? 'Save Score' : 'Not Available Yet'}
                  </Text>
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
        quickFeedbackEnabled={isQuickFeedbackEligible()}
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
    backgroundColor: colors.harvestBg,
    borderWidth: 1,
    borderColor: colors.harvestBorder,
  },
  passBadge: {
    backgroundColor: colors.passBg,
    borderWidth: 1,
    borderColor: colors.passBorder,
  },
  unknownBadge: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
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
  unknownText: {
    color: colors.textMuted,
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
  retakeCard: {
    marginBottom: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.warning + '10',
  },
  retakeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  retakeTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.warning,
  },
  retakeText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  retakeCueText: {
    marginTop: spacing.sm,
    fontSize: 12,
    color: colors.textMuted,
    lineHeight: 18,
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
  scoreCard: {
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  scoreCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.sm,
  },
  scoreCardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreCardSubtitle: {
    marginTop: 2,
    fontSize: 12,
    color: colors.textMuted,
  },
  scoreHelperText: {
    fontSize: 14,
    lineHeight: 20,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  scoreDisclaimer: {
    fontSize: 12,
    lineHeight: 18,
    color: colors.textMuted,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  scoreReferenceNote: {
    fontSize: 12,
    lineHeight: 18,
    color: colors.textMuted,
    marginBottom: spacing.md,
  },
  scoreStatusBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    borderWidth: 1,
  },
  scoreReadyBadge: {
    backgroundColor: colors.harvestBg,
    borderColor: colors.harvestBorder,
  },
  scoreIncompleteBadge: {
    backgroundColor: colors.warning + '12',
    borderColor: colors.warning + '55',
  },
  scoreStatusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  scoreReadyText: {
    color: colors.harvest,
  },
  scoreIncompleteText: {
    color: colors.warning,
  },
  scoreCheckboxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  scoreCheckbox: {
    width: 22,
    height: 22,
    borderRadius: borderRadius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scoreCheckboxChecked: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  scoreCheckboxText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
    color: colors.textSecondary,
  },
  scoreReferenceGallery: {
    gap: spacing.sm,
    paddingBottom: spacing.sm,
  },
  scoreReferenceImage: {
    width: 220,
    height: 280,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  scoreTypePickerWrap: {
    marginBottom: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  scoreTypePicker: {
    color: colors.textPrimary,
    height: 54,
  },
  scoreTypeCard: {
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  scoreTypeCardSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary + '10',
  },
  scoreTypeCardTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.sm,
  },
  scoreTypeCardTitle: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreTypeCardTitleSelected: {
    color: colors.primary,
  },
  scoreTypePill: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderWidth: 1,
  },
  scoreTypeReadyPill: {
    backgroundColor: colors.harvestBg,
    borderColor: colors.harvestBorder,
  },
  scoreTypeSoonPill: {
    backgroundColor: colors.warning + '12',
    borderColor: colors.warning + '45',
  },
  scoreTypeMutedPill: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
  scoreTypePillText: {
    fontSize: 11,
    fontWeight: '600',
  },
  scoreTypeReadyPillText: {
    color: colors.harvest,
  },
  scoreTypeSoonPillText: {
    color: colors.warning,
  },
  scoreTypeMutedPillText: {
    color: colors.textMuted,
  },
  scoreTypeNoticeBox: {
    marginBottom: spacing.md,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  scoreTypeNoticeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  scoreTypeNoticeTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreTypeNoticeText: {
    fontSize: 13,
    lineHeight: 18,
    color: colors.textSecondary,
  },
  scoreTypeNoticeSubtext: {
    marginTop: spacing.sm,
    fontSize: 12,
    lineHeight: 18,
    color: colors.textMuted,
  },
  scoreMinimumsCard: {
    marginBottom: spacing.md,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.primary + '10',
    borderWidth: 1,
    borderColor: colors.primary + '25',
  },
  scoreMinimumsTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
    textTransform: 'uppercase',
  },
  scoreMinimumsRow: {
    flexDirection: 'row',
    gap: spacing.lg,
    flexWrap: 'wrap',
  },
  scoreMinimumsValue: {
    fontSize: 14,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  scoreInlineButton: {
    alignSelf: 'flex-start',
    marginBottom: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primary + '12',
    borderWidth: 1,
    borderColor: colors.primary + '35',
  },
  scoreInlineButtonText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '600',
  },
  scoreWarningsBox: {
    marginTop: spacing.sm,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.warning + '10',
    borderWidth: 1,
    borderColor: colors.warning + '35',
  },
  scoreWarningText: {
    fontSize: 12,
    lineHeight: 18,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  scoreWarningLastText: {
    marginBottom: 0,
  },
  scoreComingSoonBox: {
    marginTop: spacing.sm,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  scoreComingSoonTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.xs,
  },
  scoreComingSoonText: {
    fontSize: 13,
    lineHeight: 18,
    color: colors.textSecondary,
  },
  scoreSummaryEmpty: {
    fontSize: 14,
    lineHeight: 20,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  scoreSummaryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: spacing.sm,
  },
  scoreSummaryItem: {
    width: '50%',
    paddingRight: spacing.sm,
    paddingBottom: spacing.sm,
  },
  scoreTripleSummaryRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  scoreTripleSummaryItem: {
    flex: 1,
  },
  scoreSummaryLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: 2,
  },
  scoreSummaryValue: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreSummaryValueSmall: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreActionRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  scorePrimaryButton: {
    flex: 1,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  scorePrimaryButtonText: {
    color: colors.white,
    fontSize: 14,
    fontWeight: '600',
  },
  scoreSecondaryButton: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  scoreSecondaryButtonText: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '500',
  },
  scoreModalIntro: {
    fontSize: 13,
    lineHeight: 18,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  scoreSplitRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  scoreSplitColumn: {
    flex: 1,
  },
  scoreSpreadPairRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  scoreSpreadPairColumn: {
    flex: 1,
  },
  scorePointsTotalCard: {
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  scorePointsTotalLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: 4,
  },
  scorePointsTotalValue: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreGroupTitle: {
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
    fontSize: 15,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreSectionNote: {
    marginTop: spacing.xs,
    fontSize: 12,
    lineHeight: 18,
    color: colors.textMuted,
    marginBottom: spacing.sm,
  },
  scoreSubgroupTitle: {
    marginTop: spacing.md,
    marginBottom: spacing.sm,
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  scoreMeasureCard: {
    marginBottom: spacing.sm,
    padding: spacing.sm,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  scoreMeasureMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  scoreMeasureCardLabel: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreDifferenceBadge: {
    alignItems: 'flex-end',
  },
  scoreDifferenceBadgeLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.textMuted,
    textTransform: 'uppercase',
    marginBottom: 2,
  },
  scoreDifferenceBadgeValue: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  scoreMeasureInputHeaderRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  scoreMeasureSideHeader: {
    flex: 1,
    fontSize: 11,
    fontWeight: '600',
    color: colors.textMuted,
    textAlign: 'center',
  },
  scoreMeasureInputsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  scoreMeasureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  scoreMeasureLabel: {
    width: 40,
    fontSize: 13,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  scoreMeasureInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    color: colors.textPrimary,
    fontSize: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  scoreMeasurementField: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  scoreMeasurementFieldCompact: {
    flex: 1,
    gap: 4,
  },
  scoreMeasurementWholeInput: {
    width: 78,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    color: colors.textPrimary,
    fontSize: 16,
    borderWidth: 1,
    borderColor: colors.border,
    textAlign: 'center',
  },
  scoreMeasurementWholeInputCompact: {
    width: 42,
    fontSize: 14,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs,
  },
  scoreMeasurementFractionWrap: {
    flex: 1,
    minWidth: 110,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  scoreMeasurementFractionWrapCompact: {
    minWidth: 88,
  },
  scoreMeasurementFractionPicker: {
    color: colors.textPrimary,
    height: 50,
    width: '100%',
  },
  scoreMeasureDivider: {
    width: 20,
    textAlign: 'center',
    color: colors.textMuted,
    fontSize: 14,
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
