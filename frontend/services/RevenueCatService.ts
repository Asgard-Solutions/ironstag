/**
 * RevenueCat Service for Iron Stag
 * Handles iOS App Store and Google Play purchases via RevenueCat
 */
import { Platform } from 'react-native';
import Purchases, { 
  PurchasesPackage, 
  CustomerInfo,
  PurchasesOffering,
  LOG_LEVEL,
} from 'react-native-purchases';

// RevenueCat API Keys - from RevenueCat Dashboard > API Keys
const REVENUECAT_API_KEYS = {
  ios: 'appl_eSwYrXwjGuDNJWReWNrIvMARzFc', // Iron Stag (App Store)
  android: 'goog_MZUtDk1KjnEPjVzDNqWAiYxPQAV', // Iron Stag (Play Store)
};

// Entitlement ID from RevenueCat (matches your "premium" entitlement)
export const ENTITLEMENT_ID = 'premium';

export interface RevenueCatProduct {
  identifier: string;
  title: string;
  description: string;
  priceString: string;
  price: number;
  currencyCode: string;
  packageType: string;
}

export interface PurchaseResult {
  success: boolean;
  message: string;
  customerInfo?: CustomerInfo;
}

class RevenueCatService {
  private isInitialized = false;

  /**
   * Initialize RevenueCat SDK
   */
  async initialize(userId?: string): Promise<boolean> {
    try {
      if (this.isInitialized) {
        console.log('[RevenueCat] Already initialized');
        return true;
      }

      // Get the appropriate API key for the platform
      const apiKey = Platform.select({
        ios: REVENUECAT_API_KEYS.ios,
        android: REVENUECAT_API_KEYS.android,
        default: REVENUECAT_API_KEYS.android,
      });

      if (!apiKey || apiKey.includes('YOUR_')) {
        console.warn('[RevenueCat] API key not configured for this platform');
        return false;
      }

      // Enable debug logs in development
      if (__DEV__) {
        Purchases.setLogLevel(LOG_LEVEL.DEBUG);
      }

      // Configure RevenueCat
      await Purchases.configure({
        apiKey,
        appUserID: userId, // Optional: link to your user ID
      });

      this.isInitialized = true;
      console.log('[RevenueCat] Initialized successfully');
      
      return true;
    } catch (error) {
      console.error('[RevenueCat] Initialize error:', error);
      return false;
    }
  }

  /**
   * Login user to RevenueCat (call after user authenticates)
   */
  async login(userId: string): Promise<CustomerInfo | null> {
    try {
      const { customerInfo } = await Purchases.logIn(userId);
      console.log('[RevenueCat] User logged in:', userId);
      return customerInfo;
    } catch (error) {
      console.error('[RevenueCat] Login error:', error);
      return null;
    }
  }

  /**
   * Logout user from RevenueCat
   */
  async logout(): Promise<void> {
    try {
      await Purchases.logOut();
      console.log('[RevenueCat] User logged out');
    } catch (error) {
      console.error('[RevenueCat] Logout error:', error);
    }
  }

  /**
   * Get available offerings (subscription packages)
   */
  async getOfferings(): Promise<PurchasesOffering | null> {
    try {
      const offerings = await Purchases.getOfferings();
      
      if (offerings.current) {
        console.log('[RevenueCat] Current offering:', offerings.current.identifier);
        return offerings.current;
      }
      
      console.log('[RevenueCat] No current offering available');
      return null;
    } catch (error) {
      console.error('[RevenueCat] Get offerings error:', error);
      return null;
    }
  }

  /**
   * Get available packages formatted for UI
   */
  async getPackages(): Promise<RevenueCatProduct[]> {
    try {
      const offering = await this.getOfferings();
      
      if (!offering) {
        return [];
      }

      return offering.availablePackages.map(pkg => ({
        identifier: pkg.identifier,
        title: pkg.product.title,
        description: pkg.product.description,
        priceString: pkg.product.priceString,
        price: pkg.product.price,
        currencyCode: pkg.product.currencyCode,
        packageType: pkg.packageType,
      }));
    } catch (error) {
      console.error('[RevenueCat] Get packages error:', error);
      return [];
    }
  }

  /**
   * Purchase a package
   */
  async purchasePackage(pkg: PurchasesPackage): Promise<PurchaseResult> {
    try {
      console.log('[RevenueCat] Purchasing package:', pkg.identifier);
      
      const { customerInfo } = await Purchases.purchasePackage(pkg);
      
      // Check if the purchase granted the premium entitlement
      const isPremium = customerInfo.entitlements.active[ENTITLEMENT_ID] !== undefined;
      
      if (isPremium) {
        return {
          success: true,
          message: 'Purchase successful! You now have premium access.',
          customerInfo,
        };
      } else {
        return {
          success: false,
          message: 'Purchase completed but entitlement not found.',
          customerInfo,
        };
      }
    } catch (error: any) {
      console.error('[RevenueCat] Purchase error:', error);
      
      // Handle user cancellation
      if (error.userCancelled) {
        return {
          success: false,
          message: 'Purchase was cancelled',
        };
      }
      
      return {
        success: false,
        message: error.message || 'Purchase failed. Please try again.',
      };
    }
  }

  /**
   * Restore previous purchases
   */
  async restorePurchases(): Promise<PurchaseResult> {
    try {
      console.log('[RevenueCat] Restoring purchases...');
      
      const customerInfo = await Purchases.restorePurchases();
      
      const isPremium = customerInfo.entitlements.active[ENTITLEMENT_ID] !== undefined;
      
      if (isPremium) {
        return {
          success: true,
          message: 'Purchases restored! You have premium access.',
          customerInfo,
        };
      } else {
        return {
          success: false,
          message: 'No previous purchases found.',
          customerInfo,
        };
      }
    } catch (error: any) {
      console.error('[RevenueCat] Restore error:', error);
      return {
        success: false,
        message: error.message || 'Failed to restore purchases.',
      };
    }
  }

  /**
   * Check if user has premium entitlement
   */
  async checkPremiumStatus(): Promise<boolean> {
    try {
      const customerInfo = await Purchases.getCustomerInfo();
      return customerInfo.entitlements.active[ENTITLEMENT_ID] !== undefined;
    } catch (error) {
      console.error('[RevenueCat] Check premium error:', error);
      return false;
    }
  }

  /**
   * Get current customer info
   */
  async getCustomerInfo(): Promise<CustomerInfo | null> {
    try {
      return await Purchases.getCustomerInfo();
    } catch (error) {
      console.error('[RevenueCat] Get customer info error:', error);
      return null;
    }
  }

  /**
   * Sync purchases with our backend
   */
  async syncWithBackend(userId: string, customerInfo: CustomerInfo): Promise<boolean> {
    try {
      const isPremium = customerInfo.entitlements.active[ENTITLEMENT_ID] !== undefined;
      const entitlement = customerInfo.entitlements.active[ENTITLEMENT_ID];
      
      // Call our backend to update subscription status
      const response = await fetch('/api/subscription/sync-revenuecat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          is_premium: isPremium,
          expires_at: entitlement?.expirationDate,
          product_id: entitlement?.productIdentifier,
          original_purchase_date: entitlement?.originalPurchaseDate,
        }),
      });
      
      return response.ok;
    } catch (error) {
      console.error('[RevenueCat] Sync with backend error:', error);
      return false;
    }
  }
}

// Export singleton instance
export const revenueCatService = new RevenueCatService();
export default revenueCatService;
