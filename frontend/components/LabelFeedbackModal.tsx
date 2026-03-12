import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
  ScrollView,
} from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { X, Check, Target, AlertCircle } from 'lucide-react-native';
import { colors, spacing, borderRadius } from '../constants/theme';
import { scanAPI } from '../utils/api';

interface LabelFeedbackModalProps {
  visible: boolean;
  onClose: () => void;
  scanId: string;
  predictedAge: number | null;
  quickFeedbackEnabled?: boolean;
  onLabelSubmitted?: () => void;
}

type LabelMode = 'select' | 'exact' | 'quick';

const AGE_SOURCE_OPTIONS = [
  { label: 'Select source...', value: '' },
  { label: 'Jawbone', value: 'jawbone' },
  { label: 'Tooth wear', value: 'tooth_wear' },
  { label: 'Taxidermist', value: 'taxidermist' },
  { label: 'Biologist assessment', value: 'biologist_assessment' },
  { label: 'Hunter best estimate', value: 'hunter_best_estimate' },
  { label: 'Other', value: 'other' },
] as const;

const LABELER_ROLE_OPTIONS = [
  { label: 'Self', value: 'self' },
  { label: 'Guide', value: 'guide' },
  { label: 'Biologist', value: 'biologist' },
  { label: 'Taxidermist', value: 'taxidermist' },
  { label: 'Admin', value: 'admin' },
  { label: 'Processor', value: 'processor' },
  { label: 'Unknown', value: 'unknown' },
] as const;

/**
 * Label Feedback Modal for Phase 2 Empirical Calibration
 * 
 * UX Principles:
 * - Optional, respectful, skippable
 * - Zero guilt language
 * - Two paths: Harvest (exact age) or Quick feedback
 */
