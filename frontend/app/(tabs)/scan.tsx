import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  Modal,
  ActivityIndicator,
  Image,
  Platform,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { Camera, ImagePlus, X, Zap, AlertTriangle } from 'lucide-react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { useAuthStore } from '../../stores/authStore';
import { useImageStore } from '../../stores/imageStore';
import { scanAPI, subscriptionAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';
import * as Crypto from 'expo-crypto';

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
  const cameraRef = useRef<CameraView>(null);

  useEffect(() => {
    checkSubscription();
  }, [isAuthenticated]);

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
        setShowDisclaimer(true);
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
      setShowDisclaimer(true);
    }
  };

  const analyzeDeer = async () => {
    if (!capturedImage || !isAuthenticated) return;

    setShowDisclaimer(false);
    setAnalyzing(true);

    try {
      // Generate local image ID
      const localImageId = await generateUUID();
      
      // Save image locally
      await saveImage(localImageId, capturedImage);

      // Send for analysis
      const response = await scanAPI.analyzeDeer({
        image_base64: capturedImage,
        local_image_id: localImageId,
      });

      // Update remaining scans
      if (user?.subscription_tier !== 'master_stag') {
        setScansRemaining((prev) => Math.max(0, prev - 1));
        updateUser({ scans_remaining: Math.max(0, scansRemaining - 1) });
      }

      // Navigate to result
      router.push(`/scan-result/${response.data.id}`);
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Analysis failed. Please try again.';
      Alert.alert('Error', message);
    } finally {
      setAnalyzing(false);
      setCapturedImage(null);
    }
  };

  const resetCapture = () => {
    setCapturedImage(null);
    setShowDisclaimer(false);
  };

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

  if (!permission) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={[styles.container, { paddingTop: insets.top }]}>
        <View style={styles.permissionContainer}>
          <Camera size={64} color={colors.primary} />
          <Text style={styles.permissionTitle}>Camera Access Required</Text>
          <Text style={styles.permissionText}>
            Iron Stag needs camera access to scan and analyze deer. Your photos are stored
            locally and never uploaded to our servers.
          </Text>
          <Button
            title="Grant Camera Access"
            onPress={requestPermission}
            style={styles.permissionButton}
          />
          <Button
            title="Upload from Gallery Instead"
            onPress={pickImage}
            variant="outline"
            style={styles.galleryButton}
          />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Scan Limit Indicator */}
      {user?.subscription_tier !== 'master_stag' && (
        <View style={[styles.scanLimit, { top: insets.top + spacing.md }]}>
          <Zap size={16} color={scansRemaining > 0 ? colors.primary : colors.error} />
          <Text style={[styles.scanLimitText, scansRemaining === 0 && styles.noScansText]}>
            {scansRemaining} scans remaining today
          </Text>
        </View>
      )}

      {capturedImage ? (
        // Preview captured image
        <View style={styles.previewContainer}>
          <Image source={{ uri: capturedImage }} style={styles.preview} resizeMode="contain" />
          <TouchableOpacity
            style={[styles.closeButton, { top: insets.top + spacing.md }]}
            onPress={resetCapture}
          >
            <X size={24} color={colors.textPrimary} />
          </TouchableOpacity>
        </View>
      ) : (
        // Camera view
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
      )}

      {/* Controls */}
      <View style={[styles.controls, { paddingBottom: insets.bottom + spacing.lg }]}>
        {!capturedImage ? (
          <>
            <TouchableOpacity style={styles.galleryPickerButton} onPress={pickImage}>
              <ImagePlus size={24} color={colors.textPrimary} />
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.captureButton, !cameraReady && styles.captureButtonDisabled]}
              onPress={takePicture}
              disabled={!cameraReady || scansRemaining === 0}
            >
              <View style={styles.captureInner} />
            </TouchableOpacity>
            <View style={styles.placeholder} />
          </>
        ) : (
          <Button
            title="Analyze Deer"
            onPress={() => setShowDisclaimer(true)}
            size="large"
            style={styles.analyzeButton}
            disabled={scansRemaining === 0}
          />
        )}
      </View>

      {/* Analyzing Overlay */}
      {analyzing && (
        <View style={styles.analyzingOverlay}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.analyzingText}>Analyzing deer...</Text>
          <Text style={styles.analyzingSubtext}>This may take a few seconds</Text>
        </View>
      )}

      {/* Disclaimer Modal */}
      <Modal visible={showDisclaimer} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <Card style={styles.disclaimerCard}>
            <View style={styles.disclaimerIcon}>
              <AlertTriangle size={32} color={colors.warning} />
            </View>
            <Text style={styles.disclaimerTitle}>Before You Continue</Text>
            <Text style={styles.disclaimerText}>
              AI analysis is a tool to assist your judgment, not replace it. Always follow local
              regulations and practice ethical hunting. The recommendation provided is an estimate
              based on visible characteristics.
            </Text>
            <View style={styles.disclaimerButtons}>
              <Button
                title="Cancel"
                onPress={() => setShowDisclaimer(false)}
                variant="outline"
                style={styles.disclaimerButton}
              />
              <Button
                title="I Understand"
                onPress={analyzeDeer}
                style={styles.disclaimerButton}
              />
            </View>
          </Card>
        </View>
      </Modal>
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
  noScansText: {
    color: colors.error,
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
  controls: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingVertical: spacing.lg,
    backgroundColor: colors.backgroundCard,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  galleryPickerButton: {
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
  placeholder: {
    width: 50,
  },
  analyzeButton: {
    flex: 1,
    marginHorizontal: spacing.lg,
  },
  analyzingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(14, 26, 20, 0.95)',
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
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  disclaimerCard: {
    width: '100%',
    maxWidth: 400,
    padding: spacing.lg,
  },
  disclaimerIcon: {
    alignSelf: 'center',
    marginBottom: spacing.md,
  },
  disclaimerTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  disclaimerText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  disclaimerButtons: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  disclaimerButton: {
    flex: 1,
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
  permissionContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  permissionTitle: {
    fontSize: 24,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  permissionText: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: spacing.lg,
  },
  permissionButton: {
    minWidth: 250,
    marginBottom: spacing.md,
  },
  galleryButton: {
    minWidth: 250,
  },
});
