/**
 * App Update Service
 * 
 * Handles version checking directly from Apple App Store and Google Play Store.
 * Opens the appropriate store for the user to download updates.
 */

import { Platform, Linking, Alert } from 'react-native';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Storage keys
const STORAGE_KEYS = {
  LAST_VERSION_CHECK: '@iron_stag_last_version_check',
  DISMISSED_VERSION: '@iron_stag_dismissed_version',
};

// Check interval in milliseconds (1 hour)
const CHECK_INTERVAL_MS = 60 * 60 * 1000;

// App Store IDs - UPDATE THESE WITH YOUR ACTUAL IDS
const APP_STORE_ID = '6478628123'; // Your Apple App Store ID
const PLAY_STORE_PACKAGE = 'io.asgardsolution.ironstag'; // Your Android package name

// Store URLs
const IOS_STORE_URL = `https://apps.apple.com/app/id${APP_STORE_ID}`;
const ANDROID_STORE_URL = `https://play.google.com/store/apps/details?id=${PLAY_STORE_PACKAGE}`;

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

/**
 * Compare two semantic version strings
 * Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal
 */
function compareVersions(v1: string, v2: string): number {
  const parts1 = v1.split('.').map(Number);
  const parts2 = v2.split('.').map(Number);
  
  for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p1 > p2) return 1;
    if (p1 < p2) return -1;
  }
  return 0;
}

class AppUpdateService {
  private currentVersion: string;
  private buildNumber: string;
  private platform: 'ios' | 'android' | 'web';

  constructor() {
    this.currentVersion = Constants.expoConfig?.version || '1.0.0';
    this.buildNumber = Platform.OS === 'ios' 
      ? Constants.expoConfig?.ios?.buildNumber || '1'
      : String(Constants.expoConfig?.android?.versionCode || 1);
    this.platform = Platform.OS as 'ios' | 'android' | 'web';
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
   * Get store URL for current platform
   */
  getStoreUrl(): string {
    return Platform.OS === 'ios' ? IOS_STORE_URL : ANDROID_STORE_URL;
  }

  /**
   * Check if we should perform a version check (rate limiting)
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
   * Clear dismissed version
   */
  async clearDismissedVersion(): Promise<void> {
    try {
      await AsyncStorage.removeItem(STORAGE_KEYS.DISMISSED_VERSION);
    } catch (error) {
      console.warn('Failed to clear dismissed version:', error);
    }
  }

  /**
   * Fetch latest version from Apple App Store
   */
  private async checkiOSVersion(): Promise<{ version: string; releaseNotes: string | null } | null> {
    try {
      // Apple's iTunes Lookup API
      const response = await fetch(
        `https://itunes.apple.com/lookup?id=${APP_STORE_ID}&country=us`
      );
      const data = await response.json();
      
      if (data.resultCount > 0) {
        const result = data.results[0];
        return {
          version: result.version,
          releaseNotes: result.releaseNotes || null,
        };
      }
      return null;
    } catch (error) {
      console.error('[AppUpdateService] iOS version check failed:', error);
      return null;
    }
  }

  /**
   * Fetch latest version from Google Play Store
   * Note: Google doesn't have an official API, so we use a workaround
   */
  private async checkAndroidVersion(): Promise<{ version: string; releaseNotes: string | null } | null> {
    try {
      // We'll try to scrape the Play Store page for version info
      // This is a common approach since Google doesn't have an official API
      const response = await fetch(
        `https://play.google.com/store/apps/details?id=${PLAY_STORE_PACKAGE}&hl=en`
      );
      const html = await response.text();
      
      // Try to extract version from the page
      // Look for pattern like "Current Version" or version in meta tags
      const versionMatch = html.match(/\[\[\["(\d+\.\d+\.?\d*)"\]\]/);
      if (versionMatch && versionMatch[1]) {
        return {
          version: versionMatch[1],
          releaseNotes: null, // Play Store scraping for notes is unreliable
        };
      }
      
      // Alternative pattern
      const altMatch = html.match(/"softwareVersion":"(\d+\.\d+\.?\d*)"/);
      if (altMatch && altMatch[1]) {
        return {
          version: altMatch[1],
          releaseNotes: null,
        };
      }
      
      return null;
    } catch (error) {
      console.error('[AppUpdateService] Android version check failed:', error);
      return null;
    }
  }

  /**
   * Check for app updates from the stores
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
      console.log(`[AppUpdateService] Checking for updates: platform=${this.platform}, current=${this.currentVersion}`);

      let storeInfo: { version: string; releaseNotes: string | null } | null = null;
      
      if (Platform.OS === 'ios') {
        storeInfo = await this.checkiOSVersion();
      } else if (Platform.OS === 'android') {
        storeInfo = await this.checkAndroidVersion();
      }

      await this.markVersionChecked();

      if (!storeInfo) {
        console.log('[AppUpdateService] Could not fetch store version');
        return {
          update_available: false,
          update_mode: 'none',
          latest_version: this.currentVersion,
          min_supported_version: '1.0.0',
          release_notes: null,
          store_url: this.getStoreUrl(),
          message: null,
        };
      }

      const comparison = compareVersions(storeInfo.version, this.currentVersion);
      const updateAvailable = comparison > 0;

      console.log(`[AppUpdateService] Store version: ${storeInfo.version}, Current: ${this.currentVersion}, Update available: ${updateAvailable}`);

      const result: VersionCheckResponse = {
        update_available: updateAvailable,
        update_mode: updateAvailable ? 'soft' : 'none',
        latest_version: storeInfo.version,
        min_supported_version: '1.0.0',
        release_notes: storeInfo.releaseNotes,
        store_url: this.getStoreUrl(),
        message: updateAvailable ? `Version ${storeInfo.version} is available!` : null,
      };

      return result;
    } catch (error: any) {
      console.error('[AppUpdateService] Version check failed:', error.message);
      return null;
    }
  }

  /**
   * Open the app store to update
   */
  async openStore(storeUrl?: string): Promise<boolean> {
    const url = storeUrl || this.getStoreUrl();
    try {
      const canOpen = await Linking.canOpenURL(url);
      if (canOpen) {
        await Linking.openURL(url);
        return true;
      } else {
        // Try alternative URLs
        if (Platform.OS === 'ios') {
          await Linking.openURL(`itms-apps://itunes.apple.com/app/id${APP_STORE_ID}`);
          return true;
        } else {
          await Linking.openURL(`market://details?id=${PLAY_STORE_PACKAGE}`);
          return true;
        }
      }
    } catch (error) {
      console.error('[AppUpdateService] Failed to open store:', error);
      // Last resort - try the web URLs
      try {
        await Linking.openURL(url);
        return true;
      } catch {
        return false;
      }
    }
  }

  /**
   * Check for updates and show alert if available
   */
  async checkAndPrompt(force: boolean = false): Promise<void> {
    const result = await this.checkForUpdates(force);
    
    if (result?.update_available) {
      Alert.alert(
        'Update Available',
        `A new version (${result.latest_version}) is available!\n\n${result.release_notes || 'Update to get the latest features and improvements.'}`,
        [
          {
            text: 'Later',
            style: 'cancel',
            onPress: () => this.dismissVersion(result.latest_version),
          },
          {
            text: 'Update Now',
            onPress: () => this.openStore(result.store_url),
          },
        ]
      );
    } else if (force) {
      // Only show "up to date" message if user manually checked
      Alert.alert(
        'Up to Date',
        `You're running the latest version (${this.currentVersion}).`,
        [{ text: 'OK' }]
      );
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
