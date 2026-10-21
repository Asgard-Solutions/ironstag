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
  ScrollView,
  Platform,
  Linking,
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
  Info,
  Check,
  XCircle,
  HelpCircle,
  FileText,
  ArrowLeft,
  Crown,
  MapPin,
  RotateCcw,
  Calendar,
  Crop,
} from 'lucide-react-native';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { OfflineBanner } from '../../components/OfflineIndicator';
import { useAuthStore } from '../../stores/authStore';
import { useImageStore } from '../../stores/imageStore';
import { offlineQueue } from '../../services/OfflineQueueService';
import { useOfflineQueue } from '../../hooks/useOfflineQueue';
import { useRevenueCat } from '../../hooks/useRevenueCat';
import { scanAPI, subscriptionAPI, authAPI } from '../../utils/api';
import { StatePicker, getStateName } from '../../components/StatePicker';
import { Picker } from '@react-native-picker/picker';
import { colors, spacing, borderRadius } from '../../constants/theme';
import { format } from 'date-fns';
import { PhotoTray } from '../../components/scan/PhotoTray';
import { CropModal } from '../../components/scan/CropModal';
import {
  CropRect,
  MAX_SCAN_PHOTOS,
  ScanPhoto,
  ScanRequestImage,
  newId,
  normalizePhoto,
  toRequestImages,
} from '../../utils/scanPhotos';

type ScanStep = 'main' | 'camera' | 'preview' | 'analyzing';

