import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface User {
  id: string;
  email: string;
  name: string;
  username?: string;
  subscription_tier: string;
  scans_remaining: number;  // For free tier: lifetime remaining (0-3), for premium: -1 (unlimited)
  total_scans_used: number; // Lifetime total scans used
  disclaimer_accepted: boolean;
  disclaimer_accepted_at?: string;
  created_at: string;
  state?: string;  // Two-letter state code for region calibration
}

interface BiometricState {
  isAvailable: boolean;
  isEnabled: boolean;
  biometricType: 'fingerprint' | 'facial' | 'iris' | 'none';
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  biometric: BiometricState;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  login: (token: string, user: User) => Promise<void>;
  logout: () => Promise<void>;
  loadToken: () => Promise<void>;
  updateUser: (updates: Partial<User>) => void;
  // Biometric methods
  checkBiometricAvailability: () => Promise<void>;
  enableBiometric: () => Promise<boolean>;
  disableBiometric: () => Promise<void>;
  authenticateWithBiometric: () => Promise<{ success: boolean; token?: string; error?: string }>;
  isBiometricEnabled: () => Promise<boolean>;
}

// Storage keys
const AUTH_TOKEN_KEY = 'auth_token';
const BIOMETRIC_ENABLED_KEY = 'biometric_enabled';
const BIOMETRIC_TOKEN_KEY = 'biometric_auth_token';

const storage = {
  getItem: async (key: string): Promise<string | null> => {
    if (Platform.OS === 'web') {
      return AsyncStorage.getItem(key);
    }
    return SecureStore.getItemAsync(key);
  },
  setItem: async (key: string, value: string): Promise<void> => {
    if (Platform.OS === 'web') {
      return AsyncStorage.setItem(key, value);
    }
    return SecureStore.setItemAsync(key, value);
  },
  removeItem: async (key: string): Promise<void> => {
    if (Platform.OS === 'web') {
      return AsyncStorage.removeItem(key);
    }
    return SecureStore.deleteItemAsync(key);
  },
};

