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
import { X, Check, Target, AlertCircle } from 'lucide-react-native';
import { colors, spacing, borderRadius } from '../constants/theme';
import { scanAPI } from '../utils/api';

interface LabelFeedbackModalProps {
  visible: boolean;
  onClose: () => void;
  scanId: string;
  predictedAge: number | null;
  onLabelSubmitted?: () => void;
}

type LabelMode = 'select' | 'exact' | 'quick';

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
  onLabelSubmitted,
}: LabelFeedbackModalProps) {
  const [mode, setMode] = useState<LabelMode>('select');
  const [exactAge, setExactAge] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const resetAndClose = () => {
    setMode('select');
    setExactAge('');
    onClose();
  };

  const handleSubmitExactAge = async () => {
    const age = parseFloat(exactAge);
    if (isNaN(age) || age < 0 || age > 15) {
      Alert.alert('Invalid Age', 'Please enter a valid age between 0 and 15 years.');
      return;
    }
    
    setIsSubmitting(true);
    try {
      await scanAPI.addLabel(scanId, {
        reported_age: age,
        harvest_confirmed: true,
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
        style={styles.modeButton}
        onPress={() => setMode('quick')}
      >
        <View style={styles.modeButtonContent}>
          <Text style={styles.modeButtonTitle}>Quick feedback</Text>
          <Text style={styles.modeButtonSubtitle}>Was it spot on, close, or way off?</Text>
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
      
      <TouchableOpacity 
        style={[styles.submitButton, isSubmitting && styles.submitButtonDisabled]}
        onPress={handleSubmitExactAge}
        disabled={isSubmitting || !exactAge}
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
