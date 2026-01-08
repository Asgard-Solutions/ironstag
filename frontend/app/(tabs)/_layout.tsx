import React, { useEffect, useState } from 'react';
import { Tabs, router } from 'expo-router';
import { Platform, StyleSheet, View } from 'react-native';
import { Home, Camera, History, BookOpen, User } from 'lucide-react-native';
import { colors, spacing } from '../../constants/theme';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuthStore } from '../../stores/authStore';

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  const { token, isLoading } = useAuthStore();
  const [hasRedirected, setHasRedirected] = useState(false);
  
  // Calculate tab bar height based on platform and safe area
  const tabBarHeight = Platform.OS === 'ios' ? 85 : 60 + insets.bottom;
  const tabBarPaddingBottom = Platform.OS === 'ios' ? insets.bottom : insets.bottom + spacing.xs;

  // Redirect to splash screen when logged out
  useEffect(() => {
    if (!isLoading && !token && !hasRedirected) {
      setHasRedirected(true);
      // Small delay to ensure state is fully propagated
      setTimeout(() => {
        router.replace('/');
      }, 100);
    }
  }, [isLoading, token, hasRedirected]);

  // Reset redirect flag when token changes (user logs back in)
  useEffect(() => {
    if (token) {
      setHasRedirected(false);
    }
  }, [token]);

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.backgroundCard,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: tabBarHeight,
          paddingTop: spacing.sm,
          paddingBottom: tabBarPaddingBottom,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: '500',
          marginTop: 4,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => <Home size={size} color={color} />,
          tabBarStyle: { display: 'none' },
        }}
      />
      <Tabs.Screen
        name="scan"
        options={{
          title: 'Scan',
          tabBarIcon: ({ color, size }) => (
            <View style={styles.scanIconContainer}>
              <Camera size={size + 4} color={colors.background} />
            </View>
          ),
          tabBarLabelStyle: { display: 'none' },
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color, size }) => <History size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="learn"
        options={{
          title: 'Learn',
          tabBarIcon: ({ color, size }) => <BookOpen size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, size }) => <User size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  scanIconContainer: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: -20,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
});
