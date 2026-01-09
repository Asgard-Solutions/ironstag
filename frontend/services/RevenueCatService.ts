/**
 * RevenueCat Mock Service for Expo Go
 * 
 * This file provides mock implementations for use in Expo Go environment.
 * The real implementation is in RevenueCatService.native.ts which Metro
 * will automatically use for native builds.
 * 
 * In Expo Go, IAP functionality is not available - this mock prevents crashes.
 */

// Type definitions (same as native)
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

/**
 * Mock RevenueCat Service for Expo Go
 * All methods return safe defaults and log that RevenueCat is unavailable
 */
class RevenueCatService {
  /**
   * Always returns false in Expo Go - RevenueCat is not available
   */
  isAvailable(): boolean {
    return false;
  }

  /**
   * No-op in Expo Go
   */
  async initialize(_userId?: string): Promise<void> {
    console.log('RevenueCat: Running in Expo Go - IAP not available');
    return;
  }

  /**
   * No-op in Expo Go
   */
  async login(_userId: string): Promise<CustomerInfo | null> {
    console.log('RevenueCat: Login not available in Expo Go');
    return null;
  }

  /**
   * No-op in Expo Go
   */
  async logout(): Promise<void> {
    console.log('RevenueCat: Logout not available in Expo Go');
    return;
  }

  /**
   * Returns null in Expo Go
   */
  async getOfferings(): Promise<any | null> {
    console.log('RevenueCat: Offerings not available in Expo Go');
    return null;
  }

  /**
   * Returns empty array in Expo Go
   */
  async getPackages(): Promise<PurchasesPackage[]> {
    console.log('RevenueCat: Packages not available in Expo Go');
    return [];
  }

  /**
   * Returns null in Expo Go
   */
  async purchasePackage(_pkg: PurchasesPackage): Promise<CustomerInfo | null> {
    console.log('RevenueCat: Purchase not available in Expo Go');
    return null;
  }

  /**
   * Returns null in Expo Go
   */
  async purchaseProduct(_productId: string): Promise<CustomerInfo | null> {
    console.log('RevenueCat: Purchase not available in Expo Go');
    return null;
  }

  /**
   * Returns null in Expo Go
   */
  async restorePurchases(): Promise<CustomerInfo | null> {
    console.log('RevenueCat: Restore not available in Expo Go');
    return null;
  }

  /**
   * Returns null in Expo Go
   */
  async getCustomerInfo(): Promise<CustomerInfo | null> {
    return null;
  }

  /**
   * Returns false in Expo Go
   */
  async isPremium(): Promise<boolean> {
    return false;
  }

  /**
   * Returns null in Expo Go
   */
  async getExpirationDate(): Promise<Date | null> {
    return null;
  }

  /**
   * Returns null in Expo Go
   */
  async getProductPrice(_productId: string): Promise<string | null> {
    return null;
  }

  /**
   * No-op in Expo Go
   */
  async syncWithBackend(_backendSyncFn: (isPremium: boolean, expiresAt: Date | null) => Promise<void>): Promise<void> {
    console.log('RevenueCat: Sync not available in Expo Go');
    return;
  }
}

export const revenueCatService = new RevenueCatService();
export default revenueCatService;
