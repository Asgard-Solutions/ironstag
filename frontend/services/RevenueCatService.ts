import { Platform } from 'react-native';
import Constants from 'expo-constants';

// Type definitions for RevenueCat
export interface PurchasesPackage {
  identifier: string;
  product: {
    identifier: string;
    priceString: string;
    price: number;
  };
}

export interface CustomerInfo {
  entitlements: {
    active: {
      [key: string]: {
        isActive: boolean;
        expirationDate: string | null;
      };
    };
  };
}

// Product identifiers (same for iOS and Android)
export const PRODUCT_IDS = {
  MONTHLY: 'ironstag_monthly_premium',
  ANNUAL: 'ironstag_annual_premium',
};

// RevenueCat Configuration
const REVENUECAT_IOS_API_KEY = 'sk_mhkZTJXJjpUcNrCYVRyMYAPDOgKgV';
const REVENUECAT_ANDROID_API_KEY = 'goog_MZUtDk1KjnEPjVZDnQWAiYxPQAV';
const ENTITLEMENT_ID = 'master_stag';

/**
 * Check if running in Expo Go (not a native development build)
 */
function isExpoGo(): boolean {
  return Constants.appOwnership === 'expo';
}

/**
 * RevenueCat Service
 * 
 * Automatically detects environment:
 * - Expo Go: Uses mock implementations (IAP not available)
 * - Native build: Uses real RevenueCat SDK
 */
class RevenueCatService {
  private initialized = false;
  private Purchases: any = null;

  /**
   * Check if RevenueCat is available
   * Returns false in Expo Go, true in native builds on iOS/Android
   */
  isAvailable(): boolean {
    if (Platform.OS === 'web') return false;
    if (isExpoGo()) return false;
    return true;
  }

  /**
   * Get the appropriate API key for the current platform
   */
  private getApiKey(): string {
    return Platform.OS === 'ios' ? REVENUECAT_IOS_API_KEY : REVENUECAT_ANDROID_API_KEY;
  }

  /**
   * Initialize RevenueCat SDK
   * In Expo Go, this is a no-op
   */
  async initialize(userId?: string): Promise<void> {
    if (Platform.OS === 'web') {
      console.log('RevenueCat: Not available on web');
      return;
    }

    if (isExpoGo()) {
      console.log('RevenueCat: Running in Expo Go - IAP not available. Create a development build to test IAP.');
      return;
    }

    if (this.initialized) {
      console.log('RevenueCat: Already initialized');
      return;
    }

    try {
      // Dynamically import react-native-purchases only in native builds
      const PurchasesModule = await import('react-native-purchases');
      this.Purchases = PurchasesModule.default;
      
      this.Purchases.setLogLevel(PurchasesModule.LOG_LEVEL.DEBUG);
      
      const apiKey = this.getApiKey();
      
      if (userId) {
        await this.Purchases.configure({ apiKey, appUserID: userId });
      } else {
        await this.Purchases.configure({ apiKey });
      }
      
      this.initialized = true;
      console.log(`RevenueCat: Initialized successfully on ${Platform.OS}`);
    } catch (error) {
      console.error('RevenueCat: Initialization failed', error);
    }
  }

  /**
   * Login user to RevenueCat
   */
  async login(userId: string): Promise<CustomerInfo | null> {
    if (!this.isAvailable() || !this.Purchases) {
      console.log('RevenueCat: Login not available');
      return null;
    }
    
    try {
      const { customerInfo } = await this.Purchases.logIn(userId);
      return customerInfo as CustomerInfo;
    } catch (error) {
      console.error('RevenueCat: Login failed', error);
      throw error;
    }
  }

  /**
   * Logout user from RevenueCat
   */
  async logout(): Promise<void> {
    if (!this.isAvailable() || !this.Purchases) {
      return;
    }
    
    try {
      await this.Purchases.logOut();
      console.log('RevenueCat: Logged out');
    } catch (error) {
      console.error('RevenueCat: Logout failed', error);
    }
  }

  /**
   * Get available subscription offerings
   */
  async getOfferings(): Promise<any | null> {
    if (!this.isAvailable() || !this.Purchases) {
      console.log('RevenueCat: Offerings not available in Expo Go');
      return null;
    }
    
    try {
      const offerings = await this.Purchases.getOfferings();
      return offerings.current;
    } catch (error) {
      console.error('RevenueCat: Failed to get offerings', error);
      return null;
    }
  }

