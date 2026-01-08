import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Mail, ArrowLeft, Lock, KeyRound } from 'lucide-react-native';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { authAPI } from '../../utils/api';
import { colors, spacing } from '../../constants/theme';

export default function ForgotPasswordScreen() {
  const insets = useSafeAreaInsets();
  const [step, setStep] = useState<'email' | 'code' | 'reset'>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleRequestCode = async () => {
    if (!email || !/\S+@\S+\.\S+/.test(email)) {
      setErrors({ email: 'Valid email is required' });
      return;
    }

    setLoading(true);
    try {
      const response = await authAPI.requestPasswordReset(email);
      // For demo, we show the code (in production, it would be sent via email)
      if (response.data.code) {
        Alert.alert('Code Sent', `Your reset code is: ${response.data.code}`);
      }
      setStep('code');
    } catch (error: any) {
      Alert.alert('Error', 'Failed to send reset code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = () => {
    if (!code || code.length !== 6) {
      setErrors({ code: 'Enter the 6-digit code' });
      return;
    }
    setStep('reset');
  };

  const handleResetPassword = async () => {
    const newErrors: Record<string, string> = {};
    
    if (!newPassword || newPassword.length < 6) {
      newErrors.newPassword = 'Password must be at least 6 characters';
    }
    if (newPassword !== confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }
    
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    try {
      await authAPI.verifyPasswordReset({
        email,
        code,
        new_password: newPassword,
      });
      Alert.alert('Success', 'Password reset successful!', [
        { text: 'OK', onPress: () => router.replace('/(auth)/login') },
      ]);
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to reset password.';
      Alert.alert('Error', message);
    } finally {
      setLoading(false);
    }
  };

  const renderStep = () => {
    switch (step) {
      case 'email':
        return (
          <>
            <Text style={styles.stepDescription}>
              Enter your email address and we'll send you a code to reset your password.
            </Text>
            <Input
              label="Email"
              placeholder="Enter your email"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              error={errors.email}
              icon={<Mail size={20} color={colors.textMuted} />}
            />
            <Button
              title="Send Reset Code"
              onPress={handleRequestCode}
              loading={loading}
              size="large"
              style={styles.submitButton}
            />
          </>
        );

      case 'code':
        return (
          <>
            <Text style={styles.stepDescription}>
              Enter the 6-digit code sent to your email.
            </Text>
            <Input
              label="Verification Code"
              placeholder="Enter 6-digit code"
              value={code}
              onChangeText={setCode}
              keyboardType="number-pad"
              maxLength={6}
              error={errors.code}
              icon={<KeyRound size={20} color={colors.textMuted} />}
            />
            <Button
              title="Verify Code"
              onPress={handleVerifyCode}
              loading={loading}
              size="large"
              style={styles.submitButton}
            />
            <TouchableOpacity
              style={styles.resendButton}
              onPress={handleRequestCode}
            >
              <Text style={styles.resendText}>Resend Code</Text>
            </TouchableOpacity>
          </>
        );

      case 'reset':
        return (
          <>
            <Text style={styles.stepDescription}>
              Create a new password for your account.
            </Text>
            <Input
              label="New Password"
              placeholder="Enter new password"
              value={newPassword}
              onChangeText={setNewPassword}
              secureTextEntry
              error={errors.newPassword}
              icon={<Lock size={20} color={colors.textMuted} />}
            />
            <Input
              label="Confirm Password"
              placeholder="Confirm new password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
              error={errors.confirmPassword}
              icon={<Lock size={20} color={colors.textMuted} />}
            />
            <Button
              title="Reset Password"
              onPress={handleResetPassword}
              loading={loading}
              size="large"
              style={styles.submitButton}
            />
          </>
        );
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          { paddingTop: insets.top + spacing.md, paddingBottom: insets.bottom + spacing.lg },
        ]}
        keyboardShouldPersistTaps="handled"
      >
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => {
            if (step === 'email') {
              router.back();
            } else if (step === 'code') {
              setStep('email');
            } else {
              setStep('code');
            }
          }}
        >
          <ArrowLeft size={24} color={colors.textPrimary} />
        </TouchableOpacity>

        <View style={styles.header}>
          <Text style={styles.title}>Reset Password</Text>
          <Text style={styles.subtitle}>
            {step === 'email' && 'Step 1 of 3'}
            {step === 'code' && 'Step 2 of 3'}
            {step === 'reset' && 'Step 3 of 3'}
          </Text>
        </View>

        <View style={styles.form}>
          {renderStep()}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    padding: spacing.lg,
  },
  backButton: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'flex-start',
  },
  header: {
    marginTop: spacing.xl,
    marginBottom: spacing.xl,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: 14,
    color: colors.primary,
    fontWeight: '500',
  },
  form: {
    flex: 1,
  },
  stepDescription: {
    fontSize: 16,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
    lineHeight: 24,
  },
  submitButton: {
    marginTop: spacing.md,
  },
  resendButton: {
    alignSelf: 'center',
    marginTop: spacing.lg,
    padding: spacing.sm,
  },
  resendText: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '500',
  },
});
