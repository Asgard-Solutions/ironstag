import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo, { NetInfoState } from '@react-native-community/netinfo';
import { scanAPI } from '../utils/api';

const OFFLINE_QUEUE_KEY = 'ironstag_offline_queue';
const QUEUE_STATUS_KEY = 'ironstag_queue_status';

export interface PendingScan {
  id: string;
  image_base64: string;
  local_image_id: string;
  notes?: string;
  state?: string;  // Hunting location state
  created_at: string;
  retryCount: number;
  lastError?: string;
}

export interface QueueStatus {
  pendingCount: number;
  isSyncing: boolean;
  lastSyncAttempt?: string;
  lastSyncSuccess?: string;
}

type QueueChangeCallback = (status: QueueStatus) => void;

class OfflineQueueService {
  private isOnline: boolean = true;
  private isSyncing: boolean = false;
  private listeners: Set<QueueChangeCallback> = new Set();
  private unsubscribeNetInfo: (() => void) | null = null;

  /**
   * Initialize the offline queue service
   * Call this once when the app starts
   */
  async initialize(): Promise<void> {
    // Subscribe to network state changes
    this.unsubscribeNetInfo = NetInfo.addEventListener((state: NetInfoState) => {
      const wasOnline = this.isOnline;
      this.isOnline = state.isConnected ?? false;
      
      console.log(`[OfflineQueue] Network status changed: ${this.isOnline ? 'online' : 'offline'}`);
      
      // If we just came online, try to sync
      if (!wasOnline && this.isOnline) {
        console.log('[OfflineQueue] Back online, attempting sync...');
        this.syncPendingScans();
      }
    });

    // Check initial network state
    const state = await NetInfo.fetch();
    this.isOnline = state.isConnected ?? false;
    console.log(`[OfflineQueue] Initial network status: ${this.isOnline ? 'online' : 'offline'}`);

    // If online on init, try to sync any pending scans from previous sessions
    if (this.isOnline) {
      const queue = await this.getQueue();
      if (queue.length > 0) {
        console.log(`[OfflineQueue] Found ${queue.length} pending scans, syncing...`);
        this.syncPendingScans();
      }
    }
  }

  /**
   * Clean up listeners when done
   */
  cleanup(): void {
    if (this.unsubscribeNetInfo) {
      this.unsubscribeNetInfo();
      this.unsubscribeNetInfo = null;
    }
    this.listeners.clear();
  }

  /**
   * Check if currently online
   */
  getIsOnline(): boolean {
    return this.isOnline;
  }

  /**
   * Subscribe to queue status changes
   */
  subscribe(callback: QueueChangeCallback): () => void {
    this.listeners.add(callback);
    // Immediately notify with current status
    this.getStatus().then(callback);
    return () => this.listeners.delete(callback);
  }

  /**
   * Notify all listeners of status change
   */
  private async notifyListeners(): Promise<void> {
    const status = await this.getStatus();
    this.listeners.forEach(callback => callback(status));
  }

  /**
   * Get current queue status
   */
  async getStatus(): Promise<QueueStatus> {
    const queue = await this.getQueue();
    const statusStr = await AsyncStorage.getItem(QUEUE_STATUS_KEY);
    const savedStatus = statusStr ? JSON.parse(statusStr) : {};
    
    return {
      pendingCount: queue.length,
      isSyncing: this.isSyncing,
      lastSyncAttempt: savedStatus.lastSyncAttempt,
      lastSyncSuccess: savedStatus.lastSyncSuccess,
    };
  }

  /**
   * Get all pending scans
   */
  async getQueue(): Promise<PendingScan[]> {
    try {
      const queueStr = await AsyncStorage.getItem(OFFLINE_QUEUE_KEY);
      return queueStr ? JSON.parse(queueStr) : [];
    } catch (error) {
      console.error('[OfflineQueue] Error reading queue:', error);
      return [];
    }
  }

