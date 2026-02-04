/**
 * React hook for In-App Purchases
 */
import { useState, useEffect, useCallback } from 'react';
import { Platform } from 'react-native';
import { iapService, IAPProduct, PurchaseResult, PRODUCT_IDS } from '../services/IAPService';

export interface UseIAPReturn {
  isInitialized: boolean;
  isLoading: boolean;
  products: IAPProduct[];
  monthlyProduct: IAPProduct | null;
  annualProduct: IAPProduct | null;
  error: string | null;
  purchaseMonthly: () => Promise<PurchaseResult>;
  purchaseAnnual: () => Promise<PurchaseResult>;
  restorePurchases: () => Promise<PurchaseResult>;
}

export function useIAP(): UseIAPReturn {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [products, setProducts] = useState<IAPProduct[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Initialize IAP on mount
  useEffect(() => {
    const init = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        const connected = await iapService.initialize();
        
        if (connected) {
          setIsInitialized(true);
          const loadedProducts = await iapService.loadProducts();
          setProducts(loadedProducts);
          
          if (loadedProducts.length === 0) {
            console.log('[useIAP] No products loaded - this is normal in development/web');
          }
        } else {
          // In development or web, IAP won't work - this is expected
          if (Platform.OS === 'web') {
            console.log('[useIAP] Web platform - IAP not available');
          } else {
            setError('Failed to connect to app store');
          }
        }
      } catch (err: any) {
        console.error('[useIAP] Init error:', err);
        setError(err.message || 'Failed to initialize purchases');
      } finally {
        setIsLoading(false);
      }
    };

    init();

    // Cleanup on unmount
    return () => {
      iapService.disconnect();
    };
  }, []);

  // Find specific products
  const monthlyProduct = products.find(p => p.productId === PRODUCT_IDS.MONTHLY) || null;
  const annualProduct = products.find(p => p.productId === PRODUCT_IDS.ANNUAL) || null;

  // Purchase monthly subscription
  const purchaseMonthly = useCallback(async (): Promise<PurchaseResult> => {
    if (!PRODUCT_IDS.MONTHLY) {
      return { success: false, message: 'Monthly product not configured' };
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await iapService.purchaseSubscription(PRODUCT_IDS.MONTHLY);
      
      if (!result.success && result.message !== 'Purchase was canceled') {
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
  }, []);

  // Purchase annual subscription
  const purchaseAnnual = useCallback(async (): Promise<PurchaseResult> => {
    if (!PRODUCT_IDS.ANNUAL) {
      return { success: false, message: 'Annual product not configured' };
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await iapService.purchaseSubscription(PRODUCT_IDS.ANNUAL);
      
      if (!result.success && result.message !== 'Purchase was canceled') {
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
  }, []);

  // Restore purchases
  const restorePurchases = useCallback(async (): Promise<PurchaseResult> => {
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await iapService.restorePurchases();
      
      if (!result.success) {
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
  }, []);

  return {
    isInitialized,
    isLoading,
    products,
    monthlyProduct,
    annualProduct,
    error,
    purchaseMonthly,
    purchaseAnnual,
    restorePurchases,
  };
}

export default useIAP;
