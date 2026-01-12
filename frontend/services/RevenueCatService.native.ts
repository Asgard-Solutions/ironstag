import { Platform } from 'react-native';
import Purchases, { LOG_LEVEL, PurchasesPackage, CustomerInfo } from 'react-native-purchases';

// Re-export types for convenience
export type { PurchasesPackage, CustomerInfo };

// RevenueCat Configuration - Platform-specific API keys
const REVENUECAT_IOS_API_KEY = 'sk_mhkZTJXJjpUcNrCYVRyMYAPDOgKgV';
const REVENUECAT_ANDROID_API_KEY = 'goog_MZUtDk1KjnEPjVZDnQWAiYxPQAV';
const ENTITLEMENT_ID = 'master_stag';

// Product identifiers (same for iOS and Android)
export const PRODUCT_IDS = {
  MONTHLY: 'ironstag_monthly_premium',
  ANNUAL: 'ironstag_annual_premium',
};

class RevenueCatService {
  private initialized = false;

  /**
   * Get the appropriate API key for the current platform
   */
  private getApiKey(): string {
    return Platform.OS === 'ios' ? REVENUECAT_IOS_API_KEY : REVENUECAT_ANDROID_API_KEY;
  }

  /**
   * Check if RevenueCat is available (always true in native builds)
   */
  isAvailable(): boolean {
    return Platform.OS === 'ios' || Platform.OS === 'android';
  }

  /**
   * Initialize RevenueCat SDK - Works on both iOS and Android
   */
  async initialize(userId?: string): Promise<void> {
    if (Platform.OS === 'web') {
      console.log('RevenueCat: Not available on web');
      return;
    }

    if (this.initialized) {
      console.log('RevenueCat: Already initialized');
      return;
    }

    try {
      Purchases.setLogLevel(LOG_LEVEL.DEBUG);
      
      const apiKey = this.getApiKey();
      
      if (userId) {
        await Purchases.configure({ apiKey, appUserID: userId });
      } else {
        await Purchases.configure({ apiKey });
      }
      
      this.initialized = true;
      console.log(`RevenueCat: Initialized successfully on ${Platform.OS}`);
    } catch (error) {
      console.error('RevenueCat: Initialization failed', error);
      // Don't throw - allow app to continue without RevenueCat
    }
  }

  /**
   * Login user to RevenueCat
   */
  async login(userId: string): Promise<CustomerInfo | null> {
    try {
      const { customerInfo } = await Purchases.logIn(userId);
      return customerInfo;
    } catch (error) {
      console.error('RevenueCat: Login failed', error);
      throw error;
    }
  }

  /**
   * Logout user from RevenueCat
   */
  async logout(): Promise<void> {
    try {
      await Purchases.logOut();
      console.log('RevenueCat: Logged out');
    } catch (error) {
      console.error('RevenueCat: Logout failed', error);
    }
  }

  /**
   * Get available subscription offerings
   */
  async getOfferings(): Promise<any | null> {
    try {
      const offerings = await Purchases.getOfferings();
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
    try {
      const { customerInfo } = await Purchases.purchasePackage(pkg);
      return customerInfo;
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
    try {
      const customerInfo = await Purchases.restorePurchases();
      console.log('RevenueCat: Purchases restored');
      return customerInfo;
    } catch (error) {
      console.error('RevenueCat: Restore failed', error);
      throw error;
    }
  }

  /**
   * Get current customer info
   */
  async getCustomerInfo(): Promise<CustomerInfo | null> {
    try {
      return await Purchases.getCustomerInfo();
    } catch (error) {
      console.error('RevenueCat: Failed to get customer info', error);
      return null;
    }
  }

  /**
   * Check if user has active premium subscription
   */
  async isPremium(): Promise<boolean> {
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