  /**
   * Add a scan to the offline queue
   */
  async addToQueue(scan: Omit<PendingScan, 'id' | 'created_at' | 'retryCount'>): Promise<PendingScan> {
    const pendingScan: PendingScan = {
      ...scan,
      id: `pending_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      created_at: new Date().toISOString(),
      retryCount: 0,
    };

    const queue = await this.getQueue();
    queue.push(pendingScan);
    await AsyncStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
    
    console.log(`[OfflineQueue] Added scan to queue, total pending: ${queue.length}`);
    await this.notifyListeners();
    
    return pendingScan;
  }

  /**
   * Remove a scan from the queue
   */
  async removeFromQueue(scanId: string): Promise<void> {
    const queue = await this.getQueue();
    const filtered = queue.filter(s => s.id !== scanId);
    await AsyncStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(filtered));
    await this.notifyListeners();
  }

  /**
   * Update a scan in the queue (e.g., increment retry count)
   */
  private async updateInQueue(scanId: string, updates: Partial<PendingScan>): Promise<void> {
    const queue = await this.getQueue();
    const index = queue.findIndex(s => s.id === scanId);
    if (index !== -1) {
      queue[index] = { ...queue[index], ...updates };
      await AsyncStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
    }
  }

  /**
   * Clear the entire queue
   */
  async clearQueue(): Promise<void> {
    await AsyncStorage.removeItem(OFFLINE_QUEUE_KEY);
    await this.notifyListeners();
  }

  /**
   * Attempt to submit a scan to the server
   * Returns true if successful, false if should retry
   */
  private async submitScan(scan: PendingScan): Promise<{ success: boolean; error?: string; scanId?: string }> {
    try {
      const response = await scanAPI.analyzeDeer({
        image_base64: scan.image_base64,
        local_image_id: scan.local_image_id,
        notes: scan.notes,
      });
      
      return { success: true, scanId: response.data.id };
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
      
      // Check if it's a permanent error (don't retry)
      if (error.response?.status === 400 || error.response?.status === 401) {
        return { success: false, error: `Permanent error: ${errorMessage}` };
      }
      
      // Temporary error (retry later)
      return { success: false, error: errorMessage };
    }
  }

  /**
   * Sync all pending scans with the server
   */
  async syncPendingScans(): Promise<{ synced: number; failed: number }> {
    if (this.isSyncing) {
      console.log('[OfflineQueue] Sync already in progress, skipping...');
      return { synced: 0, failed: 0 };
    }

    if (!this.isOnline) {
      console.log('[OfflineQueue] Offline, cannot sync');
      return { synced: 0, failed: 0 };
    }

    this.isSyncing = true;
    await this.notifyListeners();

    const queue = await this.getQueue();
    if (queue.length === 0) {
      this.isSyncing = false;
      await this.notifyListeners();
      return { synced: 0, failed: 0 };
    }

    console.log(`[OfflineQueue] Starting sync of ${queue.length} scans...`);

    let synced = 0;
    let failed = 0;
    const MAX_RETRIES = 3;

    // Update last sync attempt
    await AsyncStorage.setItem(QUEUE_STATUS_KEY, JSON.stringify({
      lastSyncAttempt: new Date().toISOString(),
    }));

    for (const scan of queue) {
      // Check if still online
      const state = await NetInfo.fetch();
      if (!state.isConnected) {
        console.log('[OfflineQueue] Lost connection during sync, stopping...');
        break;
      }

      console.log(`[OfflineQueue] Syncing scan ${scan.id} (attempt ${scan.retryCount + 1})...`);
      
      const result = await this.submitScan(scan);
      
      if (result.success) {
        await this.removeFromQueue(scan.id);
        synced++;
        console.log(`[OfflineQueue] Scan ${scan.id} synced successfully -> ${result.scanId}`);
      } else {
        const newRetryCount = scan.retryCount + 1;
        
        if (newRetryCount >= MAX_RETRIES || result.error?.startsWith('Permanent')) {
          // Max retries reached or permanent error, remove from queue
          await this.removeFromQueue(scan.id);
          failed++;
          console.log(`[OfflineQueue] Scan ${scan.id} failed permanently: ${result.error}`);
        } else {
          // Update retry count for next attempt
          await this.updateInQueue(scan.id, { 
            retryCount: newRetryCount,
            lastError: result.error,
          });
          console.log(`[OfflineQueue] Scan ${scan.id} failed, will retry later: ${result.error}`);
        }
      }

      // Small delay between requests to avoid overwhelming the server
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    // Update last sync success if any synced
    if (synced > 0) {
      const statusStr = await AsyncStorage.getItem(QUEUE_STATUS_KEY);
      const status = statusStr ? JSON.parse(statusStr) : {};
      await AsyncStorage.setItem(QUEUE_STATUS_KEY, JSON.stringify({
        ...status,
        lastSyncSuccess: new Date().toISOString(),
      }));
    }

    this.isSyncing = false;
    await this.notifyListeners();

    console.log(`[OfflineQueue] Sync complete: ${synced} synced, ${failed} failed`);
    return { synced, failed };
  }

  /**
   * Force a sync attempt (user-initiated)
   */
  async forceSyncNow(): Promise<{ synced: number; failed: number }> {
    // Refresh network status
    const state = await NetInfo.fetch();
    this.isOnline = state.isConnected ?? false;
    
    if (!this.isOnline) {
      return { synced: 0, failed: 0 };
    }
    
    return this.syncPendingScans();
  }
}

// Export singleton instance
export const offlineQueue = new OfflineQueueService();
export default offlineQueue;
