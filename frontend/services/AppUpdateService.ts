/**
 * App Update Service
 * 
 * Handles version checking and update prompts for iOS and Android.
 * Communicates with backend to check for available updates.
 */

import { Platform, Linking } from 'react-native';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from '../utils/api';

// Storage keys
const STORAGE_KEYS = {
  LAST_VERSION_CHECK: '@iron_stag_last_version_check',
  DISMISSED_VERSION: '@iron_stag_dismissed_version',
};

// Check interval in milliseconds (1 hour)
const CHECK_INTERVAL_MS = 60 * 60 * 1000;

export interface VersionCheckResponse {
  update_available: boolean;
  update_mode: 'none' | 'soft' | 'force';
  latest_version: string;
  min_supported_version: string;
  release_notes: string | null;
  store_url: string;
  message: string | null;
}

export interface UpdateState {
  isChecking: boolean;
  hasUpdate: boolean;
  updateMode: 'none' | 'soft' | 'force';
  latestVersion: string;
  currentVersion: string;
  releaseNotes: string | null;
  storeUrl: string;
  message: string | null;
  error: string | null;
}

class AppUpdateService {
  private currentVersion: string;
  private buildNumber: string;
  private platform: 'ios' | 'android';

  constructor() {
    this.currentVersion = Constants.expoConfig?.version || '1.0.0';
    this.buildNumber = Platform.OS === 'ios' 
      ? Constants.expoConfig?.ios?.buildNumber || '1'
      : String(Constants.expoConfig?.android?.versionCode || 1);
    this.platform = Platform.OS === 'ios' ? 'ios' : 'android';
  }

  /**
   * Get the current app version
   */
  getCurrentVersion(): string {
    return this.currentVersion;
  }

  /**
   * Get the current build number
   */
  getBuildNumber(): string {
    return this.buildNumber;
  }

  /**
   * Check if we should perform a version check
   * (Rate limiting to avoid excessive API calls)
   */
  async shouldCheckVersion(): Promise<boolean> {
    try {
      const lastCheck = await AsyncStorage.getItem(STORAGE_KEYS.LAST_VERSION_CHECK);
      if (!lastCheck) return true;

      const lastCheckTime = parseInt(lastCheck, 10);
      const now = Date.now();

      return (now - lastCheckTime) > CHECK_INTERVAL_MS;
    } catch {
      return true;
    }
  }

  /**
   * Mark that we've performed a version check
   */
  private async markVersionChecked(): Promise<void> {
    try {
      await AsyncStorage.setItem(
        STORAGE_KEYS.LAST_VERSION_CHECK,
        String(Date.now())
      );
    } catch (error) {
      console.warn('Failed to save version check timestamp:', error);
    }
  }

  /**
   * Check if user has dismissed the soft update prompt for this version
   */
  async hasUserDismissedVersion(version: string): Promise<boolean> {
    try {
      const dismissedVersion = await AsyncStorage.getItem(STORAGE_KEYS.DISMISSED_VERSION);
      return dismissedVersion === version;
    } catch {
      return false;
    }
  }

  /**
   * Mark that user has dismissed the soft update prompt for a version
   */
  async dismissVersion(version: string): Promise<void> {
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.DISMISSED_VERSION, version);
    } catch (error) {
      console.warn('Failed to save dismissed version:', error);
    }
  }

  /**
   * Clear dismissed version (e.g., when user manually checks for updates)
   */
  async clearDismissedVersion(): Promise<void> {
    try {
      await AsyncStorage.removeItem(STORAGE_KEYS.DISMISSED_VERSION);
    } catch (error) {
      console.warn('Failed to clear dismissed version:', error);
    }
  }

  /**
   * Check for app updates from the backend
   */
  async checkForUpdates(force: boolean = false): Promise<VersionCheckResponse | null> {
    // Skip check if we're on web
    if (Platform.OS === 'web') {
      return null;
    }

    // Check if we should perform the check (rate limiting)
    if (!force) {
      const shouldCheck = await this.shouldCheckVersion();
      if (!shouldCheck) {
        console.log('[AppUpdateService] Skipping version check (rate limited)');
        return null;
      }
    }

    try {
      console.log(`[AppUpdateService] Checking for updates: platform=${this.platform}, version=${this.currentVersion}`);

      const response = await api.post('/api/app/version-check', {
        platform: this.platform,
        current_version: this.currentVersion,
        build_number: this.buildNumber,
      });

      await this.markVersionChecked();

      const data: VersionCheckResponse = response.data;
      console.log('[AppUpdateService] Version check result:', data);

      return data;
    } catch (error: any) {
      console.error('[AppUpdateService] Version check failed:', error.message);
      // Don't throw - version check failures shouldn't break the app
      return null;
    }
  }

  /**
   * Open the app store to update
   */
  async openStore(storeUrl: string): Promise<boolean> {
    try {
      const canOpen = await Linking.canOpenURL(storeUrl);
      if (canOpen) {
        await Linking.openURL(storeUrl);
        return true;
      }
      return false;
    } catch (error) {
      console.error('[AppUpdateService] Failed to open store:', error);
      return false;
    }
  }

  /**
   * Get the appropriate store name for the current platform
   */
  getStoreName(): string {
    return Platform.OS === 'ios' ? 'App Store' : 'Google Play';
  }
}

// Export singleton instance
export const appUpdateService = new AppUpdateService();

// Export class for testing
export { AppUpdateService };
