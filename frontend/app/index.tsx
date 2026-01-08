import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, Image, Animated } from 'react-native';
import { router } from 'expo-router';
import { useAuthStore } from '../stores/authStore';
import { authAPI } from '../utils/api';
import { Button } from '../components/Button';
import { colors, spacing } from '../constants/theme';

export default function SplashScreen() {
  const { token, isLoading, login, isAuthenticated } = useAuthStore();
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

      if (token) {
        try {
          const response = await authAPI.getMe();
          await login(token, response.data);
          router.replace('/(tabs)');
        } catch (error) {
          console.log('Token invalid, staying on splash');
          setCheckingAuth(false);
        }
      } else {
        setCheckingAuth(false);
      }
    };

    checkAuth();
  }, [token, isLoading]);

  if (checkingAuth || isLoading) {
    return (
      <View style={styles.container}>
        <Animated.View style={[styles.content, { opacity: fadeAnim }]}>
          <View style={styles.logoContainer}>
            <Text style={styles.logoText}>IRON STAG</Text>
            <View style={styles.antlerDecor} />
          </View>
          <Text style={styles.tagline}>Hunt Smarter. Harvest Responsibly.</Text>
          <Text style={styles.subTagline}>Forged in Asgard, Tested in the Field</Text>
        </Animated.View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.content, { opacity: fadeAnim }]}>
        <View style={styles.logoContainer}>
          <Text style={styles.logoText}>IRON STAG</Text>
          <View style={styles.antlerDecor} />
        </View>
        <Text style={styles.tagline}>Hunt Smarter. Harvest Responsibly.</Text>
        <Text style={styles.subTagline}>Forged in Asgard, Tested in the Field</Text>
        
        <View style={styles.buttonContainer}>
          <Button
            title="Get Started"
            onPress={() => router.push('/(auth)/signup')}
            size="large"
            style={styles.primaryButton}
          />
          <Button
            title="I Already Have an Account"
            onPress={() => router.push('/(auth)/login')}
            variant="outline"
            size="large"
            style={styles.secondaryButton}
          />
        </View>
      </Animated.View>
      
      <Text style={styles.footer}>AI-Powered Deer Aging for Ethical Hunters</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  content: {
    alignItems: 'center',
    width: '100%',
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  logoText: {
    fontSize: 48,
    fontWeight: '700',
    color: colors.primary,
    letterSpacing: 4,
  },
  antlerDecor: {
    width: 80,
    height: 4,
    backgroundColor: colors.primary,
    marginTop: spacing.md,
    borderRadius: 2,
  },
  tagline: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  subTagline: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    fontStyle: 'italic',
  },
  buttonContainer: {
    width: '100%',
    marginTop: spacing.xxl,
    gap: spacing.md,
  },
  primaryButton: {
    width: '100%',
  },
  secondaryButton: {
    width: '100%',
  },
  footer: {
    position: 'absolute',
    bottom: spacing.xl,
    color: colors.textMuted,
    fontSize: 12,
  },
});
