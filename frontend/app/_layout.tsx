import React, { useEffect, useState, Component, ErrorInfo, ReactNode } from 'react';
import { Platform, BackHandler, Alert, View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Stack, usePathname, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from '../stores/authStore';
import { useImageStore } from '../stores/imageStore';
import { appUpdateService, VersionCheckResponse } from '../services/AppUpdateService';
import { offlineQueue } from '../services/OfflineQueueService';
import { crashReporting } from '../services/CrashReportingService';
import { UpdateModal } from '../components/UpdateModal';
import { colors, spacing } from '../constants/theme';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000,
    },
  },
});

// Error Boundary Component to catch React errors
interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Report to crash reporting service
    crashReporting.captureError(error, {
      type: 'react_error_boundary',
      componentStack: errorInfo.componentStack,
    });
    console.error('React Error Boundary caught error:', error, errorInfo);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <View style={errorStyles.container}>
          <Text style={errorStyles.title}>Something went wrong</Text>
          <Text style={errorStyles.message}>
            {this.state.error?.message || 'An unexpected error occurred'}
          </Text>
          <TouchableOpacity style={errorStyles.button} onPress={this.handleRetry}>
            <Text style={errorStyles.buttonText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return this.props.children;
  }
}

const errorStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },
  message: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  button: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: 8,
  },
  buttonText: {
    color: colors.background,
    fontSize: 16,
    fontWeight: '600',
  },
});

export default function RootLayout() {
  const loadToken = useAuthStore((state) => state.loadToken);
  const initializeImages = useImageStore((state) => state.initialize);
  const pathname = usePathname();
  const router = useRouter();
  
  // Update modal state
  const [updateModalVisible, setUpdateModalVisible] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<VersionCheckResponse | null>(null);

  // Handle Android back button globally to prevent app from closing unexpectedly
  useEffect(() => {
    if (Platform.OS !== 'android') return;

    const onBackPress = () => {
      // Define routes where back should navigate to tabs instead of closing app
      const rootRoutes = ['/', '/index', '/splash', '/(tabs)', '/(tabs)/scan', '/(tabs)/history', '/(tabs)/learn', '/(tabs)/profile'];
      const authRoutes = ['/(auth)/login', '/(auth)/signup'];
      
      // If on scan-result page, navigate to scan tab
      if (pathname.startsWith('/scan-result')) {
        router.replace('/(tabs)/scan');
        return true; // Prevent default
      }
      
      // If on a root tab or splash, ask before exiting
      if (rootRoutes.some(route => pathname === route || pathname.startsWith('/(tabs)'))) {
        // On main tabs - show exit confirmation
        Alert.alert(
          'Exit App',
          'Are you sure you want to exit?',
          [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Exit', style: 'destructive', onPress: () => BackHandler.exitApp() }
          ]
        );
        return true; // Prevent default
      }
      
      // If on auth screens (login/signup), go back to splash
      if (authRoutes.some(route => pathname === route || pathname.startsWith('/(auth)'))) {
        router.replace('/splash');
        return true;
      }
      
      // For other screens, let the default back behavior happen
      // but if it would close the app, prevent it
      return false;
    };

    const subscription = BackHandler.addEventListener('hardwareBackPress', onBackPress);
    return () => subscription.remove();
  }, [pathname, router]);

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
        
        // Initialize crash reporting service
        await crashReporting.initialize();
        
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
        crashReporting.captureError(error as Error, { type: 'app_initialization' });
      }
    };
    
    initApp();
  }, []);

  // Track screen changes for crash reporting
  useEffect(() => {
    crashReporting.setCurrentScreen(pathname);
  }, [pathname]);

  return (
    <ErrorBoundary>
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
