import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface User {
  id: string;
  email: string;
  name: string;
  username?: string;
  subscription_tier: string;
  scans_remaining: number;
  disclaimer_accepted: boolean;
  created_at: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  login: (token: string, user: User) => Promise<void>;
  logout: () => Promise<void>;
  loadToken: () => Promise<void>;
  updateUser: (updates: Partial<User>) => void;
}

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

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: null,
  isLoading: true,
  isAuthenticated: false,

  setUser: (user) => set({ user, isAuthenticated: !!user }),

  setToken: (token) => set({ token }),

  login: async (token, user) => {
    await storage.setItem('auth_token', token);
    set({ token, user, isAuthenticated: true, isLoading: false });
  },

  logout: async () => {
    await storage.removeItem('auth_token');
    set({ token: null, user: null, isAuthenticated: false });
  },

  loadToken: async () => {
    try {
      const token = await storage.getItem('auth_token');
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
}));
