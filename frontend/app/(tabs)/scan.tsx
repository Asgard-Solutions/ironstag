import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Modal,
  ActivityIndicator,
  Image,
  ScrollView,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { 
  Camera, 
  ImagePlus, 
  X, 
  Zap, 
  AlertTriangle, 
  ArrowLeft,
  Target,
  Info,
  Check,
  XCircle,
  HelpCircle,
  FileText,
} from 'lucide-react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { useAuthStore } from '../../stores/authStore';
import { useImageStore } from '../../stores/imageStore';
import { scanAPI, subscriptionAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';
import * as Crypto from 'expo-crypto';

type ScanStep = 'main' | 'camera' | 'preview' | 'analyzing';

export default function ScanScreen() {
  const insets = useSafeAreaInsets();
  const { isAuthenticated, user, updateUser } = useAuthStore();
  const { saveImage } = useImageStore();
  
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraReady, setCameraReady] = useState(false);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [scansRemaining, setScansRemaining] = useState(user?.scans_remaining || 3);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [scanStep, setScanStep] = useState<ScanStep>('main');
  const cameraRef = useRef<CameraView>(null);

  const checkSubscription = async () => {
    if (!isAuthenticated) return;
    try {
      const response = await subscriptionAPI.getStatus();
      setScansRemaining(response.data.scans_remaining);
      updateUser({ scans_remaining: response.data.scans_remaining });
    } catch (error) {
      console.error('Failed to check subscription:', error);
    }
  };

  const generateUUID = async (): Promise<string> => {
    return Crypto.randomUUID();
  };

  const takePicture = async () => {
    if (!cameraRef.current || !cameraReady) return;

    try {
      const photo = await cameraRef.current.takePictureAsync({
        base64: true,
        quality: 0.8,
      });
      if (photo?.base64) {
        setCapturedImage(`data:image/jpeg;base64,${photo.base64}`);
        setScanStep('preview');
      }
    } catch (error) {
      console.error('Failed to take picture:', error);
      Alert.alert('Error', 'Failed to capture image. Please try again.');
    }
  };

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
      base64: true,
    });

    if (!result.canceled && result.assets[0].base64) {
      setCapturedImage(`data:image/jpeg;base64,${result.assets[0].base64}`);
      setScanStep('preview');
    }
  };

  const analyzeDeer = async () => {
    if (!capturedImage || !isAuthenticated) return;

    setScanStep('analyzing');
    setAnalyzing(true);

    try {
      const localImageId = await generateUUID();
      await saveImage(localImageId, capturedImage);

      const response = await scanAPI.analyzeDeer({
        image_base64: capturedImage,
        local_image_id: localImageId,
      });

      if (user?.subscription_tier !== 'master_stag') {
        setScansRemaining((prev) => Math.max(0, prev - 1));
        updateUser({ scans_remaining: Math.max(0, scansRemaining - 1) });
      }

      router.push(`/scan-result/${response.data.id}`);
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Analysis failed. Please try again.';
      Alert.alert('Error', message);
      setScanStep('main');
    } finally {
      setAnalyzing(false);
      setCapturedImage(null);
    }
  };

  const resetCapture = () => {
    setCapturedImage(null);
    setScanStep('main');
  };

  const openCamera = async () => {
    if (!permission?.granted) {
      const result = await requestPermission();
      if (!result.granted) {
        Alert.alert('Permission Required', 'Camera access is needed to scan deer.');
        return;
      }
    }
    setScanStep('camera');
  };

  // Auth required screen
  if (!isAuthenticated) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <View style={styles.authRequired}>
          <Camera size={64} color={colors.textMuted} />
          <Text style={styles.authTitle}>Sign In Required</Text>
          <Text style={styles.authText}>
            Please sign in to scan deer and access AI-powered analysis.
          </Text>
          <Button
            title="Sign In"
            onPress={() => router.push('/(auth)/login')}
            style={styles.authButton}
          />
        </View>
      </View>
    );
  }

  // Camera view
  if (scanStep === 'camera') {
    return (
      <View style={styles.container}>
        {user?.subscription_tier !== 'master_stag' && (
          <View style={[styles.scanLimit, { top: insets.top + spacing.md }]}>
            <Zap size={16} color={scansRemaining > 0 ? colors.primary : colors.error} />
            <Text style={[styles.scanLimitText, scansRemaining === 0 && styles.noScansText]}>
              {scansRemaining} scans remaining today
            </Text>
          </View>
        )}

        <CameraView
          ref={cameraRef}
          style={styles.camera}
          facing="back"
          onCameraReady={() => setCameraReady(true)}
        >
          <View style={styles.overlay}>
            <View style={styles.cornerTL} />
            <View style={styles.cornerTR} />
            <View style={styles.cornerBL} />
            <View style={styles.cornerBR} />
          </View>
        </CameraView>

        <View style={[styles.cameraControls, { paddingBottom: insets.bottom + spacing.lg }]}>
          <TouchableOpacity style={styles.controlButton} onPress={() => setScanStep('main')}>
            <X size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.captureButton, !cameraReady && styles.captureButtonDisabled]}
            onPress={takePicture}
            disabled={!cameraReady || scansRemaining === 0}
          >
            <View style={styles.captureInner} />
          </TouchableOpacity>
          <TouchableOpacity style={styles.controlButton} onPress={pickImage}>
            <ImagePlus size={24} color={colors.textPrimary} />
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // Preview view
  if (scanStep === 'preview' && capturedImage) {
    return (
      <View style={styles.container}>
        <View style={styles.previewContainer}>
          <Image source={{ uri: capturedImage }} style={styles.preview} resizeMode="contain" />
          <TouchableOpacity
            style={[styles.closeButton, { top: insets.top + spacing.md }]}
            onPress={resetCapture}
          >
            <X size={24} color={colors.textPrimary} />
          </TouchableOpacity>
        </View>

        <View style={[styles.previewControls, { paddingBottom: insets.bottom + spacing.lg }]}>
          <Button
            title="Retake"
            onPress={resetCapture}
            variant="outline"
            style={styles.previewButton}
          />
          <Button
            title="Analyze Deer"
            onPress={analyzeDeer}
            style={styles.previewButton}
            disabled={scansRemaining === 0}
          />
        </View>
      </View>
    );
  }

  // Analyzing view
  if (scanStep === 'analyzing') {
    return (
      <View style={[styles.container, styles.analyzingContainer]}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.analyzingText}>Analyzing deer...</Text>
        <Text style={styles.analyzingSubtext}>This may take a few seconds</Text>
      </View>
    );
  }

  // Main scan screen
  return (
    <View style={[styles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <ArrowLeft size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <View style={styles.headerText}>
          <Text style={styles.headerTitle}>Iron Stag</Text>
          <Text style={styles.headerSubtitle}>Precision for Ethical Hunters</Text>
        </View>
        <TouchableOpacity style={styles.infoButton} onPress={() => setShowDisclaimer(true)}>
          <FileText size={20} color={colors.textMuted} />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.mainContent}>
        {/* Target Icon */}
        <View style={styles.targetContainer}>
          <View style={styles.targetOuter}>
            <View style={styles.targetMiddle}>
              <View style={styles.targetInner}>
                <View style={styles.targetDot} />
              </View>
            </View>
          </View>
        </View>

        {/* Scan Info */}
        <Text style={styles.scanTitle}>Scan a Deer</Text>
        <Text style={styles.scanDescription}>
          Take or upload a clear photo of the deer. Our AI will analyze body characteristics, antler development, and other indicators to provide an age estimation.
        </Text>

        {/* Scans Remaining */}
        {user?.subscription_tier !== 'master_stag' && (
          <View style={styles.scansRemainingCard}>
            <Zap size={18} color={scansRemaining > 0 ? colors.primary : colors.error} />
            <Text style={[styles.scansRemainingText, scansRemaining === 0 && styles.noScansText]}>
              {scansRemaining} scans remaining today
            </Text>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionButtons}>
          <Button
            title="Take Photo"
            onPress={openCamera}
            size="large"
            style={styles.primaryActionButton}
            disabled={scansRemaining === 0}
            icon={<Camera size={20} color={colors.background} />}
          />
          <Button
            title="Choose from Library"
            onPress={pickImage}
            size="large"
            variant="secondary"
            style={styles.secondaryActionButton}
            disabled={scansRemaining === 0}
            icon={<ImagePlus size={20} color={colors.textPrimary} />}
          />
        </View>
      </ScrollView>

      {/* Disclaimer Modal */}
      <Modal visible={showDisclaimer} animationType="slide">
        <DisclaimerScreen onClose={() => setShowDisclaimer(false)} />
      </Modal>
    </View>
  );
}

// Disclaimer Screen Component
function DisclaimerScreen({ onClose }: { onClose: () => void }) {
  const insets = useSafeAreaInsets();

  const mustDoItems = [
    'Use your own field assessment and professional judgment',
    'Comply with ALL local hunting laws and regulations',
    'Follow property rules and safety guidelines',
    'Verify ALL information before taking action',
    'Consult wildlife professionals for management advice',
    'Never rely solely on AI estimations for hunting decisions',
  ];

  const providesItems = [
    'AI-generated age estimations',
    'Body condition observations',
    'Antler development analysis',
    'General harvest guidance',
  ];

  const doesNotProvideItems = [
    'Professional wildlife advice',
    'Legal hunting guidance',
    'Definitive age determinations',
    'Guaranteed accuracy',
  ];

  return (
    <View style={[disclaimerStyles.container, { paddingTop: insets.top }]}>
      {/* Header */}
      <View style={disclaimerStyles.header}>
        <TouchableOpacity style={disclaimerStyles.backButton} onPress={onClose}>
          <ArrowLeft size={24} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={disclaimerStyles.headerTitle}>Scanning Disclaimer</Text>
        <View style={disclaimerStyles.placeholder} />
      </View>

      <ScrollView 
        contentContainerStyle={disclaimerStyles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Warning Header */}
        <View style={disclaimerStyles.warningHeader}>
          <View style={disclaimerStyles.warningIcon}>
            <AlertTriangle size={24} color="#DC2626" />
          </View>
          <Text style={disclaimerStyles.warningTitle}>Critical: Read Before Scanning</Text>
          <Text style={disclaimerStyles.warningSubtitle}>
            Important information about AI deer analysis
          </Text>
        </View>

        {/* Critical Responsibility Card */}
        <Card style={disclaimerStyles.criticalCard}>
          <View style={disclaimerStyles.criticalHeader}>
            <Info size={18} color="#DC2626" />
            <Text style={disclaimerStyles.criticalTitle}>CRITICAL: Your Responsibility</Text>
          </View>
          <Text style={disclaimerStyles.criticalText}>
            Iron Stag is an AI estimation tool for informational purposes ONLY. It does NOT provide professional wildlife management advice, legal guidance, or definitive age determinations.
          </Text>
          <Text style={disclaimerStyles.responsibilityText}>
            YOU are solely responsible for ALL hunting decisions.
          </Text>
          
          <Text style={disclaimerStyles.mustTitle}>You MUST:</Text>
          {mustDoItems.map((item, index) => (
            <View key={index} style={disclaimerStyles.bulletRow}>
              <Text style={disclaimerStyles.bullet}>•</Text>
              <Text style={disclaimerStyles.bulletText}>{item}</Text>
            </View>
          ))}
          
          <Text style={disclaimerStyles.footerNote}>
            AI estimations may be inaccurate. This app is a tool to supplement YOUR expertise, NOT replace it.
          </Text>
        </Card>

        {/* What This App Provides */}
        <Card style={disclaimerStyles.infoCard}>
          <View style={disclaimerStyles.infoHeader}>
            <Check size={18} color={colors.harvest} />
            <Text style={disclaimerStyles.infoTitle}>What This App Provides</Text>
          </View>
          {providesItems.map((item, index) => (
            <View key={index} style={disclaimerStyles.bulletRow}>
              <Check size={14} color={colors.harvest} />
              <Text style={disclaimerStyles.infoText}>{item}</Text>
            </View>
          ))}
        </Card>

        {/* What This App Does NOT Provide */}
        <Card style={disclaimerStyles.infoCard}>
          <View style={disclaimerStyles.infoHeader}>
            <XCircle size={18} color={colors.error} />
            <Text style={disclaimerStyles.infoTitleRed}>What This App Does NOT Provide</Text>
          </View>
          {doesNotProvideItems.map((item, index) => (
            <View key={index} style={disclaimerStyles.bulletRow}>
              <XCircle size={14} color={colors.error} />
              <Text style={disclaimerStyles.infoText}>{item}</Text>
            </View>
          ))}
        </Card>

        {/* Understanding Your Results */}
        <Card style={disclaimerStyles.understandingCard}>
          <View style={disclaimerStyles.infoHeader}>
            <HelpCircle size={18} color={colors.info} />
            <Text style={disclaimerStyles.understandingTitle}>Understanding Your Results</Text>
          </View>
          <Text style={disclaimerStyles.understandingText}>
            Results include confidence percentages indicating AI certainty. Lower confidence means more uncertainty. Always combine AI analysis with your own field observations, local knowledge, and applicable regulations before making any decisions.
          </Text>
        </Card>

        {/* Continue Button */}
        <Button
          title="I Understand"
          onPress={onClose}
          size="large"
          style={disclaimerStyles.continueButton}
        />
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
    paddingHorizontal: spacing.md,
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
  },
  headerText: {
    flex: 1,
    marginLeft: spacing.md,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  headerSubtitle: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  infoButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.backgroundCard,
    justifyContent: 'center',
    alignItems: 'center',
  },
  mainContent: {
    padding: spacing.lg,
    alignItems: 'center',
  },
  targetContainer: {
    marginTop: spacing.xl,
    marginBottom: spacing.xl,
  },
  targetOuter: {
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  targetMiddle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  targetInner: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  targetDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.primary,
  },
  scanTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  scanDescription: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: spacing.lg,
    paddingHorizontal: spacing.md,
  },
  scansRemainingCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.backgroundCard,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.full,
    marginBottom: spacing.xl,
  },
  scansRemainingText: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  noScansText: {
    color: colors.error,
  },
  actionButtons: {
    width: '100%',
    gap: spacing.md,
  },
  primaryActionButton: {
    width: '100%',
  },
  secondaryActionButton: {
    width: '100%',
  },
  camera: {
    flex: 1,
  },
  overlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  cornerTL: {
    position: 'absolute',
    top: '25%',
    left: '15%',
    width: 40,
    height: 40,
    borderTopWidth: 3,
    borderLeftWidth: 3,
    borderColor: colors.primary,
  },
  cornerTR: {
    position: 'absolute',
    top: '25%',
    right: '15%',
    width: 40,
    height: 40,
    borderTopWidth: 3,
    borderRightWidth: 3,
    borderColor: colors.primary,
  },
  cornerBL: {
    position: 'absolute',
    bottom: '25%',
    left: '15%',
    width: 40,
    height: 40,
    borderBottomWidth: 3,
    borderLeftWidth: 3,
    borderColor: colors.primary,
  },
  cornerBR: {
    position: 'absolute',
    bottom: '25%',
    right: '15%',
    width: 40,
    height: 40,
    borderBottomWidth: 3,
    borderRightWidth: 3,
    borderColor: colors.primary,
  },
  scanLimit: {
    position: 'absolute',
    left: spacing.md,
    zIndex: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: 'rgba(0,0,0,0.7)',
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.full,
  },
  scanLimitText: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: '500',
  },
  cameraControls: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingVertical: spacing.lg,
    backgroundColor: colors.backgroundCard,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  controlButton: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  captureButton: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 4,
    borderColor: colors.primaryDark,
  },
  captureButtonDisabled: {
    opacity: 0.5,
  },
  captureInner: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: colors.primary,
    borderWidth: 2,
    borderColor: colors.background,
  },
  previewContainer: {
    flex: 1,
    backgroundColor: colors.background,
  },
  preview: {
    flex: 1,
  },
  closeButton: {
    position: 'absolute',
    right: spacing.md,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  previewControls: {
    flexDirection: 'row',
    gap: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.backgroundCard,
  },
  previewButton: {
    flex: 1,
  },
  analyzingContainer: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  analyzingText: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: '600',
    marginTop: spacing.lg,
  },
  analyzingSubtext: {
    color: colors.textMuted,
    fontSize: 14,
    marginTop: spacing.sm,
  },
  authRequired: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  authTitle: {
    fontSize: 24,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  authText: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  authButton: {
    minWidth: 200,
  },
});

const disclaimerStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0E1A14',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
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
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  placeholder: {
    width: 40,
  },
  scrollContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  warningHeader: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  warningIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#FEE2E2',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  warningTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.xs,
  },
  warningSubtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  criticalCard: {
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FECACA',
    marginBottom: spacing.md,
  },
  criticalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  criticalTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#DC2626',
  },
  criticalText: {
    fontSize: 14,
    color: '#7F1D1D',
    lineHeight: 22,
    marginBottom: spacing.md,
  },
  responsibilityText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#DC2626',
    marginBottom: spacing.md,
  },
  mustTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: '#7F1D1D',
    marginBottom: spacing.sm,
  },
  bulletRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  bullet: {
    fontSize: 14,
    color: '#7F1D1D',
    lineHeight: 22,
  },
  bulletText: {
    flex: 1,
    fontSize: 14,
    color: '#7F1D1D',
    lineHeight: 22,
  },
  footerNote: {
    fontSize: 13,
    color: '#DC2626',
    fontStyle: 'italic',
    marginTop: spacing.md,
    lineHeight: 20,
  },
  infoCard: {
    backgroundColor: colors.backgroundCard,
    marginBottom: spacing.md,
  },
  infoHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  infoTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.harvest,
  },
  infoTitleRed: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.error,
  },
  infoText: {
    flex: 1,
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  understandingCard: {
    backgroundColor: 'rgba(33, 150, 243, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(33, 150, 243, 0.3)',
    marginBottom: spacing.xl,
  },
  understandingTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.info,
  },
  understandingText: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  continueButton: {
    marginBottom: spacing.xl,
  },
});
