import { useState, useEffect, useCallback } from 'react';
import { offlineQueue, QueueStatus, PendingScan } from '../services/OfflineQueueService';

/**
 * React hook for accessing offline queue status and functions
 */
export function useOfflineQueue() {
  const [status, setStatus] = useState<QueueStatus>({
    pendingCount: 0,
    isSyncing: false,
  });
  const [isOnline, setIsOnline] = useState(true);
  const [pendingScans, setPendingScans] = useState<PendingScan[]>([]);

  useEffect(() => {
    // Subscribe to status changes
    const unsubscribe = offlineQueue.subscribe((newStatus) => {
      setStatus(newStatus);
      setIsOnline(offlineQueue.getIsOnline());
    });

    // Load initial pending scans
    loadPendingScans();

    return () => {
      unsubscribe();
    };
  }, []);

  const loadPendingScans = useCallback(async () => {
    const scans = await offlineQueue.getQueue();
    setPendingScans(scans);
  }, []);

  const syncNow = useCallback(async () => {
    const result = await offlineQueue.forceSyncNow();
    await loadPendingScans();
    return result;
  }, [loadPendingScans]);

  const clearQueue = useCallback(async () => {
    await offlineQueue.clearQueue();
    await loadPendingScans();
  }, [loadPendingScans]);

  const removeFromQueue = useCallback(async (scanId: string) => {
    await offlineQueue.removeFromQueue(scanId);
    await loadPendingScans();
  }, [loadPendingScans]);

  return {
    // Status
    pendingCount: status.pendingCount,
    isSyncing: status.isSyncing,
    isOnline,
    lastSyncAttempt: status.lastSyncAttempt,
    lastSyncSuccess: status.lastSyncSuccess,
    
    // Data
    pendingScans,
    
    // Actions
    syncNow,
    clearQueue,
    removeFromQueue,
    refreshQueue: loadPendingScans,
  };
}

export default useOfflineQueue;
