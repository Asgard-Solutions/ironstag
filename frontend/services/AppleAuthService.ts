import { Platform } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';

export interface AppleAuthCredentials {
  identityToken: string;
  authorizationCode: string;
  user: string;
  email?: string | null;
  fullName?: {
    givenName?: string | null;
    familyName?: string | null;
  } | null;
}

class AppleAuthService {
  /**
   * Check if Sign in with Apple is available
   */
  async isAvailable(): Promise<boolean> {
    if (Platform.OS !== 'ios') {
      return false;
    }

    try {
      return await AppleAuthentication.isAvailableAsync();
    } catch (error) {
      console.error('AppleAuth: Failed to check availability', error);
      return false;
    }
  }

  /**
   * Sign in with Apple
   */
  async signIn(): Promise<AppleAuthCredentials> {
    if (Platform.OS !== 'ios') {
      throw new Error('Sign in with Apple is only available on iOS');
    }

    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });

      if (!credential.identityToken || !credential.authorizationCode) {
        throw new Error('Invalid Apple authentication response');
      }

      return {
        identityToken: credential.identityToken,
        authorizationCode: credential.authorizationCode,
        user: credential.user,
        email: credential.email,
        fullName: credential.fullName,
      };
    } catch (error: any) {
      if (error.code === 'ERR_REQUEST_CANCELED') {
        throw new Error('Sign in cancelled');
      }
      console.error('AppleAuth: Sign in failed', error);
      throw error;
    }
  }

  /**
   * Get credential state for a user
   */
  async getCredentialState(userId: string): Promise<AppleAuthentication.AppleAuthenticationCredentialState> {
    if (Platform.OS !== 'ios') {
      throw new Error('Sign in with Apple is only available on iOS');
    }

    try {
      return await AppleAuthentication.getCredentialStateAsync(userId);
    } catch (error) {
      console.error('AppleAuth: Failed to get credential state', error);
      throw error;
    }
  }

  /**
   * Check if user's Apple credentials are still valid
   */
  async isCredentialValid(userId: string): Promise<boolean> {
    try {
      const state = await this.getCredentialState(userId);
      return state === AppleAuthentication.AppleAuthenticationCredentialState.AUTHORIZED;
    } catch (error) {
      return false;
    }
  }
}

export const appleAuthService = new AppleAuthService();
export default appleAuthService;
