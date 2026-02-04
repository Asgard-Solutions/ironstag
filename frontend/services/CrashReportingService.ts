/**
 * Crash Reporting Service
 * 
 * Captures and reports app crashes/errors to the backend.
 * Can be enabled/disabled via backend configuration.
 */

import { Platform } from 'react-native';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api } from '../utils/api';

const STORAGE_KEYS = {
  DEBUG_ENABLED: '@iron_stag_debug_enabled',
  PENDING_CRASHES: '@iron_stag_pending_crashes',
};

export interface CrashReport {
  id: string;
  timestamp: string;
  error_message: string;
  error_stack: string | null;
  component_stack: string | null;
  screen: string | null;
  user_id: string | null;
  platform: 'ios' | 'android' | 'web';
  app_version: string;
  build_number: string;
  device_info: {
    os_version: string | null;
    device_name: string | null;
  };
  extra_data: Record<string, any>;
}

class CrashReportingService {
  private isEnabled: boolean = false;
  private userId: string | null = null;
  private currentScreen: string | null = null;
  private appVersion: string;
  private buildNumber: string;
  private platform: 'ios' | 'android' | 'web';

  constructor() {
    this.appVersion = Constants.expoConfig?.version || '1.0.0';
    this.buildNumber = Platform.OS === 'ios'
      ? Constants.expoConfig?.ios?.buildNumber || '1'
      : String(Constants.expoConfig?.android?.versionCode || 1);
    this.platform = Platform.OS as 'ios' | 'android' | 'web';
  }

  /**
   * Initialize the crash reporting service
   */
  async initialize(): Promise<void> {
    try {
      // Check if debug mode is enabled from backend
      await this.checkDebugStatus();
      
      // Set up global error handlers
      this.setupErrorHandlers();
      
      // Try to send any pending crash reports
      await this.sendPendingReports();
      
      console.log(`[CrashReporting] Initialized - enabled: ${this.isEnabled}`);
    } catch (error) {
      console.error('[CrashReporting] Initialization failed:', error);
    }
  }

  /**
   * Check if debug mode is enabled from backend
   */
  async checkDebugStatus(): Promise<void> {
    try {
      const response = await api.get('/api/debug/status');
      this.isEnabled = response.data?.debug_enabled || false;
      
      // Cache the status locally
      await AsyncStorage.setItem(
        STORAGE_KEYS.DEBUG_ENABLED,
        JSON.stringify(this.isEnabled)
      );
    } catch (error) {
      // Fall back to cached status
      try {
        const cached = await AsyncStorage.getItem(STORAGE_KEYS.DEBUG_ENABLED);
        if (cached) {
          this.isEnabled = JSON.parse(cached);
        }
      } catch {
        this.isEnabled = false;
      }
    }
  }

  /**
   * Set the current user ID for crash reports
   */
  setUserId(userId: string | null): void {
    this.userId = userId;
  }

  /**
   * Set the current screen name for crash reports
   */
  setCurrentScreen(screen: string): void {
    this.currentScreen = screen;
  }

  /**
   * Setup global error handlers
   */
  private setupErrorHandlers(): void {
    // Handle unhandled promise rejections
    const originalHandler = (global as any).onunhandledrejection;
    (global as any).onunhandledrejection = (event: any) => {
      this.captureError(
        event?.reason || new Error('Unhandled Promise Rejection'),
        { type: 'unhandled_rejection' }
      );
      if (originalHandler) {
        originalHandler(event);
      }
    };

    // Handle uncaught errors
    const originalErrorHandler = ErrorUtils.getGlobalHandler();
    ErrorUtils.setGlobalHandler((error: Error, isFatal?: boolean) => {
      this.captureError(error, { type: 'uncaught_error', isFatal });
      if (originalErrorHandler) {
        originalErrorHandler(error, isFatal);
      }
    });
  }

