import React, { useEffect } from 'react';
import { Platform } from 'react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useAuthStore } from '../stores/authStore';
import { useImageStore } from '../stores/imageStore';
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

  useEffect(() => {
    const initApp = async () => {
      try {
        await loadToken();
        await initializeImages();
        
        // Initialize RevenueCat for iOS and Android (only in native builds, not Expo Go)
        if (Platform.OS === 'ios' || Platform.OS === 'android') {
          try {
            const { revenueCatService } = await import('../services/RevenueCatService');
            await revenueCatService.initialize();
          } catch (rcError) {
            console.log('RevenueCat init skipped (Expo Go or error):', rcError);
          }
        }
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
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