export default function ScanScreen() {
  const insets = useSafeAreaInsets();
  const { isAuthenticated, user, updateUser } = useAuthStore();
  const { saveImageFromBase64 } = useImageStore();
  
  // RevenueCat hook for IAP
  const { 
    isLoading: iapLoading, 
    monthlyPackage, 
    annualPackage, 
    purchaseMonthly, 
    purchaseAnnual,
    restorePurchases,
    refreshStatus: refreshIAPStatus,
    error: iapError,
  } = useRevenueCat();
  
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraReady, setCameraReady] = useState(false);
  const [photos, setPhotos] = useState<ScanPhoto[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [cropIndex, setCropIndex] = useState<number | null>(null);
  const [preparingPhotos, setPreparingPhotos] = useState(false);
  const submissionIdRef = useRef<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [scansRemaining, setScansRemaining] = useState(user?.scans_remaining || 3);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<'monthly' | 'annual'>('monthly');
  const [purchaseLoading, setPurchaseLoading] = useState(false);
  const [scanStep, setScanStep] = useState<ScanStep>('main');
  const [disclaimerChecked, setDisclaimerChecked] = useState(false);
  const cameraRef = useRef<CameraView>(null);
  
  // Hunting location state (per-scan override)
  const [showLocationPicker, setShowLocationPicker] = useState(false);
  const [huntingLocation, setHuntingLocation] = useState<string | null>(null);

  // Date taken state (per-scan)
  const [dateTaken, setDateTaken] = useState<Date | null>(null);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const currentYear = new Date().getFullYear();
  const [pickerYear, setPickerYear] = useState(currentYear);
  const [pickerMonth, setPickerMonth] = useState(new Date().getMonth() + 1);
  const [pickerDay, setPickerDay] = useState(new Date().getDate());

  const isPremium = user?.subscription_tier === 'master_stag';

  // Check if disclaimer needs to be shown on first visit
  useEffect(() => {
    if (isAuthenticated && user && !user.disclaimer_accepted && !disclaimerChecked) {
      setShowDisclaimer(true);
      setDisclaimerChecked(true);
    }
  }, [isAuthenticated, user, disclaimerChecked]);

  const handleAcceptDisclaimer = async () => {
    try {
      const response = await authAPI.acceptDisclaimer(true);
      updateUser({ 
        disclaimer_accepted: true,
        disclaimer_accepted_at: response.data.disclaimer_accepted_at
      });
      setShowDisclaimer(false);
    } catch (error) {
      console.error('Failed to accept disclaimer:', error);
      Alert.alert('Error', 'Failed to save disclaimer acceptance. Please try again.');
    }
  };

  const handleViewDisclaimer = () => {
    setShowDisclaimer(true);
  };

  const handleCloseDisclaimer = () => {
    // Only allow closing if already accepted
    if (user?.disclaimer_accepted) {
      setShowDisclaimer(false);
    }
  };

  const checkSubscription = async () => {
    if (!isAuthenticated) return;
    try {
      const response = await subscriptionAPI.getStatus();
      setScansRemaining(response.data.scans_remaining);
      updateUser({ 
        scans_remaining: response.data.scans_remaining,
        total_scans_used: response.data.total_scans_used 
      });
    } catch (error) {
      console.error('Failed to check subscription:', error);
    }
  };

  // Check if user can scan before starting
  const checkScanEligibility = async (): Promise<boolean> => {
    if (isPremium) return true;
    
    try {
      const response = await subscriptionAPI.checkEligibility();
      if (!response.data.allowed) {
        setShowUpgradeModal(true);
        return false;
      }
      setScansRemaining(response.data.scans_remaining);
      return true;
    } catch (error) {
      console.error('Failed to check eligibility:', error);
      // Allow scan attempt - backend will enforce the limit
      return true;
    }
  };

  const resetSubmission = () => {
    submissionIdRef.current = null;
  };

  const updatePhotos = (updater: (prev: ScanPhoto[]) => ScanPhoto[]) => {
    setPhotos(updater);
    resetSubmission(); // Any change to the photo set is a new submission
  };

  const addPhotos = async (incoming: { uri: string; width?: number; height?: number; exif?: Record<string, any> | null }[]) => {
    const room = MAX_SCAN_PHOTOS - photos.length;
    if (room <= 0) {
      Alert.alert('Photo Limit', `You can add up to ${MAX_SCAN_PHOTOS} photos per scan.`);
      return;
    }
    if (incoming.length > room) {
      Alert.alert('Photo Limit', `Only ${room} more photo${room === 1 ? '' : 's'} can be added (max ${MAX_SCAN_PHOTOS}).`);
    }
    setPreparingPhotos(true);
    try {
      const normalized: ScanPhoto[] = [];
      for (const item of incoming.slice(0, room)) {
        normalized.push(await normalizePhoto(item.uri, item.width, item.height, item.exif));
      }
      if (normalized.length) {
        updatePhotos((prev) => [...prev, ...normalized].slice(0, MAX_SCAN_PHOTOS));
        setSelectedIndex(photos.length + normalized.length - 1);
        setScanStep('preview');
      }
    } catch (error) {
      console.error('Failed to prepare photo:', error);
      Alert.alert('Error', 'That photo could not be loaded. Please try a different one.');
    } finally {
      setPreparingPhotos(false);
    }
  };

  const takePicture = async () => {
    if (!cameraRef.current || !cameraReady) return;

    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.9,
        exif: true,
      });
      if (photo?.uri) {
        await addPhotos([{ uri: photo.uri, width: photo.width, height: photo.height, exif: photo.exif }]);
      }
    } catch (error) {
      console.error('Failed to take picture:', error);
      Alert.alert('Error', 'Failed to capture image. Please try again.');
    }
  };

  const pickImage = async () => {
    const room = MAX_SCAN_PHOTOS - photos.length;
    if (room <= 0) return;
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: room > 1,
      selectionLimit: room,
      quality: 0.9,
      exif: true,
    });

    if (!result.canceled && result.assets.length) {
      await addPhotos(result.assets.map((a) => ({ uri: a.uri, width: a.width, height: a.height, exif: a.exif })));
    }
  };

  const promptAddPhoto = () => {
    if (Platform.OS === 'web') {
      pickImage();
      return;
    }
    Alert.alert('Add Photo', 'Use photos of the same deer from the same encounter.', [
      { text: 'Take Photo', onPress: openCamera },
      { text: 'Choose from Library', onPress: pickImage },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  const removePhoto = (index: number) => {
    updatePhotos((prev) => prev.filter((_, i) => i !== index));
    setSelectedIndex((cur) => Math.max(0, cur >= index ? cur - 1 : cur));
    if (photos.length <= 1) setScanStep('main');
  };

  const movePhoto = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= photos.length) return;
    updatePhotos((prev) => {
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
    setSelectedIndex(target);
  };

  const applyCrop = (crop: CropRect | null) => {
    if (cropIndex === null) return;
    updatePhotos((prev) => prev.map((p, i) => (i === cropIndex ? { ...p, crop } : p)));
    setCropIndex(null);
  };

  // Offline queue hook
  const { isOnline, pendingCount } = useOfflineQueue();

  const clearPhotos = () => {
    setPhotos([]);
    setSelectedIndex(0);
    resetSubmission();
  };

  const analyzeDeer = async () => {
    if (!photos.length || !isAuthenticated) return;

    // Check eligibility before starting analysis (only if online)
    if (isOnline) {
      const canScan = await checkScanEligibility();
      if (!canScan) {
        setScanStep('main');
        clearPhotos();
        return;
      }
    }

    setScanStep('analyzing');
    setAnalyzing(true);

    // One id per photo set: retries (network drop, offline queue) never double-charge.
    if (!submissionIdRef.current) submissionIdRef.current = newId();
    const submissionId = submissionIdRef.current;
    const stateToSend = huntingLocation || user?.state || undefined;
    let requestImages: ScanRequestImage[] = [];
    let primaryLocalId = '';

    const queueOffline = async (title: string, message: string) => {
      await offlineQueue.addToQueue({
        image_base64: requestImages[0].image_base64,
        images: requestImages,
        submission_id: submissionId,
        local_image_id: primaryLocalId,
        notes: undefined,
        state: stateToSend,
      });
      Alert.alert(title, message, [{ text: 'OK', style: 'default' }]);
      setHuntingLocation(null);
      setScanStep('main');
      clearPhotos();
    };

    try {
      // Save every photo to local storage first (order preserved)
      const localIds: string[] = [];
      for (const photo of photos) {
        localIds.push(await saveImageFromBase64(photo.uri));
      }
      primaryLocalId = localIds[0];
      requestImages = toRequestImages(photos, localIds);

      if (!isOnline) {
        await queueOffline(
          '📶 Scan Saved Offline',
          'Your scan has been saved and will be automatically uploaded when you\'re back online.\n\nYou can view your pending scans in the History tab.',
        );
        return;
      }

      const response = await scanAPI.analyzeDeer({
        images: requestImages,
        submission_id: submissionId,
        local_image_id: primaryLocalId,
        state: stateToSend,
        date_taken: dateTaken ? format(dateTaken, 'yyyy-MM-dd') : undefined,
      });

      // Server is the source of truth for credits (retries are never double-charged)
      checkSubscription();

      setHuntingLocation(null);
      setDateTaken(null);
      clearPhotos();
      router.push(`/scan-result/${response.data.id}`);
    } catch (error: any) {
      console.error('Analyze deer error:', error?.response?.data || error);

      if (requestImages.length && !error.response && (error.code === 'ECONNABORTED' || error.message?.includes('Network') || !isOnline)) {
        await queueOffline(
          '📶 Connection Lost',
          'Your scan has been saved and will be uploaded automatically when you\'re back online.',
        );
        return;
      }

      const status = error.response?.status;
      const detail = error.response?.data?.detail;

      if (status === 403 && detail?.code === 'FREE_LIMIT_REACHED') {
        setShowUpgradeModal(true);
        setScanStep('main');
        clearPhotos();
        return;
      }

      if (status === 400 && detail?.code === 'NOT_A_DEER') {
        const detected = detail?.detected_subject || 'something other than a deer';
        Alert.alert(
          '🦌 Not a Deer',
          `We detected "${detected}" in your image.\n\nThis app is designed specifically for analyzing Whitetail and Mule Deer. Please try again with a deer image.\n\nNo scan was used.`,
          [{ text: 'OK', style: 'default' }]
        );
        setScanStep('main');
        clearPhotos();
        return;
      }

      // Correctable problems: keep the photos so the user can fix them
      if (status === 422 && detail?.code === 'MIXED_DEER') {
        const ids: string[] = detail.conflicting_image_ids || [];
        if (ids.length) setSelectedIndex(Math.max(0, Number(ids[0].split('_')[1]) - 1));
        Alert.alert('Different Deer?', detail.message, [{ text: 'Review Photos', style: 'default' }]);
        setScanStep('preview');
        return;
      }
      if (status === 400 && detail?.code) {
        Alert.alert('Check Your Photos', `${detail.message}\n\nNo scan was used.`);
        setScanStep('preview');
        return;
      }

      const message = detail?.message || detail || 'Analysis failed. Please try again.';
      Alert.alert('Error', typeof message === 'string' ? message : 'Analysis failed. Please try again.');
      setScanStep('preview');
    } finally {
      setAnalyzing(false);
    }
  };

  const resetCapture = () => {
    clearPhotos();
    setScanStep('main');
  };

  const openCamera = async () => {
    // Camera doesn't work well on web - use image picker instead
    if (Platform.OS === 'web') {
      Alert.alert(
        'Camera Not Available',
        'Camera is only available on mobile devices. Would you like to choose an image from your library instead?',
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Choose Image', onPress: pickImage }
        ]
      );
      return;
    }
    
    console.log('openCamera called, permission:', permission);
    
    if (!permission?.granted) {
      console.log('Requesting camera permission...');
      const result = await requestPermission();
      console.log('Permission result:', result);
      if (!result.granted) {
        if (!result.canAskAgain) {
          Alert.alert('Camera Access Off', 'Turn on camera access in Settings to photograph deer, or choose photos from your library.', [
            { text: 'Choose from Library', onPress: pickImage },
            { text: 'Open Settings', onPress: () => Linking.openSettings() },
            { text: 'Cancel', style: 'cancel' },
          ]);
        } else {
          Alert.alert('Permission Required', 'Camera access is needed to scan deer. You can also choose photos from your library.');
        }
        return;
      }
    }
    
    console.log('Setting scanStep to camera');
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
        {!isPremium && (
          <View style={[styles.scanLimit, { top: insets.top + spacing.md }]}>
            <Zap size={16} color={scansRemaining > 0 ? colors.primary : colors.error} />
            <Text style={[styles.scanLimitText, scansRemaining === 0 && styles.noScansText]}>
              {scansRemaining} free scan{scansRemaining !== 1 ? 's' : ''} remaining
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
          <TouchableOpacity style={styles.controlButton} onPress={() => setScanStep(photos.length ? 'preview' : 'main')}>
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
  if (scanStep === 'preview' && photos.length > 0) {
    const current = photos[Math.min(selectedIndex, photos.length - 1)];
    return (
      <View style={styles.container}>
        <View style={styles.previewContainer}>
          <Image source={{ uri: current.uri }} style={styles.preview} resizeMode="contain" testID="photo-preview-main" />
          {current.crop && (
            <View style={[styles.croppedPill, { top: insets.top + spacing.md }]}>
              <Crop size={12} color={colors.textOnPrimary} />
              <Text style={styles.croppedPillText}>Cropped for analysis</Text>
            </View>
          )}
          <TouchableOpacity
            style={[styles.closeButton, { top: insets.top + spacing.md }]}
            onPress={resetCapture}
            testID="preview-close"
          >
            <X size={24} color={colors.textPrimary} />
          </TouchableOpacity>
          {preparingPhotos && (
            <View style={styles.preparingOverlay}>
              <ActivityIndicator color={colors.primary} />
            </View>
          )}
        </View>

        <View style={[styles.previewControls, { paddingBottom: insets.bottom + spacing.lg }]}>
          <PhotoTray
            photos={photos}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
            onRemove={removePhoto}
            onMove={movePhoto}
            onAdd={promptAddPhoto}
          />
          <View style={styles.photoGuideRow}>
            <Text style={styles.photoGuideText} testID="photo-guidance">
              Use photos of the same deer from the same encounter. Include a clear side view with the full body visible.
            </Text>
            <TouchableOpacity
              style={styles.cropButton}
              onPress={() => setCropIndex(Math.min(selectedIndex, photos.length - 1))}
              testID="photo-crop-button"
            >
              <Crop size={16} color={colors.primary} />
              <Text style={styles.cropButtonText}>{current.crop ? 'Edit crop' : 'Crop'}</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.previewButtonRow}>
            <Button
              title="Start Over"
              onPress={resetCapture}
              variant="outline"
              style={styles.previewButton}
            />
            <Button
              title={photos.length > 1 ? `Analyze ${photos.length} Photos` : 'Analyze Deer'}
              onPress={analyzeDeer}
              style={styles.previewButton}
              disabled={(!isPremium && scansRemaining === 0) || preparingPhotos}
            />
          </View>
          <View style={styles.locationInlineRow}>
            <View style={styles.locationInlineLeft}>
              <View style={styles.locationInlineIconWrap}>
                <MapPin size={16} color={colors.primary} />
              </View>
              <View style={styles.locationInlineCopy}>
                <Text style={styles.locationInlineLabel}>Hunting Location</Text>
                <Text style={styles.locationInlineText}>
                  {huntingLocation
                    ? `${getStateName(huntingLocation)} (${huntingLocation})`
                    : user?.state
                      ? `${getStateName(user.state)} (${user.state})`
                      : 'Select State'}
                </Text>
              </View>
            </View>
            <TouchableOpacity
              style={styles.locationInlineChange}
              onPress={() => setShowLocationPicker(true)}
            >
              <Text style={styles.locationInlineChangeText}>Change</Text>
            </TouchableOpacity>
          </View>

          {/* Date Taken Row */}
          <View style={styles.locationInlineRow}>
            <View style={styles.locationInlineLeft}>
              <View style={styles.locationInlineIconWrap}>
                <Calendar size={16} color={colors.primary} />
              </View>
              <View style={styles.locationInlineCopy}>
                <Text style={styles.locationInlineLabel}>Date Taken</Text>
                <Text style={styles.locationInlineText}>
                  {dateTaken
                    ? format(dateTaken, 'MMM d, yyyy')
                    : 'Not set (optional)'}
                </Text>
              </View>
            </View>
            <View style={styles.dateActionRow}>
              {dateTaken && (
                <TouchableOpacity
                  style={styles.dateClearButton}
                  onPress={() => setDateTaken(null)}
                >
                  <Text style={styles.dateClearText}>Clear</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity
                style={styles.locationInlineChange}
                onPress={() => {
                  if (dateTaken) {
                    setPickerYear(dateTaken.getFullYear());
                    setPickerMonth(dateTaken.getMonth() + 1);
                    setPickerDay(dateTaken.getDate());
                  } else {
                    const now = new Date();
                    setPickerYear(now.getFullYear());
                    setPickerMonth(now.getMonth() + 1);
                    setPickerDay(now.getDate());
                  }
                  setShowDatePicker(true);
                }}
              >
                <Text style={styles.locationInlineChangeText}>
                  {dateTaken ? 'Change' : 'Set Date'}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        <CropModal
          photo={cropIndex !== null ? photos[cropIndex] ?? null : null}
          onCancel={() => setCropIndex(null)}
          onApply={applyCrop}
        />

        {/* State Picker Modal */}
        <StatePicker
          visible={showLocationPicker}
          selectedState={huntingLocation}
          onSelect={(state) => {
            setHuntingLocation(state);
            setShowLocationPicker(false);
          }}
          onClose={() => setShowLocationPicker(false)}
          title="Select Hunting Location"
          allowClear={true}
        />

        {/* Date Picker Modal */}
        {showDatePicker && (
          <Modal
            transparent
            animationType="fade"
            visible={showDatePicker}
            onRequestClose={() => setShowDatePicker(false)}
          >
            <TouchableOpacity
              style={styles.datePickerOverlay}
              activeOpacity={1}
              onPress={() => setShowDatePicker(false)}
            >
              <View
                style={styles.datePickerContainer}
                onStartShouldSetResponder={() => true}
              >
                <View style={styles.datePickerHeader}>
                  <Text style={styles.datePickerTitle}>When was this photo taken?</Text>
                  <TouchableOpacity onPress={() => setShowDatePicker(false)}>
                    <X size={20} color={colors.textPrimary} />
                  </TouchableOpacity>
                </View>

                {/* Wheel Pickers: Year / Month / Day */}
                <View style={styles.dateWheelRow}>
                  {/* Year */}
                  <View style={styles.dateWheelCol}>
                    <Text style={styles.dateWheelLabel}>Year</Text>
                    <View style={styles.dateWheelPickerWrap}>
                      <Picker
                        selectedValue={pickerYear}
                        onValueChange={(val) => setPickerYear(val)}
                        style={styles.dateWheelPicker}
                        itemStyle={styles.dateWheelItemStyle}
                      >
                        {Array.from({ length: 30 }, (_, i) => currentYear - i).map((yr) => (
                          <Picker.Item key={yr} label={String(yr)} value={yr} />
                        ))}
                      </Picker>
                    </View>
                  </View>

                  {/* Month */}
                  <View style={styles.dateWheelCol}>
                    <Text style={styles.dateWheelLabel}>Month</Text>
                    <View style={styles.dateWheelPickerWrap}>
                      <Picker
                        selectedValue={pickerMonth}
                        onValueChange={(val) => setPickerMonth(val)}
                        style={styles.dateWheelPicker}
                        itemStyle={styles.dateWheelItemStyle}
                      >
                        {[
                          { label: 'Jan', value: 1 }, { label: 'Feb', value: 2 },
                          { label: 'Mar', value: 3 }, { label: 'Apr', value: 4 },
                          { label: 'May', value: 5 }, { label: 'Jun', value: 6 },
                          { label: 'Jul', value: 7 }, { label: 'Aug', value: 8 },
                          { label: 'Sep', value: 9 }, { label: 'Oct', value: 10 },
                          { label: 'Nov', value: 11 }, { label: 'Dec', value: 12 },
                        ].map((m) => (
                          <Picker.Item key={m.value} label={m.label} value={m.value} />
                        ))}
                      </Picker>
                    </View>
                  </View>

                  {/* Day */}
                  <View style={styles.dateWheelCol}>
                    <Text style={styles.dateWheelLabel}>Day</Text>
                    <View style={styles.dateWheelPickerWrap}>
                      <Picker
                        selectedValue={pickerDay}
                        onValueChange={(val) => setPickerDay(val)}
                        style={styles.dateWheelPicker}
                        itemStyle={styles.dateWheelItemStyle}
                      >
                        {Array.from(
                          { length: new Date(pickerYear, pickerMonth, 0).getDate() },
                          (_, i) => i + 1,
                        ).map((d) => (
                          <Picker.Item key={d} label={String(d)} value={d} />
                        ))}
                      </Picker>
                    </View>
                  </View>
                </View>

                <Text style={styles.datePickerHint}>
                  Helps determine seasonal context for more accurate aging
                </Text>

                {/* Confirm button */}
                <TouchableOpacity
                  style={styles.dateConfirmButton}
                  onPress={() => {
                    const d = new Date(pickerYear, pickerMonth - 1, pickerDay);
                    if (d <= new Date()) {
                      setDateTaken(d);
                      setShowDatePicker(false);
                    } else {
                      Alert.alert('Invalid Date', 'Date cannot be in the future.');
                    }
                  }}
                >
                  <Text style={styles.dateConfirmText}>Set Date</Text>
                </TouchableOpacity>
              </View>
            </TouchableOpacity>
          </Modal>
        )}
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
        <View style={styles.headerText}>
          <Text style={styles.headerTitle}>Iron Stag</Text>
          <Text style={styles.headerSubtitle}>Precision for Ethical Hunters</Text>
        </View>
        <TouchableOpacity style={styles.infoButton} onPress={handleViewDisclaimer}>
          <FileText size={20} color={colors.textMuted} />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={[styles.mainContent, { paddingBottom: insets.bottom + spacing.xl }]}>
        {/* Offline Banner */}
        <OfflineBanner />
        
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
        <View style={styles.scanTipCard}>
          <View style={styles.scanTipHeader}>
            <Info size={16} color={colors.primary} />
            <Text style={styles.scanTipTitle}>For Best Estimate</Text>
          </View>
          <Text style={styles.scanTipText}>
            Use a full-body side view when possible. Keep the deer centered and in focus, with the head, chest, belly, and legs visible. Avoid long-distance shots, heavy shadows, and photos with multiple deer.
          </Text>
          <Text style={[styles.scanTipText, { marginTop: spacing.xs }]}>
            You can add up to {MAX_SCAN_PHOTOS} photos of the same deer. One scan credit covers all of them.
          </Text>
        </View>

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
            disabled={!isPremium && scansRemaining === 0}
            icon={<Camera size={20} color={colors.background} />}
          />
          <Button
            title="Choose from Library"
            onPress={pickImage}
            size="large"
            variant="secondary"
            style={styles.secondaryActionButton}
            disabled={!isPremium && scansRemaining === 0}
            icon={<ImagePlus size={20} color={colors.textPrimary} />}
          />
        </View>
      </ScrollView>

      {/* Disclaimer Modal */}
      <Modal visible={showDisclaimer} animationType="slide">
        <DisclaimerScreen 
          onClose={handleCloseDisclaimer} 
          onAccept={handleAcceptDisclaimer}
          isAccepted={user?.disclaimer_accepted || false}
          acceptedAt={user?.disclaimer_accepted_at}
        />
      </Modal>

      {/* Upgrade Modal - Free Scans Used */}
      <Modal
        visible={showUpgradeModal}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setShowUpgradeModal(false)}
      >
        <View style={upgradeModalStyles.overlay}>
          <View style={upgradeModalStyles.content}>
            {/* Icon */}
            <View style={upgradeModalStyles.iconContainer}>
              <Crown size={40} color={colors.primary} />
            </View>
            
            {/* Title */}
            <Text style={upgradeModalStyles.title}>Free Scans Used</Text>
            
            {/* Message */}
            <Text style={upgradeModalStyles.message}>
              You&apos;ve used all 3 of your free scans. Upgrade to Master Stag for unlimited AI-powered deer analysis.
            </Text>
            
            {/* Plan Options */}
            <View style={upgradeModalStyles.planOptions}>
              {/* Monthly */}
              <TouchableOpacity 
                style={[
                  upgradeModalStyles.planOption,
                  selectedPlan === 'monthly' && upgradeModalStyles.planOptionSelected
                ]}
                onPress={() => setSelectedPlan('monthly')}
              >
                <View style={[
                  upgradeModalStyles.planRadio,
                  selectedPlan === 'monthly' && upgradeModalStyles.planRadioSelected
                ]}>
                  {selectedPlan === 'monthly' && <View style={upgradeModalStyles.planRadioInner} />}
                </View>
                <View style={upgradeModalStyles.planInfo}>
                  <Text style={upgradeModalStyles.planName}>Monthly</Text>
                  <Text style={upgradeModalStyles.planPrice}>
                    {monthlyPackage?.product?.priceString || '$9.99/mo'}
                  </Text>
                </View>
              </TouchableOpacity>

              {/* Annual */}
              <TouchableOpacity 
                style={[
                  upgradeModalStyles.planOption,
                  selectedPlan === 'annual' && upgradeModalStyles.planOptionSelected
                ]}
                onPress={() => setSelectedPlan('annual')}
              >
                <View style={upgradeModalStyles.saveBadge}>
                  <Text style={upgradeModalStyles.saveBadgeText}>SAVE $30</Text>
                </View>
                <View style={[
                  upgradeModalStyles.planRadio,
                  selectedPlan === 'annual' && upgradeModalStyles.planRadioSelected
                ]}>
                  {selectedPlan === 'annual' && <View style={upgradeModalStyles.planRadioInner} />}
                </View>
                <View style={upgradeModalStyles.planInfo}>
                  <Text style={upgradeModalStyles.planName}>Annual</Text>
                  <Text style={upgradeModalStyles.planPrice}>
                    {annualPackage?.product?.priceString || '$89.99/yr'}
                  </Text>
                </View>
              </TouchableOpacity>
            </View>
            
            {/* If offerings failed to load, surface an explicit error + retry for App Review */}
            {iapError ? (
              <View style={upgradeModalStyles.iapErrorBox}>
                <Text style={upgradeModalStyles.iapErrorTitle}>Purchase Options Unavailable</Text>
                <Text style={upgradeModalStyles.iapErrorText}>{iapError}</Text>
                <TouchableOpacity
                  style={upgradeModalStyles.iapRetryButton}
                  disabled={iapLoading || purchaseLoading}
                  onPress={async () => {
                    try {
                      await refreshIAPStatus();
                    } catch (e) {
                      // ignore
                    }
                  }}
                >
                  <Text style={upgradeModalStyles.iapRetryButtonText}>
                    {iapLoading ? 'Loading…' : 'Try Again'}
                  </Text>
                </TouchableOpacity>
              </View>
            ) : null}

            {/* Buttons */}
            <TouchableOpacity 
              style={upgradeModalStyles.upgradeButton}
              disabled={purchaseLoading || iapLoading || (!!iapError && (!monthlyPackage && !annualPackage))}
              onPress={async () => {
                setPurchaseLoading(true);
                try {
                  // If packages are missing, attempt a quick refresh (common during first launch)
                  if (!monthlyPackage && !annualPackage) {
                    await refreshIAPStatus();
                  }

                  let result;
                  if (selectedPlan === 'monthly') {
                    result = await purchaseMonthly();
                  } else {
                    result = await purchaseAnnual();
                  }
                  
                  if (result.success) {
                    // Refresh user data to get updated subscription
                    const userResponse = await authAPI.getMe();
                    updateUser(userResponse.data);
                    
                    Alert.alert(
                      '🎉 Welcome to Master Stag!',
                      'Your subscription is now active. Enjoy unlimited deer scans!',
                      [{ text: 'OK', style: 'default' }]
                    );
                    setShowUpgradeModal(false);
                  } else if (result.message !== 'Purchase was canceled') {
                    Alert.alert('Purchase Failed', result.message);
                  }
                } catch (error: any) {
                  Alert.alert('Error', error.message || 'Failed to complete purchase.');
                } finally {
                  setPurchaseLoading(false);
                }
              }}
            >
              {(purchaseLoading || iapLoading) ? (
                <ActivityIndicator size="small" color={colors.textOnPrimary} />
              ) : (
                <Text style={upgradeModalStyles.upgradeButtonText}>
                  Subscribe Now
                </Text>
              )}
            </TouchableOpacity>
            
            {/* Restore Purchases Button */}
            <TouchableOpacity 
              style={upgradeModalStyles.restoreButton}
              disabled={purchaseLoading || iapLoading}
              onPress={async () => {
                setPurchaseLoading(true);
                try {
                  const result = await restorePurchases();
                  
                  if (result.success) {
                    // Refresh user data
                    const userResponse = await authAPI.getMe();
                    updateUser(userResponse.data);
                    
                    Alert.alert(
                      'Purchases Restored!',
                      'Your subscription has been restored.',
                      [{ text: 'OK', style: 'default' }]
                    );
                    setShowUpgradeModal(false);
                  } else {
                    Alert.alert('Restore Failed', result.message);
                  }
                } catch (error: any) {
                  Alert.alert('Error', error.message || 'Failed to restore purchases.');
                } finally {
                  setPurchaseLoading(false);
                }
              }}
            >
              <RotateCcw size={14} color={colors.primary} />
              <Text style={upgradeModalStyles.restoreButtonText}>Restore Purchases</Text>
            </TouchableOpacity>
            
            <TouchableOpacity 
              style={upgradeModalStyles.laterButton}
              onPress={() => setShowUpgradeModal(false)}
            >
              <Text style={upgradeModalStyles.laterButtonText}>Maybe Later</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

// Disclaimer Screen Component
interface DisclaimerScreenProps {
  onClose: () => void;
  onAccept: () => void;
  isAccepted: boolean;
  acceptedAt?: string;
}

function DisclaimerScreen({ onClose, onAccept, isAccepted, acceptedAt }: DisclaimerScreenProps) {
  const insets = useSafeAreaInsets();

  // Format the acceptance date
  const formatAcceptedDate = (dateString?: string) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

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
        {isAccepted ? (
          <TouchableOpacity style={disclaimerStyles.backButton} onPress={onClose}>
            <ArrowLeft size={24} color={colors.textPrimary} />
          </TouchableOpacity>
        ) : (
          <View style={disclaimerStyles.placeholder} />
        )}
        <Text style={disclaimerStyles.headerTitle}>Scanning Disclaimer</Text>
        <View style={disclaimerStyles.placeholder} />
      </View>

      <ScrollView 
        contentContainerStyle={disclaimerStyles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Acceptance Badge - Only show if already accepted */}
        {isAccepted && acceptedAt && (
          <View style={disclaimerStyles.acceptedBadge}>
            <Check size={16} color={colors.harvest} />
            <Text style={disclaimerStyles.acceptedText}>
              Acknowledged on {formatAcceptedDate(acceptedAt)}
            </Text>
          </View>
        )}

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
        {isAccepted ? (
          <Button
            title="Close"
            onPress={onClose}
            size="large"
            variant="outline"
            style={disclaimerStyles.continueButton}
          />
        ) : (
          <Button
            title="I Understand"
            onPress={onAccept}
            size="large"
            style={disclaimerStyles.continueButton}
          />
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerText: {
    flex: 1,
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
  scanTipCard: {
    width: '100%',
    backgroundColor: 'rgba(200, 162, 74, 0.10)',
    borderWidth: 1,
    borderColor: 'rgba(200, 162, 74, 0.28)',
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.xl,
  },
  scanTipHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.xs,
  },
  scanTipTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textPrimary,
  },
  scanTipText: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
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
    gap: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.backgroundCard,
  },
  croppedPill: {
    position: 'absolute',
    left: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primary,
  },
  croppedPillText: { color: colors.textOnPrimary, fontSize: 12, fontWeight: '600' },
  preparingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.4)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  photoGuideRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  photoGuideText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 17 },
  cropButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    minHeight: 44,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  cropButtonText: { color: colors.primary, fontWeight: '600', fontSize: 13 },
  previewButtonRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  previewButton: {
    flex: 1,
  },
  locationInlineRow: {
    width: '100%',
    backgroundColor: 'transparent',
    borderRadius: borderRadius.md,
    borderWidth: 2,
    borderColor: colors.primary,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  locationInlineLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flex: 1,
  },
  locationInlineIconWrap: {
    width: 32,
    height: 32,
    borderRadius: borderRadius.full,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(184, 149, 74, 0.12)',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  locationInlineCopy: {
    flex: 1,
  },
  locationInlineLabel: {
    fontSize: 11,
    color: colors.primary,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 2,
  },
  locationInlineText: {
    fontSize: 16,
    color: colors.primary,
    fontWeight: '700',
  },
  locationInlineChange: {
    minWidth: 96,
    paddingVertical: 10,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  locationInlineChangeText: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.textOnPrimary,
  },
  dateActionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dateClearButton: {
    paddingVertical: 10,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dateClearText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textMuted,
  },
  // ── Date Picker Modal ──
  datePickerOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
    padding: 0,
  },
  datePickerContainer: {
    backgroundColor: colors.background,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    paddingTop: spacing.lg,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
  },
  datePickerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  datePickerTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  dateWheelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  dateWheelCol: {
    flex: 1,
    alignItems: 'center',
  },
  dateWheelLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.primary,
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 4,
  },
  dateWheelPickerWrap: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
    width: '100%',
    height: 150,
  },
  dateWheelPicker: {
    width: '100%',
    height: 150,
    color: colors.textPrimary,
    backgroundColor: 'transparent',
  },
  dateWheelItemStyle: {
    fontSize: 18,
    color: colors.textPrimary,
    height: 150,
  },
  datePickerHint: {
    fontSize: 12,
    color: colors.textMuted,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  dateConfirmButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dateConfirmText: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textOnPrimary,
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
    backgroundColor: colors.background,
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
  acceptedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.harvestBg,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    marginBottom: spacing.lg,
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.harvestBorder,
  },
  acceptedText: {
    fontSize: 13,
    color: colors.harvest,
    fontWeight: '500',
  },
  warningHeader: {
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  warningIcon: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.errorBg,
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
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.error,
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

// Upgrade Modal Styles
const upgradeModalStyles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  content: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    alignItems: 'center',
    width: '100%',
    maxWidth: 340,
    borderWidth: 1,
    borderColor: colors.border,
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(200, 162, 74, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.md,
    borderWidth: 2,
    borderColor: colors.primary,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  message: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: spacing.lg,
  },
  benefits: {
    width: '100%',
    marginBottom: spacing.lg,
  },
  benefitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.xs,
  },
  benefitText: {
    fontSize: 14,
    color: colors.textPrimary,
    marginLeft: spacing.sm,
  },
  upgradeButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
    minHeight: 48,
  },
  upgradeButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
  restoreButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  restoreButtonText: {
    fontSize: 13,
    color: colors.primary,
    fontWeight: '500',
  },
  laterButton: {
    paddingVertical: spacing.sm,
  },
  laterButtonText: {
    fontSize: 14,
    color: colors.textMuted,
  },
  planOptions: {
    width: '100%',
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  planOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
    position: 'relative',
  },
  planOptionSelected: {
    borderColor: colors.primary,
    backgroundColor: 'rgba(200, 162, 74, 0.1)',
  },
  planRadio: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: colors.border,
    marginRight: spacing.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  planRadioSelected: {
    borderColor: colors.primary,
  },
  planRadioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.primary,
  },
  planInfo: {
    flex: 1,
  },
  planName: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 2,
  },
  planPrice: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  saveBadge: {
    position: 'absolute',
    top: -8,
    right: spacing.sm,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  saveBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.background,
  },
  iapErrorBox: {
    width: '100%',
    padding: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(239, 68, 68, 0.25)',
    marginBottom: spacing.md,
  },
  iapErrorTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: 4,
  },
  iapErrorText: {
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 18,
    marginBottom: spacing.sm,
  },
  iapRetryButton: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(200, 162, 74, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(200, 162, 74, 0.35)',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: borderRadius.sm,
  },
  iapRetryButtonText: {
    color: colors.primary,
    fontWeight: '600',
    fontSize: 12,
  },
});