export function LabelFeedbackModal({
  visible,
  onClose,
  scanId,
  predictedAge,
  quickFeedbackEnabled = true,
  onLabelSubmitted,
}: LabelFeedbackModalProps) {
  const [mode, setMode] = useState<LabelMode>('select');
  const [exactAge, setExactAge] = useState('');
  const [ageSource, setAgeSource] = useState('');
  const [labelerRole, setLabelerRole] = useState('self');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const resetAndClose = () => {
    setMode('select');
    setExactAge('');
    setAgeSource('');
    setLabelerRole('self');
    onClose();
  };

  const handleSubmitExactAge = async () => {
    const age = parseFloat(exactAge);
    if (isNaN(age) || age < 0 || age > 15.5) {
      Alert.alert('Invalid Age', 'Please enter a valid age between 0 and 15.5 years.');
      return;
    }
    if (!ageSource) {
      Alert.alert('Age Source Needed', 'Select how the exact age was determined so we can weight the label correctly.');
      return;
    }
    
    setIsSubmitting(true);
    try {
      await scanAPI.addLabel(scanId, {
        reported_age: age,
        harvest_confirmed: true,
        age_source: ageSource as any,
        labeler_role: labelerRole as any,
      });
      Alert.alert('Thanks!', 'Your feedback helps improve accuracy for everyone.');
      onLabelSubmitted?.();
      resetAndClose();
    } catch (error: any) {
      if (error.response?.status === 400 && error.response?.data?.detail?.includes('already exists')) {
        Alert.alert('Already Labeled', 'This scan already has feedback. You can delete the existing label from the scan details page to re-label.');
      } else {
        Alert.alert('Error', 'Failed to save feedback. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleQuickFeedback = async (category: 'exact' | 'close' | 'off') => {
    setIsSubmitting(true);
    try {
      await scanAPI.addLabel(scanId, {
        accuracy_category: category,
        harvest_confirmed: false,
      });
      Alert.alert('Thanks!', 'Your feedback helps improve accuracy for everyone.');
      onLabelSubmitted?.();
      resetAndClose();
    } catch (error: any) {
      if (error.response?.status === 400 && error.response?.data?.detail?.includes('already exists')) {
        Alert.alert('Already Labeled', 'This scan already has feedback.');
      } else {
        Alert.alert('Error', 'Failed to save feedback. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderSelectMode = () => (
    <View style={styles.selectContainer}>
      <Text style={styles.modalTitle}>How did this estimate hold up?</Text>
      <Text style={styles.modalSubtitle}>Only if you know — totally optional.</Text>
      
      {predictedAge !== null && predictedAge > 0 && (
        <View style={styles.predictionCard}>
          <Target size={16} color={colors.primary} />
          <Text style={styles.predictionText}>
            We estimated: <Text style={styles.predictionAge}>{predictedAge} years</Text>
          </Text>
        </View>
      )}
      
      <TouchableOpacity 
        style={styles.modeButton}
        onPress={() => setMode('exact')}
      >
        <View style={styles.modeButtonContent}>
          <Text style={styles.modeButtonTitle}>I harvested this deer</Text>
          <Text style={styles.modeButtonSubtitle}>Enter the actual age (most helpful)</Text>
        </View>
        <Check size={20} color={colors.primary} />
      </TouchableOpacity>
      
      <TouchableOpacity 
        style={[styles.modeButton, !quickFeedbackEnabled && styles.modeButtonDisabled]}
        onPress={() => {
          if (quickFeedbackEnabled) {
            setMode('quick');
          }
        }}
        disabled={!quickFeedbackEnabled}
      >
        <View style={styles.modeButtonContent}>
          <Text style={styles.modeButtonTitle}>Quick feedback</Text>
          <Text style={styles.modeButtonSubtitle}>
            {quickFeedbackEnabled
              ? 'Was it spot on, close, or way off?'
              : 'Unlocks 7 days after the scan so you have time to compare it in the field.'}
          </Text>
        </View>
        <AlertCircle size={20} color={colors.textMuted} />
      </TouchableOpacity>
      
      <TouchableOpacity style={styles.skipButton} onPress={resetAndClose}>
        <Text style={styles.skipText}>Maybe later</Text>
      </TouchableOpacity>
    </View>
  );

  const renderExactMode = () => (
    <View style={styles.exactContainer}>
      <TouchableOpacity style={styles.backButton} onPress={() => setMode('select')}>
        <Text style={styles.backText}>← Back</Text>
      </TouchableOpacity>
      
      <Text style={styles.modalTitle}>Enter actual age</Text>
      <Text style={styles.modalSubtitle}>
        Based on jawbone or professional assessment
      </Text>
      
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.ageInput}
          value={exactAge}
          onChangeText={setExactAge}
          placeholder="e.g., 4.5"
          placeholderTextColor={colors.textMuted}
          keyboardType="decimal-pad"
          autoFocus
        />
        <Text style={styles.inputSuffix}>years</Text>
      </View>

      <View style={styles.fieldGroup}>
        <Text style={styles.fieldLabel}>How was the age determined?</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={ageSource}
            onValueChange={(value) => setAgeSource(value)}
            style={styles.picker}
            dropdownIconColor={colors.textPrimary}
          >
            {AGE_SOURCE_OPTIONS.map((option) => (
              <Picker.Item key={option.value || 'blank'} label={option.label} value={option.value} />
            ))}
          </Picker>
        </View>
      </View>

      <View style={styles.fieldGroup}>
        <Text style={styles.fieldLabel}>Who supplied the age?</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={labelerRole}
            onValueChange={(value) => setLabelerRole(value)}
            style={styles.picker}
            dropdownIconColor={colors.textPrimary}
          >
            {LABELER_ROLE_OPTIONS.map((option) => (
              <Picker.Item key={option.value} label={option.label} value={option.value} />
            ))}
          </Picker>
        </View>
      </View>

      <Text style={styles.helperText}>
        Exact-age labels are most useful when the source is jawbone, tooth wear, or a professional assessment.
      </Text>
      
      <TouchableOpacity 
        style={[styles.submitButton, isSubmitting && styles.submitButtonDisabled]}
        onPress={handleSubmitExactAge}
        disabled={isSubmitting || !exactAge || !ageSource}
      >
        {isSubmitting ? (
          <ActivityIndicator color={colors.white} size="small" />
        ) : (
          <Text style={styles.submitButtonText}>Submit</Text>
        )}
      </TouchableOpacity>
      
      <TouchableOpacity style={styles.skipButton} onPress={resetAndClose}>
        <Text style={styles.skipText}>Cancel</Text>
      </TouchableOpacity>
    </View>
  );

  const renderQuickMode = () => (
    <View style={styles.quickContainer}>
      <TouchableOpacity style={styles.backButton} onPress={() => setMode('select')}>
        <Text style={styles.backText}>← Back</Text>
      </TouchableOpacity>
      
      <Text style={styles.modalTitle}>Quick feedback</Text>
      {predictedAge !== null && predictedAge > 0 ? (
        <Text style={styles.modalSubtitle}>
          How close was our estimate of {predictedAge} years?
        </Text>
      ) : (
        <Text style={styles.modalSubtitle}>How'd we do?</Text>
      )}
      
      <View style={styles.quickButtons}>
        <TouchableOpacity 
          style={[styles.quickButton, styles.quickExact]}
          onPress={() => handleQuickFeedback('exact')}
          disabled={isSubmitting}
        >
          <Text style={styles.quickButtonEmoji}>🎯</Text>
          <Text style={styles.quickButtonText}>Spot on</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[styles.quickButton, styles.quickClose]}
          onPress={() => handleQuickFeedback('close')}
          disabled={isSubmitting}
        >
          <Text style={styles.quickButtonEmoji}>👍</Text>
          <Text style={styles.quickButtonText}>Close enough</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={[styles.quickButton, styles.quickOff]}
          onPress={() => handleQuickFeedback('off')}
          disabled={isSubmitting}
        >
          <Text style={styles.quickButtonEmoji}>🤷</Text>
          <Text style={styles.quickButtonText}>Way off</Text>
        </TouchableOpacity>
      </View>
      
      {isSubmitting && (
        <ActivityIndicator style={styles.quickLoading} color={colors.primary} />
      )}
      
      <TouchableOpacity style={styles.skipButton} onPress={resetAndClose}>
        <Text style={styles.skipText}>Cancel</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={resetAndClose}
    >
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.overlay}
      >
        <View style={styles.container}>
          {/* Close button */}
          <TouchableOpacity style={styles.closeButton} onPress={resetAndClose}>
            <X size={24} color={colors.textMuted} />
          </TouchableOpacity>
          
          <ScrollView 
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled"
          >
            {mode === 'select' && renderSelectMode()}
            {mode === 'exact' && renderExactMode()}
            {mode === 'quick' && renderQuickMode()}
          </ScrollView>
          
          {/* Privacy footer */}
          <Text style={styles.privacyText}>
            Your feedback is stored anonymously and only used to improve confidence accuracy.
          </Text>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  container: {
    backgroundColor: colors.background,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    maxHeight: '80%',
    minHeight: 320,
  },
  closeButton: {
    position: 'absolute',
    top: spacing.md,
    right: spacing.md,
    zIndex: 10,
    padding: spacing.xs,
  },
  content: {
    padding: spacing.lg,
    paddingTop: spacing.xl,
  },
  
  // Select mode
  selectContainer: {
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  modalSubtitle: {
    fontSize: 14,
    color: colors.textMuted,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  predictionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary + '10',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  predictionText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  predictionAge: {
    fontWeight: '600',
    color: colors.primary,
  },
  modeButton: {
    width: '100%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  modeButtonDisabled: {
    opacity: 0.55,
  },
  modeButtonContent: {
    flex: 1,
  },
  modeButtonTitle: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  modeButtonSubtitle: {
    fontSize: 12,
    color: colors.textMuted,
  },
  skipButton: {
    marginTop: spacing.md,
    padding: spacing.sm,
  },
  skipText: {
    fontSize: 14,
    color: colors.textMuted,
  },
  
  // Exact mode
  exactContainer: {
    alignItems: 'center',
  },
  backButton: {
    alignSelf: 'flex-start',
    marginBottom: spacing.md,
  },
  backText: {
    fontSize: 14,
    color: colors.primary,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: spacing.lg,
    gap: spacing.sm,
  },
  ageInput: {
    width: 120,
    fontSize: 32,
    fontWeight: '600',
    color: colors.textPrimary,
    textAlign: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderWidth: 2,
    borderColor: colors.primary,
  },
  inputSuffix: {
    fontSize: 18,
    color: colors.textMuted,
  },
  fieldGroup: {
    width: '100%',
    marginBottom: spacing.md,
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: '500',
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  pickerWrapper: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surface,
    overflow: 'hidden',
  },
  picker: {
    color: colors.textPrimary,
  },
  helperText: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    lineHeight: 18,
    marginBottom: spacing.lg,
  },
  submitButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.lg,
    minWidth: 150,
    alignItems: 'center',
  },
  submitButtonDisabled: {
    opacity: 0.6,
  },
  submitButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.white,
  },
  
  // Quick mode
  quickContainer: {
    alignItems: 'center',
  },
  quickButtons: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginVertical: spacing.lg,
  },
  quickButton: {
    flex: 1,
    alignItems: 'center',
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
  },
  quickExact: {
    backgroundColor: colors.harvest + '10',
    borderColor: colors.harvest + '30',
  },
  quickClose: {
    backgroundColor: colors.primary + '10',
    borderColor: colors.primary + '30',
  },
  quickOff: {
    backgroundColor: colors.textMuted + '10',
    borderColor: colors.textMuted + '30',
  },
  quickButtonEmoji: {
    fontSize: 28,
    marginBottom: spacing.xs,
  },
  quickButtonText: {
    fontSize: 12,
    fontWeight: '500',
    color: colors.textPrimary,
    textAlign: 'center',
  },
  quickLoading: {
    marginBottom: spacing.md,
  },
  
  // Privacy footer
  privacyText: {
    fontSize: 11,
    color: colors.textMuted,
    textAlign: 'center',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.lg,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
});

export default LabelFeedbackModal;
