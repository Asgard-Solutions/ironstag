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
          <Image
            source={require('../assets/images/IronStagLogo.png')}
            style={styles.logo}
            resizeMode="contain"
          />
        </Animated.View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.content, { opacity: fadeAnim }]}>
        <Image
          source={require('../assets/images/IronStagLogo.png')}
          style={styles.logo}
          resizeMode="contain"
        />
        
        <Text style={styles.tagline}>Hunt Smarter. Harvest Responsibly.</Text>
        <Text style={styles.subTagline}>AI-Powered Deer Aging</Text>
        
        <View style={[styles.buttonContainer, { paddingBottom: insets.bottom + spacing.lg }]}>
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
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  logo: {
    width: 350,
    height: 350,
  },
  buttonContainer: {
    position: 'absolute',
    bottom: 0,
    left: spacing.lg,
    right: spacing.lg,
    gap: spacing.md,
  },
  primaryButton: {
    width: '100%',
  },
  secondaryButton: {
    width: '100%',
  },
});