  /**
   * Get available packages (monthly/annual)
   */
  async getPackages(): Promise<PurchasesPackage[]> {
    if (!this.isAvailable() || !this.Purchases) {
      return [];
    }
    
    try {
      const offering = await this.getOfferings();
      return offering?.availablePackages || [];
    } catch (error) {
      console.error('RevenueCat: Failed to get packages', error);
      return [];
    }
  }

  /**
   * Purchase a subscription package
   */
  async purchasePackage(pkg: PurchasesPackage): Promise<CustomerInfo | null> {
    if (!this.isAvailable() || !this.Purchases) {
      console.log('RevenueCat: Purchase not available in Expo Go');
      return null;
    }
    
    try {
      const { customerInfo } = await this.Purchases.purchasePackage(pkg as any);
      return customerInfo as CustomerInfo;
    } catch (error: any) {
      if (error.userCancelled) {
        throw new Error('Purchase cancelled by user');
      }
      console.error('RevenueCat: Purchase failed', error);
      throw error;
    }
  }

  /**
   * Purchase by product ID
   */
  async purchaseProduct(productId: string): Promise<CustomerInfo | null> {
    if (!this.isAvailable() || !this.Purchases) {
      console.log('RevenueCat: Purchase not available in Expo Go');
      return null;
    }
    
    try {
      const packages = await this.getPackages();
      const pkg = packages.find(p => p.product.identifier === productId);
      
      if (!pkg) {
        throw new Error(`Product ${productId} not found`);
      }

      return await this.purchasePackage(pkg);
    } catch (error) {
      console.error('RevenueCat: Purchase product failed', error);
      throw error;
    }
  }

  /**
   * Restore previous purchases
   */
  async restorePurchases(): Promise<CustomerInfo | null> {
    if (!this.isAvailable() || !this.Purchases) {
      console.log('RevenueCat: Restore not available in Expo Go');
      return null;
    }
    
    try {
      const customerInfo = await this.Purchases.restorePurchases();
      console.log('RevenueCat: Purchases restored');
      return customerInfo as CustomerInfo;
    } catch (error) {
      console.error('RevenueCat: Restore failed', error);
      throw error;
    }
  }

  /**
   * Get current customer info
   */
  async getCustomerInfo(): Promise<CustomerInfo | null> {
    if (!this.isAvailable() || !this.Purchases) {
      return null;
    }
    
    try {
      return await this.Purchases.getCustomerInfo() as CustomerInfo;
    } catch (error) {
      console.error('RevenueCat: Failed to get customer info', error);
      return null;
    }
  }

  /**
   * Check if user has active premium subscription
   */
  async isPremium(): Promise<boolean> {
    if (!this.isAvailable() || !this.Purchases) {
      return false;
    }
    
    try {
      const customerInfo = await this.getCustomerInfo();
      if (!customerInfo) return false;

      const entitlement = customerInfo.entitlements.active[ENTITLEMENT_ID];
      return entitlement !== undefined && entitlement.isActive;
    } catch (error) {
      console.error('RevenueCat: Failed to check premium status', error);
      return false;
    }
  }

  /**
   * Get subscription expiration date
   */
  async getExpirationDate(): Promise<Date | null> {
    if (!this.isAvailable() || !this.Purchases) {
      return null;
    }
    
    try {
      const customerInfo = await this.getCustomerInfo();
      if (!customerInfo) return null;

      const entitlement = customerInfo.entitlements.active[ENTITLEMENT_ID];
      if (!entitlement || !entitlement.expirationDate) return null;

      return new Date(entitlement.expirationDate);
    } catch (error) {
      console.error('RevenueCat: Failed to get expiration date', error);
      return null;
    }
  }

  /**
   * Get formatted price for a product
   */
  async getProductPrice(productId: string): Promise<string | null> {
    if (!this.isAvailable() || !this.Purchases) {
      return null;
    }
    
    try {
      const packages = await this.getPackages();
      const pkg = packages.find(p => p.product.identifier === productId);
      return pkg?.product.priceString || null;
    } catch (error) {
      console.error('RevenueCat: Failed to get product price', error);
      return null;
    }
  }

  /**
   * Sync purchases with backend
   */
  async syncWithBackend(backendSyncFn: (isPremium: boolean, expiresAt: Date | null) => Promise<void>): Promise<void> {
    if (!this.isAvailable()) {
      return;
    }
    
    try {
      const isPremium = await this.isPremium();
      const expiresAt = await this.getExpirationDate();
      await backendSyncFn(isPremium, expiresAt);
    } catch (error) {
      console.error('RevenueCat: Backend sync failed', error);
    }
  }
}

export const revenueCatService = new RevenueCatService();
export default revenueCatService;
