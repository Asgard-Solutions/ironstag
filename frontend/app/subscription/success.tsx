import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { subscriptionAPI } from '../../utils/api';
import { useAuthStore } from '../../stores/authStore';

export default function SubscriptionSuccess() {
  const router = useRouter();
  const { updateUser, refreshUser } = useAuthStore();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Confirming your subscription...');

  useEffect(() => {
    confirmSubscription();
  }, []);

  const confirmSubscription = async () => {
    try {
      // Give Stripe webhook a moment to process
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Refresh subscription status from server
      const response = await subscriptionAPI.getStatus();
      
      if (response.data.is_premium || response.data.tier === 'master_stag') {
        // Update local state
        updateUser({ 
          subscription_tier: 'master_stag',
          scans_remaining: -1 
        });
        
        setStatus('success');
        setMessage('Welcome to Master Stag!');
        
        // Redirect to home after showing success
        setTimeout(() => {
          router.replace('/(tabs)');
        }, 2500);
      } else {
        // Subscription not yet processed, try refreshing user
        await refreshUser();
        
        // Check again
        const retryResponse = await subscriptionAPI.getStatus();
        if (retryResponse.data.is_premium || retryResponse.data.tier === 'master_stag') {
          updateUser({ 
            subscription_tier: 'master_stag',
            scans_remaining: -1 
          });
          setStatus('success');
          setMessage('Welcome to Master Stag!');
          setTimeout(() => {
            router.replace('/(tabs)');
          }, 2500);
        } else {
          // Still processing
          setStatus('success');
          setMessage('Payment received! Your subscription will be active shortly.');
          setTimeout(() => {
            router.replace('/(tabs)');
          }, 3000);
        }
      }
    } catch (error) {
      console.error('Error confirming subscription:', error);
      setStatus('error');
      setMessage('There was an issue confirming your subscription. Please check your profile or contact support.');
      
      // Still redirect after showing error
      setTimeout(() => {
        router.replace('/(tabs)/profile');
      }, 4000);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.content}>
        {status === 'loading' && (
          <>
            <ActivityIndicator size="large" color="#D4A574" />
            <Text style={styles.title}>Processing...</Text>
            <Text style={styles.message}>{message}</Text>
          </>
        )}
        
        {status === 'success' && (
          <>
            <View style={styles.iconContainer}>
              <Ionicons name="checkmark-circle" size={80} color="#4CAF50" />
            </View>
            <Text style={styles.title}>Success!</Text>
            <Text style={styles.message}>{message}</Text>
            <Text style={styles.subtitle}>Unlimited scans unlocked 🦌</Text>
          </>
        )}
        
        {status === 'error' && (
          <>
            <View style={styles.iconContainer}>
              <Ionicons name="alert-circle" size={80} color="#FF9800" />
            </View>
            <Text style={styles.title}>Almost There</Text>
            <Text style={styles.message}>{message}</Text>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1a1a1a',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  content: {
    alignItems: 'center',
    maxWidth: 320,
  },
  iconContainer: {
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#FFFFFF',
    marginTop: 16,
    marginBottom: 8,
  },
  message: {
    fontSize: 16,
    color: '#B0B0B0',
    textAlign: 'center',
    lineHeight: 24,
  },
  subtitle: {
    fontSize: 18,
    color: '#D4A574',
    marginTop: 16,
    fontWeight: '600',
  },
});