  /**
   * Capture and report an error
   */
  async captureError(
    error: Error | string,
    extraData: Record<string, any> = {}
  ): Promise<void> {
    if (!this.isEnabled) {
      console.log('[CrashReporting] Disabled - not capturing error');
      return;
    }

    try {
      const errorObj = typeof error === 'string' ? new Error(error) : error;
      
      const report: CrashReport = {
        id: this.generateId(),
        timestamp: new Date().toISOString(),
        error_message: errorObj.message || 'Unknown error',
        error_stack: errorObj.stack || null,
        component_stack: extraData.componentStack || null,
        screen: this.currentScreen,
        user_id: this.userId,
        platform: this.platform,
        app_version: this.appVersion,
        build_number: this.buildNumber,
        device_info: {
          os_version: Platform.Version?.toString() || null,
          device_name: Constants.deviceName || null,
        },
        extra_data: extraData,
      };

      // Try to send immediately
      const sent = await this.sendReport(report);
      
      // If failed, save for later
      if (!sent) {
        await this.saveReportLocally(report);
      }
    } catch (e) {
      console.error('[CrashReporting] Failed to capture error:', e);
    }
  }

  /**
   * Capture a breadcrumb/event for debugging
   */
  async captureBreadcrumb(
    message: string,
    data: Record<string, any> = {}
  ): Promise<void> {
    if (!this.isEnabled) return;

    try {
      await api.post('/api/debug/breadcrumb', {
        timestamp: new Date().toISOString(),
        message,
        screen: this.currentScreen,
        user_id: this.userId,
        platform: this.platform,
        app_version: this.appVersion,
        data,
      });
    } catch (error) {
      // Silently fail - breadcrumbs are non-critical
      console.log('[CrashReporting] Failed to send breadcrumb');
    }
  }

  /**
   * Send a crash report to the backend
   */
  private async sendReport(report: CrashReport): Promise<boolean> {
    try {
      await api.post('/api/debug/crash-report', report);
      console.log('[CrashReporting] Report sent successfully');
      return true;
    } catch (error) {
      console.error('[CrashReporting] Failed to send report:', error);
      return false;
    }
  }

  /**
   * Save a report locally for later sending
   */
  private async saveReportLocally(report: CrashReport): Promise<void> {
    try {
      const existing = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_CRASHES);
      const reports: CrashReport[] = existing ? JSON.parse(existing) : [];
      
      // Keep only last 10 reports
      reports.push(report);
      if (reports.length > 10) {
        reports.shift();
      }
      
      await AsyncStorage.setItem(
        STORAGE_KEYS.PENDING_CRASHES,
        JSON.stringify(reports)
      );
    } catch (error) {
      console.error('[CrashReporting] Failed to save report locally:', error);
    }
  }

  /**
   * Send any pending crash reports
   */
  private async sendPendingReports(): Promise<void> {
    try {
      const existing = await AsyncStorage.getItem(STORAGE_KEYS.PENDING_CRASHES);
      if (!existing) return;

      const reports: CrashReport[] = JSON.parse(existing);
      const remaining: CrashReport[] = [];

      for (const report of reports) {
        const sent = await this.sendReport(report);
        if (!sent) {
          remaining.push(report);
        }
      }

      if (remaining.length > 0) {
        await AsyncStorage.setItem(
          STORAGE_KEYS.PENDING_CRASHES,
          JSON.stringify(remaining)
        );
      } else {
        await AsyncStorage.removeItem(STORAGE_KEYS.PENDING_CRASHES);
      }
    } catch (error) {
      console.error('[CrashReporting] Failed to send pending reports:', error);
    }
  }

  /**
   * Generate a unique ID for crash reports
   */
  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Check if debug mode is currently enabled
   */
  isDebugEnabled(): boolean {
    return this.isEnabled;
  }

  /**
   * Manually enable/disable debug mode (for testing)
   */
  setDebugEnabled(enabled: boolean): void {
    this.isEnabled = enabled;
  }
}

// Export singleton instance
export const crashReporting = new CrashReportingService();

// Export class for testing
export { CrashReportingService };
