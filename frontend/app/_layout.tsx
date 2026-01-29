import React, { useEffect, useState } from 'react';
import { Platform } from 'react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from '../stores/authStore';
import { useImageStore } from '../stores/imageStore';
import { appUpdateService, VersionCheckResponse } from '../services/AppUpdateService';
import { offlineQueue } from '../services/OfflineQueueService';
import { UpdateModal } from '../components/UpdateModal';
import { colors } from '../constants/theme';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000,
    },
  },
});

export default function RootLayout() {
  const loadToken = useAuthStore((state) => state.loadToken);
  const initializeImages = useImageStore((state) => state.initialize);
  
  // Update modal state
  const [updateModalVisible, setUpdateModalVisible] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<VersionCheckResponse | null>(null);

  // Check for updates
  const checkForUpdates = async (force: boolean = false) => {
    try {
      const result = await appUpdateService.checkForUpdates(force);
      
      if (result && result.update_available) {
        // For soft updates, check if user has dismissed this version
        if (result.update_mode === 'soft') {
          const dismissed = await appUpdateService.hasUserDismissedVersion(result.latest_version);
          if (dismissed && !force) {
            console.log('[RootLayout] User has dismissed this version');
            return;
          }
        }
        
        setUpdateInfo(result);
        setUpdateModalVisible(true);
      }
    } catch (error) {
      console.error('[RootLayout] Update check failed:', error);
    }
  };

  // Handle update button press
  const handleUpdate = async () => {
    if (updateInfo?.store_url) {
      await appUpdateService.openStore(updateInfo.store_url);
    }
  };

  // Handle dismiss button press
  const handleDismiss = async () => {
    if (updateInfo) {
      await appUpdateService.dismissVersion(updateInfo.latest_version);
    }
    setUpdateModalVisible(false);
  };

  useEffect(() => {
    const initApp = async () => {
      try {
        await loadToken();
        await initializeImages();
        
        // Initialize offline queue service
        await offlineQueue.initialize();
        
        // Initialize RevenueCat for iOS and Android (only in native builds, not Expo Go)
        if (Platform.OS === 'ios' || Platform.OS === 'android') {
          try {
            const { revenueCatService } = await import('../services/RevenueCatService');
            await revenueCatService.initialize();
          } catch (rcError) {
            console.log('RevenueCat init skipped (Expo Go or error):', rcError);
          }
        }
        
        // Check for app updates after initialization
        await checkForUpdates();
      } catch (error) {
        console.error('App initialization error:', error);
      }
    };
    
    initApp();
  }, []);

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: colors.background },
            animation: 'fade',
          }}
        >
          <Stack.Screen name="index" />
          <Stack.Screen name="splash" />
          <Stack.Screen name="(auth)" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen 
            name="scan-result/[id]" 
            options={{ 
              headerShown: false,
              animation: 'slide_from_right',
            }} 
          />
        </Stack>
        
        {/* App Update Modal */}
        {updateInfo && (
          <UpdateModal
            visible={updateModalVisible}
            updateMode={updateInfo.update_mode as 'soft' | 'force'}
            latestVersion={updateInfo.latest_version}
            currentVersion={appUpdateService.getCurrentVersion()}
            releaseNotes={updateInfo.release_notes}
            message={updateInfo.message}
            storeName={appUpdateService.getStoreName()}
            onUpdate={handleUpdate}
            onDismiss={handleDismiss}
          />
        )}
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
