import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as FileSystem from 'expo-file-system';
import { Platform } from 'react-native';

interface ImageEntry {
  id: string;
  base64: string;
  createdAt: string;
}

interface ImageStore {
  images: Record<string, ImageEntry>;
  isLoaded: boolean;
  saveImage: (id: string, base64: string) => Promise<void>;
  getImage: (id: string) => string | null;
  deleteImage: (id: string) => Promise<void>;
  loadImages: () => Promise<void>;
  clearAllImages: () => Promise<void>;
  getStorageSize: () => number;
}

const STORAGE_KEY = 'iron_stag_local_images';

export const useImageStore = create<ImageStore>((set, get) => ({
  images: {},
  isLoaded: false,

  saveImage: async (id, base64) => {
    const entry: ImageEntry = {
      id,
      base64,
      createdAt: new Date().toISOString(),
    };

    const { images } = get();
    const newImages = { ...images, [id]: entry };

    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(newImages));
      set({ images: newImages });
    } catch (error) {
      console.error('Error saving image:', error);
    }
  },

  getImage: (id) => {
    const { images } = get();
    return images[id]?.base64 || null;
  },

  deleteImage: async (id) => {
    const { images } = get();
    const { [id]: removed, ...rest } = images;

    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(rest));
      set({ images: rest });
    } catch (error) {
      console.error('Error deleting image:', error);
    }
  },

  loadImages: async () => {
    try {
      const stored = await AsyncStorage.getItem(STORAGE_KEY);
      if (stored) {
        set({ images: JSON.parse(stored), isLoaded: true });
      } else {
        set({ isLoaded: true });
      }
    } catch (error) {
      console.error('Error loading images:', error);
      set({ isLoaded: true });
    }
  },

  clearAllImages: async () => {
    try {
      await AsyncStorage.removeItem(STORAGE_KEY);
      set({ images: {} });
    } catch (error) {
      console.error('Error clearing images:', error);
    }
  },

  getStorageSize: () => {
    const { images } = get();
    const jsonStr = JSON.stringify(images);
    return new Blob([jsonStr]).size;
  },
}));
