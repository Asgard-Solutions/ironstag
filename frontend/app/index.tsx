import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Image, Animated } from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuthStore } from '../stores/authStore';
import { authAPI } from '../utils/api';
import { Button } from '../components/Button';
import { colors, spacing } from '../constants/theme';

export default function SplashScreen() {
  const insets = useSafeAreaInsets();
  const { token, isLoading, login, isAuthenticated, user } = useAuthStore();
  const [fadeAnim] = useState(new Animated.Value(0));
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 1000,
      useNativeDriver: true,
    }).start();
  }, []);

  useEffect(() => {
    const checkAuth = async () => {
      if (isLoading) return;

      // If no token or user is null (logged out), show splash buttons
      if (!token) {
        setCheckingAuth(false);
        return;
      }

      // If token exists, try to validate it
      try {
        const response = await authAPI.getMe();
        await login(token, response.data);
        router.replace('/(tabs)');
      } catch (error) {
        console.log('Token invalid, staying on splash');
        setCheckingAuth(false);
      }
    };

    checkAuth();
  }, [token, isLoading, isAuthenticated]);

  // Show splash with buttons when not authenticated
  if (!isAuthenticated && !isLoading && !checkingAuth) {
    return (
      <View style={styles.container}>
        <Animated.View style={[styles.content, { opacity: fadeAnim }]}>
          {/* Logo Section */}
          <View style={styles.logoSection}>
            <Image
              source={require('../assets/images/IronStagLogo.png')}
              style={styles.logo}
              resizeMode="contain"
            />
          </View>
          
          {/* Tagline Section - Centered between logo and buttons */}
          <View style={styles.taglineSection}>
            <Text style={styles.tagline}>Hunt Smarter. Harvest Responsibly.</Text>
            <Text style={styles.subTagline}>AI-Powered Deer Aging</Text>
          </View>
          
          {/* Buttons Section */}
          <View style={[styles.buttonSection, { paddingBottom: insets.bottom + spacing.md }]}>
            <Button
              title="Get Started"
              onPress={() => router.push('/(auth)/login')}
              size="large"
              style={styles.primaryButton}
            />
            <Button
              title="Create Account"
              onPress={() => router.push('/(auth)/signup')}
              variant="outline"
              size="large"
              style={styles.secondaryButton}
            />
            <Text style={styles.footer}>Forged in Asgard, Tested in the Field</Text>
          </View>
        </Animated.View>
      </View>
    );
  }

  // Show loading state while checking auth
  if (checkingAuth || isLoading) {
    return (
      <View style={styles.container}>
        <Animated.View style={[styles.content, { opacity: fadeAnim }]}>
          <Image
            source={require('../assets/images/IronStagLogo.png')}
            style={styles.logo}
            resizeMode="contain"
          />
        </Animated.View>
      </View>
    );
  }

  // Fallback - show splash with buttons
  return (
    <View style={styles.container}>
      <Animated.View style={[styles.content, { opacity: fadeAnim }]}>
        {/* Logo Section */}
        <View style={styles.logoSection}>
          <Image
            source={require('../assets/images/IronStagLogo.png')}
            style={styles.logo}
            resizeMode="contain"
          />
        </View>
        
        {/* Tagline Section - Centered between logo and buttons */}
        <View style={styles.taglineSection}>
          <Text style={styles.tagline}>Hunt Smarter. Harvest Responsibly.</Text>
          <Text style={styles.subTagline}>AI-Powered Deer Aging</Text>
        </View>
        
        {/* Buttons Section */}
        <View style={[styles.buttonSection, { paddingBottom: insets.bottom + spacing.md }]}>
          <Button
            title="Get Started"
            onPress={() => router.push('/(auth)/login')}
            size="large"
            style={styles.primaryButton}
          />
          <Button
            title="Create Account"
            onPress={() => router.push('/(auth)/signup')}
            variant="outline"
            size="large"
            style={styles.secondaryButton}
          />
          <Text style={styles.footer}>Forged in Asgard, Tested in the Field</Text>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  content: {
    flex: 1,
  },
  logoSection: {
    alignItems: 'center',
    paddingTop: spacing.xl,
  },
  logo: {
    width: 350,
    height: 350,
  },
  taglineSection: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
  },
  tagline: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
    textAlign: 'center',
  },
  subTagline: {
    fontSize: 16,
    color: colors.primary,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
  buttonSection: {
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  primaryButton: {
    width: '100%',
  },
  secondaryButton: {
    width: '100%',
  },
  footer: {
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.sm,
    fontStyle: 'italic',
  },
});
