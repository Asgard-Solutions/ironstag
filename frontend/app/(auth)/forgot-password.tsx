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
  Image,
  Modal,
  TextInput,
} from 'react-native';
import { router } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ArrowLeft, Mail, Check, Lock } from 'lucide-react-native';
import { Button } from '../../components/Button';
import { Input } from '../../components/Input';
import { Card } from '../../components/Card';
import { authAPI } from '../../utils/api';
import { colors, spacing, borderRadius } from '../../constants/theme';

type Step = 'email' | 'code' | 'reset' | 'success';

export default function ForgotPasswordScreen() {
  const insets = useSafeAreaInsets();
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showCodeSentModal, setShowCodeSentModal] = useState(false);

  const handleRequestCode = async () => {
    if (!email || !/\S+@\S+\.\S+/.test(email)) {
      setErrors({ email: 'Please enter a valid email address' });
      return;
    }

    setLoading(true);
    try {
      await authAPI.requestPasswordReset(email);
      setShowCodeSentModal(true);
    } catch (error: any) {
      Alert.alert('Error', 'Failed to send reset code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCodeSentConfirm = () => {
    setShowCodeSentModal(false);
    setStep('code');
  };

  const handleCodeChange = (value: string, index: number) => {
    if (value.length > 1) {
      // Handle paste
      const digits = value.replace(/\D/g, '').slice(0, 6).split('');
      const newCode = [...code];
      digits.forEach((digit, i) => {
        if (index + i < 6) {
          newCode[index + i] = digit;
        }
      });
      setCode(newCode);
    } else {
      const newCode = [...code];
      newCode[index] = value;
      setCode(newCode);
    }
  };

  const handleVerifyCode = () => {
    const fullCode = code.join('');
    if (fullCode.length !== 6) {
      setErrors({ code: 'Please enter the complete 6-digit code' });
      return;
    }
    setStep('reset');
  };

  const handleResetPassword = async () => {
    const newErrors: Record<string, string> = {};
    
    if (!newPassword || newPassword.length < 8) {
      newErrors.newPassword = 'Password must be at least 8 characters';
    }
    
    if (!/[A-Z]/.test(newPassword)) {
      newErrors.newPassword = 'Password must contain an uppercase letter';
    }
    
    if (!/[a-z]/.test(newPassword)) {
      newErrors.newPassword = 'Password must contain a lowercase letter';
    }
    
    if (!/[0-9]/.test(newPassword)) {
      newErrors.newPassword = 'Password must contain a number';
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
        code: code.join(''),
        new_password: newPassword,
      });
      setStep('success');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to reset password.';
      Alert.alert('Error', message);
    } finally {
      setLoading(false);
    }
  };

  const renderEmailStep = () => (
    <>
      <View style={styles.headerContainer}>
        <Text style={styles.title}>Forgot Password?</Text>
        <Text style={styles.subtitle}>
          Enter your email address and we'll send you a verification code to reset your password.
        </Text>
      </View>

      <View style={styles.form}>
        <Input
          label="Email Address"
          placeholder="your@email.com"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
          error={errors.email}
        />

        <Button
          title="Send Reset Code"
          onPress={handleRequestCode}
          loading={loading}
          size="large"
          style={styles.submitButton}
        />
      </View>

      <View style={styles.backToLogin}>
        <Text style={styles.backToLoginText}>Remember your password? </Text>
        <TouchableOpacity onPress={() => router.back()}>
          <Text style={styles.backToLoginLink}>Sign In</Text>
        </TouchableOpacity>
      </View>
    </>
  );

  const renderCodeStep = () => (
    <>
      <TouchableOpacity style={styles.backButton} onPress={() => setStep('email')}>
        <ArrowLeft size={24} color={colors.textPrimary} />
      </TouchableOpacity>

      <View style={styles.headerContainer}>
        <Text style={styles.title}>Enter Verification Code</Text>
        <Text style={styles.subtitle}>
          We sent a 6-digit code to <Text style={styles.emailHighlight}>{email}</Text>
        </Text>
      </View>

      <View style={styles.codeContainer}>
        {code.map((digit, index) => (
          <TextInput
            key={index}
            style={[styles.codeInput, digit && styles.codeInputFilled]}
            value={digit}
            onChangeText={(value) => handleCodeChange(value, index)}
            keyboardType="number-pad"
            maxLength={6}
            selectTextOnFocus
          />
        ))}
      </View>

      {errors.code && <Text style={styles.errorText}>{errors.code}</Text>}

      <Button
        title="Verify Code"
        onPress={handleVerifyCode}
        size="large"
        style={styles.submitButton}
      />

      <TouchableOpacity style={styles.resendContainer} onPress={handleRequestCode}>
        <Text style={styles.resendText}>Didn't receive the code? </Text>
        <Text style={styles.resendLink}>Resend</Text>
      </TouchableOpacity>
    </>
  );

  const renderResetStep = () => (
    <>
      <TouchableOpacity style={styles.backButton} onPress={() => setStep('code')}>
        <ArrowLeft size={24} color={colors.textPrimary} />
      </TouchableOpacity>

      <View style={styles.headerContainer}>
        <Text style={styles.title}>Create New Password</Text>
        <Text style={styles.subtitle}>
          Your new password must be different from previously used passwords.
        </Text>
      </View>

      <View style={styles.form}>
        <Input
          label="New Password"
          placeholder="Enter new password"
          value={newPassword}
          onChangeText={setNewPassword}
          secureTextEntry
          error={errors.newPassword}
        />

        <Input
          label="Confirm Password"
          placeholder="Confirm new password"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          secureTextEntry
          error={errors.confirmPassword}
        />

        {/* Password Requirements */}
        <View style={styles.requirements}>
          <Text style={styles.requirementsTitle}>Password must contain:</Text>
          <View style={styles.requirementRow}>
            <Check size={16} color={newPassword.length >= 8 ? colors.harvest : colors.textMuted} />
            <Text style={[styles.requirementText, newPassword.length >= 8 && styles.requirementMet]}>
              At least 8 characters
            </Text>
          </View>
          <View style={styles.requirementRow}>
            <Check size={16} color={/[A-Z]/.test(newPassword) ? colors.harvest : colors.textMuted} />
            <Text style={[styles.requirementText, /[A-Z]/.test(newPassword) && styles.requirementMet]}>
              One uppercase letter
            </Text>
          </View>
          <View style={styles.requirementRow}>
            <Check size={16} color={/[a-z]/.test(newPassword) ? colors.harvest : colors.textMuted} />
            <Text style={[styles.requirementText, /[a-z]/.test(newPassword) && styles.requirementMet]}>
              One lowercase letter
            </Text>
          </View>
          <View style={styles.requirementRow}>
            <Check size={16} color={/[0-9]/.test(newPassword) ? colors.harvest : colors.textMuted} />
            <Text style={[styles.requirementText, /[0-9]/.test(newPassword) && styles.requirementMet]}>
              One number
            </Text>
          </View>
        </View>

        <Button
          title="Reset Password"
          onPress={handleResetPassword}
          loading={loading}
          size="large"
          style={styles.submitButton}
        />
      </View>
    </>
  );

  const renderSuccessStep = () => (
    <View style={styles.successContainer}>
      <View style={styles.successIcon}>
        <Check size={48} color={colors.harvest} />
      </View>
      <Text style={styles.successTitle}>Password Reset!</Text>
      <Text style={styles.successText}>
        Your password has been successfully reset. You can now sign in with your new password.
      </Text>
      <Button
        title="Sign In"
        onPress={() => router.replace('/(auth)/login')}
        size="large"
        style={styles.submitButton}
      />
    </View>
  );

  return (
    <View style={styles.container}>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={[
            styles.scrollContent,
            { paddingTop: insets.top + spacing.md, paddingBottom: insets.bottom + spacing.lg },
          ]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Logo */}
          <View style={styles.logoContainer}>
            <Image
              source={require('../../assets/images/iron_stag_logo.png')}
              style={styles.logo}
              resizeMode="contain"
            />
          </View>

          {step === 'email' && renderEmailStep()}
          {step === 'code' && renderCodeStep()}
          {step === 'reset' && renderResetStep()}
          {step === 'success' && renderSuccessStep()}

          {/* Footer */}
          <View style={styles.footer}>
            <Text style={styles.footerTagline}>Forged in Asgard, Tested in the Field</Text>
            <Text style={styles.footerCopyright}>© 2026 Asgard Solutions LLC</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Code Sent Modal */}
      <Modal visible={showCodeSentModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <Card style={styles.modalCard}>
            <View style={styles.modalIconContainer}>
              <Mail size={32} color={colors.primary} />
            </View>
            <Text style={styles.modalTitle}>Code Sent!</Text>
            <Text style={styles.modalText}>
              We've sent a verification code to{'\n'}
              <Text style={styles.modalEmail}>{email}</Text>
            </Text>
            <Text style={styles.modalSubtext}>
              Please check your inbox and spam folder.
            </Text>
            <Button
              title="Continue"
              onPress={handleCodeSentConfirm}
              size="large"
              style={styles.modalButton}
            />
          </Card>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: spacing.lg,
  },
  logoContainer: {
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  logo: {
    width: 160,
    height: 160,
  },
  backButton: {
    width: 44,
    height: 44,
    justifyContent: 'center',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
  },
  headerContainer: {
    marginBottom: spacing.xl,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: 16,
    color: colors.textSecondary,
    lineHeight: 24,
  },
  emailHighlight: {
    color: colors.primary,
    fontWeight: '500',
  },
  form: {
    marginBottom: spacing.lg,
  },
  submitButton: {
    marginTop: spacing.md,
  },
  backToLogin: {
    flexDirection: 'row',
    justifyContent: 'center',
  },
  backToLoginText: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  backToLoginLink: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '600',
  },
  codeContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  codeInput: {
    width: 48,
    height: 56,
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: '700',
    textAlign: 'center',
  },
  codeInputFilled: {
    borderColor: colors.primary,
  },
  errorText: {
    color: colors.error,
    fontSize: 14,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  resendContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.lg,
  },
  resendText: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  resendLink: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '600',
  },
  requirements: {
    backgroundColor: colors.backgroundCard,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  requirementsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  requirementRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  requirementText: {
    fontSize: 14,
    color: colors.textMuted,
  },
  requirementMet: {
    color: colors.harvest,
  },
  successContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
  },
  successIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.harvestBg,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  successTitle: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  successText: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: spacing.xl,
  },
  footer: {
    alignItems: 'center',
    marginTop: 'auto',
  },
  footerTagline: {
    fontSize: 13,
    color: colors.textMuted,
    fontStyle: 'italic',
    marginBottom: spacing.xs,
  },
  footerCopyright: {
    fontSize: 12,
    color: colors.textMuted,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  modalCard: {
    width: '100%',
    maxWidth: 340,
    alignItems: 'center',
    padding: spacing.xl,
  },
  modalIconContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(200, 162, 74, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  modalText: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
  },
  modalEmail: {
    color: colors.primary,
    fontWeight: '600',
  },
  modalSubtext: {
    fontSize: 14,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.sm,
    marginBottom: spacing.lg,
  },
  modalButton: {
    width: '100%',
  },
});
