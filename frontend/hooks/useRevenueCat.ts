/**
 * React hook for RevenueCat purchases
 */
import { useState, useEffect, useCallback } from 'react';
import { Platform } from 'react-native';
import { PurchasesPackage } from 'react-native-purchases';
import { revenueCatService, PurchaseResult } from '../services/RevenueCatService';
import { useAuthStore } from '../stores/authStore';

export interface UseRevenueCatReturn {
  isInitialized: boolean;
  isLoading: boolean;
  isPremium: boolean;
  packages: PurchasesPackage[];
  monthlyPackage: PurchasesPackage | null;
  annualPackage: PurchasesPackage | null;
  error: string | null;
  purchaseMonthly: () => Promise<PurchaseResult>;
  purchaseAnnual: () => Promise<PurchaseResult>;
  purchasePackage: (pkg: PurchasesPackage) => Promise<PurchaseResult>;
  restorePurchases: () => Promise<PurchaseResult>;
  refreshStatus: () => Promise<void>;
}

export function useRevenueCat(): UseRevenueCatReturn {
  const { user, updateUser } = useAuthStore();
  const [isInitialized, setIsInitialized] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isPremium, setIsPremium] = useState(false);
  const [packages, setPackages] = useState<PurchasesPackage[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Initialize RevenueCat on mount
  useEffect(() => {
    const init = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Initialize with user ID if available
        const userId = user?.id;
        const initialized = await revenueCatService.initialize(userId);
        
        if (initialized) {
          setIsInitialized(true);
          
          // Login if user is authenticated
          if (userId) {
            await revenueCatService.login(userId);
          }
          
          // Load offerings
          await loadOfferings();
          
          // Check premium status
          await checkPremiumStatus();
        } else {
          // RevenueCat may not work in web/dev environment
          if (Platform.OS === 'web') {
            console.log('[useRevenueCat] Web platform - RevenueCat not available');
          } else {
            setError('Failed to initialize purchases');
          }
        }
      } catch (err: any) {
        console.error('[useRevenueCat] Init error:', err);
        setError(err.message || 'Failed to initialize purchases');
      } finally {
        setIsLoading(false);
      }
    };

    init();
  }, [user?.id]);

  // Load available offerings
  const loadOfferings = async () => {
    try {
      const offering = await revenueCatService.getOfferings();
      if (offering) {
        const pkgs = offering.availablePackages ?? [];
        setPackages(pkgs);

        if (pkgs.length === 0 && Platform.OS !== 'web') {
          setError(
            'No purchase options available right now. Please try again in a moment.'
          );
        }
      } else {
        setPackages([]);
        if (Platform.OS !== 'web') {
          setError(
            'Unable to load purchase options. Please try again. (If this persists, check RevenueCat offering configuration.)'
          );
        }
      }
    } catch (err: any) {
      console.error('[useRevenueCat] Load offerings error:', err);
      if (Platform.OS !== 'web') {
        setError(err?.message || 'Failed to load purchase options');
      }
    }
  };

  // Check premium status
  const checkPremiumStatus = async () => {
    try {
      const premium = await revenueCatService.checkPremiumStatus();
      setIsPremium(premium);
      
      // Sync with local user state
      if (premium && user?.subscription_tier !== 'master_stag') {
        updateUser({ subscription_tier: 'master_stag', scans_remaining: -1 });
      }
    } catch (err) {
      console.error('[useRevenueCat] Check premium error:', err);
    }
  };

  // Find monthly package
  const monthlyPackage = packages.find(
    pkg => pkg.packageType === 'MONTHLY' || pkg.identifier.toLowerCase().includes('monthly')
  ) || null;

  // Find annual package
  const annualPackage = packages.find(
    pkg => pkg.packageType === 'ANNUAL' || pkg.identifier.toLowerCase().includes('annual')
  ) || null;

  // Purchase a specific package
  const purchasePackage = useCallback(async (pkg: PurchasesPackage): Promise<PurchaseResult> => {
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await revenueCatService.purchasePackage(pkg);
      
      if (result.success && result.customerInfo) {
        setIsPremium(true);
        
        // Update local user state
        updateUser({ 
          subscription_tier: 'master_stag', 
          scans_remaining: -1 
        });
        
        // Sync with backend
        if (user?.id) {
          await revenueCatService.syncWithBackend(result.customerInfo);
        }
      } else if (result.message !== 'Purchase was cancelled') {
        setError(result.message);
      }
      
      return result;
    } catch (err: any) {
      const message = err.message || 'Purchase failed';
      setError(message);
      return { success: false, message };
    } finally {
      setIsLoading(false);
    }
  }, [user?.id, updateUser]);

  // Purchase monthly
  const purchaseMonthly = useCallback(async (): Promise<PurchaseResult> => {
    if (!monthlyPackage) {
      return { success: false, message: 'Monthly package not available' };
    }
    return purchasePackage(monthlyPackage);
  }, [monthlyPackage, purchasePackage]);

  // Purchase annual
  const purchaseAnnual = useCallback(async (): Promise<PurchaseResult> => {
    if (!annualPackage) {
      return { success: false, message: 'Annual package not available' };
    }
    return purchasePackage(annualPackage);
  }, [annualPackage, purchasePackage]);

  // Restore purchases
  const restorePurchases = useCallback(async (): Promise<PurchaseResult> => {
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await revenueCatService.restorePurchases();
      
      if (result.success && result.customerInfo) {
        setIsPremium(true);
        
        // Update local user state
        updateUser({ 
          subscription_tier: 'master_stag', 
          scans_remaining: -1 
        });
        
        // Sync with backend
        if (user?.id) {
          await revenueCatService.syncWithBackend(result.customerInfo);
        }
      } else {
        setError(result.message);
      }
      
      return result;
    } catch (err: any) {
      const message = err.message || 'Restore failed';
      setError(message);
      return { success: false, message };
    } finally {
      setIsLoading(false);
    }
  }, [user?.id, updateUser]);

  // Refresh status
  const refreshStatus = useCallback(async () => {
    await checkPremiumStatus();
    await loadOfferings();
  }, []);

  return {
    isInitialized,
    isLoading,
    isPremium,
    packages,
    monthlyPackage,
    annualPackage,
    error,
    purchaseMonthly,
    purchaseAnnual,
    purchasePackage,
    restorePurchases,
    refreshStatus,
  };
}

export default useRevenueCat;