// Helper to get biometric type name
const getBiometricTypeName = (types: LocalAuthentication.AuthenticationType[]): 'fingerprint' | 'facial' | 'iris' | 'none' => {
  // On Android, prioritize fingerprint as it's more common
  // On iOS, Face ID takes precedence
  if (Platform.OS === 'android') {
    if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      return 'fingerprint';
    }
    if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      return 'facial';
    }
  } else {
    // iOS - Face ID takes precedence
    if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
      return 'facial';
    }
    if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
      return 'fingerprint';
    }
  }
  if (types.includes(LocalAuthentication.AuthenticationType.IRIS)) {
    return 'iris';
  }
  return 'none';
};

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: true,
  isAuthenticated: false,
  biometric: {
    isAvailable: false,
    isEnabled: false,
    biometricType: 'none',
  },

  setUser: (user) => set({ user, isAuthenticated: !!user }),

  setToken: (token) => set({ token }),

  login: async (token, user) => {
    await storage.setItem(AUTH_TOKEN_KEY, token);
    set({ token, user, isAuthenticated: true, isLoading: false });
  },

  logout: async () => {
    await storage.removeItem(AUTH_TOKEN_KEY);
    // Don't remove biometric token on logout - user might want to use it again
    set({ token: null, user: null, isAuthenticated: false, isLoading: false });
  },

  loadToken: async () => {
    try {
      const token = await storage.getItem(AUTH_TOKEN_KEY);
      if (token) {
        set({ token, isLoading: false });
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Error loading token:', error);
      set({ isLoading: false });
    }
  },

  updateUser: (updates) => {
    const { user } = get();
    if (user) {
      set({ user: { ...user, ...updates } });
    }
  },

  // Check if biometric authentication is available on this device
  checkBiometricAvailability: async () => {
    if (Platform.OS === 'web') {
      set({ 
        biometric: { 
          isAvailable: false, 
          isEnabled: false, 
          biometricType: 'none' 
        } 
      });
      return;
    }

    try {
      // Check if hardware exists
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      
      // Check if biometrics are enrolled (user has set up fingerprint/face)
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();
      
      // Get supported authentication types
      const supportedTypes = await LocalAuthentication.supportedAuthenticationTypesAsync();
      const biometricType = getBiometricTypeName(supportedTypes);
      
      // Check if user has enabled biometric login for this app
      const biometricEnabled = await storage.getItem(BIOMETRIC_ENABLED_KEY);
      
      const isAvailable = hasHardware && isEnrolled;
      
      set({
        biometric: {
          isAvailable,
          isEnabled: biometricEnabled === 'true' && isAvailable,
          biometricType,
        },
      });
      
      console.log('[Auth] Biometric check:', { hasHardware, isEnrolled, biometricType, isEnabled: biometricEnabled === 'true' });
    } catch (error) {
      console.error('[Auth] Error checking biometric availability:', error);
      set({ 
        biometric: { 
          isAvailable: false, 
          isEnabled: false, 
          biometricType: 'none' 
        } 
      });
    }
  },

  // Enable biometric login (stores current token securely)
  enableBiometric: async () => {
    const { token, biometric } = get();
    
    if (!biometric.isAvailable) {
      console.warn('[Auth] Biometric not available on this device');
      return false;
    }
    
    if (!token) {
      console.warn('[Auth] No token to store for biometric');
      return false;
    }

    try {
      // Authenticate first to confirm user identity
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Confirm your identity to enable biometric login',
        cancelLabel: 'Cancel',
        disableDeviceFallback: false,
      });

      if (!result.success) {
        console.log('[Auth] Biometric authentication cancelled or failed');
        return false;
      }

      // Store token securely for biometric access
      await storage.setItem(BIOMETRIC_TOKEN_KEY, token);
      await storage.setItem(BIOMETRIC_ENABLED_KEY, 'true');
      
      set({
        biometric: {
          ...biometric,
          isEnabled: true,
        },
      });
      
      console.log('[Auth] Biometric login enabled');
      return true;
    } catch (error) {
      console.error('[Auth] Error enabling biometric:', error);
      return false;
    }
  },

  // Disable biometric login
  disableBiometric: async () => {
    const { biometric } = get();
    
    try {
      await storage.removeItem(BIOMETRIC_TOKEN_KEY);
      await storage.setItem(BIOMETRIC_ENABLED_KEY, 'false');
      
      set({
        biometric: {
          ...biometric,
          isEnabled: false,
        },
      });
      
      console.log('[Auth] Biometric login disabled');
    } catch (error) {
      console.error('[Auth] Error disabling biometric:', error);
    }
  },

  // Authenticate with biometric and return stored token
  authenticateWithBiometric: async () => {
    const { biometric } = get();
    
    if (!biometric.isEnabled) {
      return { success: false, error: 'Biometric login not enabled' };
    }

    try {
      // Get the prompt message based on biometric type
      let promptMessage = 'Login with biometrics';
      if (biometric.biometricType === 'facial') {
        promptMessage = 'Login with Face ID';
      } else if (biometric.biometricType === 'fingerprint') {
        promptMessage = 'Login with fingerprint';
      }

      const result = await LocalAuthentication.authenticateAsync({
        promptMessage,
        cancelLabel: 'Use Password',
        disableDeviceFallback: false,
      });

      if (!result.success) {
        if (result.error === 'user_cancel') {
          return { success: false, error: 'cancelled' };
        }
        return { success: false, error: result.error || 'Authentication failed' };
      }

      // Retrieve stored token
      const storedToken = await storage.getItem(BIOMETRIC_TOKEN_KEY);
      
      if (!storedToken) {
        // Token was cleared, disable biometric
        await storage.setItem(BIOMETRIC_ENABLED_KEY, 'false');
        set({
          biometric: {
            ...biometric,
            isEnabled: false,
          },
        });
        return { success: false, error: 'Please login with password and re-enable biometric' };
      }

      console.log('[Auth] Biometric authentication successful');
      return { success: true, token: storedToken };
    } catch (error) {
      console.error('[Auth] Biometric authentication error:', error);
      return { success: false, error: 'Authentication failed' };
    }
  },

  // Check if biometric is enabled (for UI)
  isBiometricEnabled: async () => {
    const enabled = await storage.getItem(BIOMETRIC_ENABLED_KEY);
    return enabled === 'true';
  },
}));
