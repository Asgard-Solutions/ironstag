/**
 * In-App Purchase Service for Iron Stag
 * Handles iOS App Store and Google Play purchases
 */
import { Platform } from 'react-native';
import * as ExpoIAP from 'expo-iap';
import api from '../utils/api';

// Product IDs configured in App Store Connect / Google Play Console
export const PRODUCT_IDS = {
  MONTHLY: Platform.select({
    ios: 'master_stag_monthly',
    android: 'master_stag_monthly',
  }) || 'master_stag_monthly',
  ANNUAL: Platform.select({
    ios: 'master_stag_annual', 
    android: 'master_stag_annual',
  }) || 'master_stag_annual',
};

export interface IAPProduct {
  productId: string;
  title: string;
  description: string;
  price: string;
  priceAmountMicros?: string;
  priceCurrencyCode?: string;
  subscriptionPeriod?: string;
}

export interface PurchaseResult {
  success: boolean;
  message: string;
  transactionId?: string;
  expiresAt?: string;
}

class IAPService {
  private isInitialized = false;
  private products: IAPProduct[] = [];

  /**
   * Initialize the IAP connection
   */
  async initialize(): Promise<boolean> {
    try {
      if (this.isInitialized) {
        return true;
      }

      // Connect to the store
      const connected = await ExpoIAP.initConnection();
      console.log('[IAP] Connection initialized:', connected);
      
      if (connected) {
        this.isInitialized = true;
        
        // Load available products
        await this.loadProducts();
        
        // Check for any pending purchases that need to be finished
        await this.checkPendingPurchases();
      }
      
      return connected;
    } catch (error) {
      console.error('[IAP] Initialize error:', error);
      return false;
    }
  }

  /**
   * Load available subscription products from the store
   */
  async loadProducts(): Promise<IAPProduct[]> {
    try {
      const productIds = [PRODUCT_IDS.MONTHLY, PRODUCT_IDS.ANNUAL];
      
      console.log('[IAP] Loading products:', productIds);
      
      const products = await ExpoIAP.getProducts(productIds);
      
      console.log('[IAP] Products loaded:', products);
      
      this.products = products.map(p => ({
        productId: p.productId,
        title: p.title || p.productId,
        description: p.description || '',
        price: p.localizedPrice || p.price || '$0.00',
        priceAmountMicros: p.priceAmountMicros?.toString(),
        priceCurrencyCode: p.priceCurrencyCode,
        subscriptionPeriod: p.subscriptionPeriod,
      }));
      
      return this.products;
    } catch (error) {
      console.error('[IAP] Load products error:', error);
      return [];
    }
  }

  /**
   * Get cached products
   */
  getProducts(): IAPProduct[] {
    return this.products;
  }

  /**
   * Purchase a subscription
   */
  async purchaseSubscription(productId: string): Promise<PurchaseResult> {
    try {
      console.log('[IAP] Initiating purchase for:', productId);
      
      // Request the purchase
      const purchase = await ExpoIAP.requestPurchase({ sku: productId });
      
      console.log('[IAP] Purchase response:', purchase);
      
      if (!purchase) {
        return {
          success: false,
          message: 'Purchase was canceled',
        };
      }

      // Validate with our server
      const validationResult = await this.validatePurchase(purchase);
      
      if (validationResult.success) {
        // Finish the transaction
        await ExpoIAP.finishTransaction({
          purchase,
          isConsumable: false,
        });
      }
      
      return validationResult;
    } catch (error: any) {
      console.error('[IAP] Purchase error:', error);
      
      // Handle user cancellation
      if (error.code === 'E_USER_CANCELLED' || error.message?.includes('cancel')) {
        return {
          success: false,
          message: 'Purchase was canceled',
        };
      }
      
      // Handle already owned
      if (error.code === 'E_ALREADY_OWNED') {
        return {
          success: false,
          message: 'You already own this subscription. Try restoring purchases.',
        };
      }
      
      return {
        success: false,
        message: error.message || 'Purchase failed. Please try again.',
      };
    }
  }

  /**
   * Validate purchase with our backend server
   */
  private async validatePurchase(purchase: any): Promise<PurchaseResult> {
    try {
      const platform = Platform.OS;
      const receiptData = Platform.select({
        ios: purchase.transactionReceipt,
        android: purchase.purchaseToken,
      });
      
      console.log('[IAP] Validating purchase with server...');
      
      const response = await api.post('/subscription/validate-iap', {
        receipt_data: receiptData,
        platform: platform,
        product_id: purchase.productId,
        transaction_id: purchase.transactionId,
      });
      
      console.log('[IAP] Validation response:', response.data);
      
      if (response.data.is_valid) {
        return {
          success: true,
          message: 'Purchase validated successfully!',
          transactionId: response.data.original_transaction_id,
          expiresAt: response.data.expires_at,
        };
      } else {
        return {
          success: false,
          message: response.data.message || 'Purchase validation failed',
        };
      }
    } catch (error: any) {
      console.error('[IAP] Validation error:', error);
      return {
        success: false,
        message: error.response?.data?.detail || 'Server validation failed',
      };
    }
  }

  /**
   * Restore previous purchases
   */
  async restorePurchases(): Promise<PurchaseResult> {
    try {
      console.log('[IAP] Restoring purchases...');
      
      const purchases = await ExpoIAP.getAvailablePurchases();
      
      console.log('[IAP] Available purchases:', purchases);
      
      if (!purchases || purchases.length === 0) {
        return {
          success: false,
          message: 'No previous purchases found',
        };
      }
      
      // Validate each purchase with our server
      for (const purchase of purchases) {
        const validationResult = await this.validatePurchase(purchase);
        
        if (validationResult.success) {
          // Finish the transaction
          await ExpoIAP.finishTransaction({
            purchase,
            isConsumable: false,
          });
          
          return {
            success: true,
            message: 'Your subscription has been restored!',
            transactionId: validationResult.transactionId,
            expiresAt: validationResult.expiresAt,
          };
        }
      }
      
      return {
        success: false,
        message: 'No active subscriptions found to restore',
      };
    } catch (error: any) {
      console.error('[IAP] Restore error:', error);
      return {
        success: false,
        message: error.message || 'Failed to restore purchases',
      };
    }
  }

  /**
   * Check for pending purchases that need to be finished
   */
  private async checkPendingPurchases(): Promise<void> {
    try {
      const purchases = await ExpoIAP.getAvailablePurchases();
      
      for (const purchase of purchases) {
        // Check if this purchase is already validated on our server
        const validationResult = await this.validatePurchase(purchase);
        
        if (validationResult.success) {
          await ExpoIAP.finishTransaction({
            purchase,
            isConsumable: false,
          });
          console.log('[IAP] Finished pending purchase:', purchase.productId);
        }
      }
    } catch (error) {
      console.error('[IAP] Check pending purchases error:', error);
    }
  }

  /**
   * Disconnect from the IAP service
   */
  async disconnect(): Promise<void> {
    try {
      await ExpoIAP.endConnection();
      this.isInitialized = false;
      console.log('[IAP] Disconnected');
    } catch (error) {
      console.error('[IAP] Disconnect error:', error);
    }
  }
}

// Export singleton instance
export const iapService = new IAPService();
export default iapService;
