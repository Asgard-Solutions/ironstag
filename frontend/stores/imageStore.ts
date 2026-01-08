import { create } from 'zustand';
import { LocalImageService, StorageStats } from '../services/LocalImageService';

interface ImageStore {
  // State
  isLoaded: boolean;
  stats: StorageStats;
  cleanupInterval: number;
  
  // Actions
  initialize: () => Promise<void>;
  saveImage: (sourceUri: string) => Promise<string>;
  saveImageFromBase64: (base64Data: string, extension?: string) => Promise<string>;
  getImage: (id: string) => Promise<string | null>;
  getImageUri: (id: string) => Promise<string | null>;
  deleteImage: (id: string) => Promise<boolean>;
  cleanupOldImages: () => Promise<number>;
  clearAllImages: () => Promise<number>;
  refreshStats: () => Promise<void>;
  getCleanupInterval: () => Promise<number>;
  setCleanupInterval: (days: number) => Promise<void>;
  imageExists: (id: string) => Promise<boolean>;
}

export const useImageStore = create<ImageStore>((set, get) => ({
  isLoaded: false,
  stats: {
    totalImages: 0,
    totalSizeBytes: 0,
    totalSizeMB: '0.00',
    oldestImage: null,
  },
  cleanupInterval: 90,

  initialize: async () => {
    try {
      await LocalImageService.initialize();
      const stats = await LocalImageService.getStorageStats();
      const interval = await LocalImageService.getCleanupInterval();
      set({ isLoaded: true, stats, cleanupInterval: interval });
    } catch (error) {
      console.error('Error initializing image store:', error);
      set({ isLoaded: true });
    }
  },

  saveImage: async (sourceUri: string) => {
    const localImageId = await LocalImageService.saveImage(sourceUri);
    // Refresh stats after saving
    const stats = await LocalImageService.getStorageStats();
    set({ stats });
    return localImageId;
  },

  saveImageFromBase64: async (base64Data: string, extension: string = 'jpg') => {
    const localImageId = await LocalImageService.saveImageFromBase64(base64Data, extension);
    // Refresh stats after saving
    const stats = await LocalImageService.getStorageStats();
    set({ stats });
    return localImageId;
  },

  getImage: async (id: string) => {
    return await LocalImageService.getImageAsBase64(id);
  },

  getImageUri: async (id: string) => {
    return await LocalImageService.getImageUri(id);
  },

  deleteImage: async (id: string) => {
    const result = await LocalImageService.deleteImage(id);
    if (result) {
      // Refresh stats after deleting
      const stats = await LocalImageService.getStorageStats();
      set({ stats });
    }
    return result;
  },

  cleanupOldImages: async () => {
    const { cleanupInterval } = get();
    const deletedCount = await LocalImageService.cleanupOldImages(cleanupInterval);
    // Refresh stats after cleanup
    const stats = await LocalImageService.getStorageStats();
    set({ stats });
    return deletedCount;
  },

  clearAllImages: async () => {
    const deletedCount = await LocalImageService.clearAllImages();
    // Reset stats after clearing
    set({
      stats: {
        totalImages: 0,
        totalSizeBytes: 0,
        totalSizeMB: '0.00',
        oldestImage: null,
      },
    });
    return deletedCount;
  },

  refreshStats: async () => {
    const stats = await LocalImageService.getStorageStats();
    set({ stats });
  },

  getCleanupInterval: async () => {
    const interval = await LocalImageService.getCleanupInterval();
    set({ cleanupInterval: interval });
    return interval;
  },

  setCleanupInterval: async (days: number) => {
    await LocalImageService.setCleanupInterval(days);
    set({ cleanupInterval: days });
  },

  imageExists: async (id: string) => {
    return await LocalImageService.imageExists(id);
  },
}));
