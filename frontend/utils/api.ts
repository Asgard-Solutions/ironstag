import axios from 'axios';
import { useAuthStore } from '../stores/authStore';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: (data: { email: string; password: string; name: string; first_name?: string; last_name?: string; username?: string }) =>
    api.post('/auth/register', data),

  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),

  appleSignIn: (data: { 
    identity_token: string; 
    authorization_code: string; 
    user: string; 
    email?: string; 
    full_name?: string; 
  }) => api.post('/auth/apple', data),

  getMe: () => api.get('/auth/me'),

  updateProfile: (data: { 
    name?: string; 
    username?: string;
    email?: string;
    current_password?: string;
    new_password?: string;
  }) => api.put('/auth/profile', data),

  acceptDisclaimer: (accepted: boolean) =>
    api.post('/auth/accept-disclaimer', { accepted }),

  requestPasswordReset: (email: string) =>
    api.post('/auth/password-reset/request', { email }),

  verifyPasswordReset: (data: { email: string; code: string; new_password: string }) =>
    api.post('/auth/password-reset/verify', data),
};

// Scan API
export const scanAPI = {
  analyzeDeer: (data: { image_base64: string; local_image_id: string; notes?: string }) =>
    api.post('/analyze-deer', data),

  getScans: (params?: { deer_type?: string; deer_sex?: string; recommendation?: string; limit?: number; skip?: number }) =>
    api.get('/scans', { params }),

  getScan: (id: string) => api.get(`/scans/${id}`),

  updateScan: (id: string, data: { notes?: string }) =>
    api.put(`/scans/${id}`, data),

  deleteScan: (id: string) => api.delete(`/scans/${id}`),

  getStats: () => api.get('/scans/stats/summary'),
};

// Subscription API
export const subscriptionAPI = {
  getStatus: () => api.get('/subscription/status'),

  checkEligibility: () => api.get('/subscription/scan-eligibility'),

  createCheckout: (plan: 'monthly' | 'annual' = 'monthly') => 
    api.post('/subscription/create-checkout', { plan }),

  getPortalUrl: () => api.post('/subscription/portal'),

  cancelSubscription: () => api.post('/subscription/cancel'),

  verifyRevenueCat: () => api.post('/subscription/verify-revenuecat'),
};

// Learn API
export const learnAPI = {
  getContent: () => api.get('/learn/content'),
};

export default api;
