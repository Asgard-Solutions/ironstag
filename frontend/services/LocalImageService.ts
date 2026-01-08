import * as FileSystem from 'expo-file-system/legacy';
import AsyncStorage from '@react-native-async-storage/async-storage';
import 'react-native-get-random-values';
import { v4 as uuidv4 } from 'uuid';
import { Platform } from 'react-native';

// Storage keys
const IMAGE_METADATA_KEY = '@iron_stag_image_metadata';
const CLEANUP_INTERVAL_KEY = '@cleanup_interval_days';
const WEB_IMAGE_STORAGE_KEY = '@iron_stag_web_images';

// Storage directory (only used on native)
const SCAN_IMAGES_DIR = FileSystem.documentDirectory ? `${FileSystem.documentDirectory}scan_images/` : '';

// Check if running on web
const isWeb = Platform.OS === 'web';

// Image metadata interface
interface ImageMetadata {
  localImageId: string;
  createdAt: number; // Unix timestamp
  sizeBytes: number;
  extension: string;
  fileName: string;
}

interface StorageStats {
  totalImages: number;
  totalSizeBytes: number;
  totalSizeMB: string;
  oldestImage: Date | null;
}

/**
 * LocalImageService - Privacy-First Local Storage System
 * 
 * Implements zero-cloud storage policy:
 * ✅ Images NEVER uploaded to cloud storage
 * ✅ Images NEVER stored on servers
 * ✅ Images exist ONLY on device
 * ✅ Complete user control over local data
 * ✅ Automatic cleanup when app uninstalled
 */
class LocalImageServiceClass {
  private initialized = false;

  /**
   * Initialize the storage directory
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    try {
      // Check if directory exists
      const dirInfo = await FileSystem.getInfoAsync(SCAN_IMAGES_DIR);
      
      if (!dirInfo.exists) {
        // Create scan_images directory
        await FileSystem.makeDirectoryAsync(SCAN_IMAGES_DIR, { intermediates: true });
        console.log('[LocalImageService] Created scan_images directory');
      }
      
      this.initialized = true;
    } catch (error) {
      console.error('[LocalImageService] Failed to initialize:', error);
      throw error;
    }
  }

  /**
   * Get file extension from URI or default to jpg
   */
  private getFileExtension(uri: string): string {
    const match = uri.match(/\.([^.]+)$/);
    if (match) {
      const ext = match[1].toLowerCase();
      if (['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'].includes(ext)) {
        return ext === 'jpeg' ? 'jpg' : ext;
      }
    }
    return 'jpg';
  }

  /**
   * Get all image metadata from AsyncStorage
   */
  private async getAllMetadata(): Promise<Record<string, ImageMetadata>> {
    try {
      const stored = await AsyncStorage.getItem(IMAGE_METADATA_KEY);
      return stored ? JSON.parse(stored) : {};
    } catch (error) {
      console.error('[LocalImageService] Error loading metadata:', error);
      return {};
    }
  }

  /**
   * Save all metadata to AsyncStorage
   */
  private async saveAllMetadata(metadata: Record<string, ImageMetadata>): Promise<void> {
    try {
      await AsyncStorage.setItem(IMAGE_METADATA_KEY, JSON.stringify(metadata));
    } catch (error) {
      console.error('[LocalImageService] Error saving metadata:', error);
      throw error;
    }
  }

  /**
   * Save an image from a source URI to local storage
   * Returns the localImageId (UUID)
   */
  async saveImage(sourceUri: string): Promise<string> {
    await this.initialize();

    // 1. Check if source file exists
    const fileInfo = await FileSystem.getInfoAsync(sourceUri);
    if (!fileInfo.exists) {
      throw new Error('Image file does not exist');
    }

    // 2. Check file size (10MB limit)
    const sizeBytes = fileInfo.size || 0;
    if (sizeBytes > 10 * 1024 * 1024) {
      const sizeMB = (sizeBytes / (1024 * 1024)).toFixed(1);
      throw new Error(`Image too large: ${sizeMB}MB exceeds 10MB limit`);
    }

    // 3. Generate UUID for identification
    const localImageId = uuidv4();
    const extension = this.getFileExtension(sourceUri);
    const fileName = `${localImageId}.${extension}`;
    const localPath = `${SCAN_IMAGES_DIR}${fileName}`;

    // 4. Copy from temp location to permanent local storage
    await FileSystem.copyAsync({
      from: sourceUri,
      to: localPath,
    });

    // 5. Save metadata for cleanup tracking
    const metadata = await this.getAllMetadata();
    metadata[localImageId] = {
      localImageId,
      createdAt: Date.now(),
      sizeBytes,
      extension,
      fileName,
    };
    await this.saveAllMetadata(metadata);

    console.log(`[LocalImageService] Saved image: ${localImageId}`);
    return localImageId;
  }

  /**
   * Save an image from base64 data
   * Returns the localImageId (UUID)
   */
  async saveImageFromBase64(base64Data: string, extension: string = 'jpg'): Promise<string> {
    await this.initialize();

    // 1. Generate UUID for identification
    const localImageId = uuidv4();
    const fileName = `${localImageId}.${extension}`;
    const localPath = `${SCAN_IMAGES_DIR}${fileName}`;

    // 2. Remove data URL prefix if present
    let base64String = base64Data;
    if (base64Data.includes(',')) {
      base64String = base64Data.split(',')[1];
    }

    // 3. Write base64 to file
    await FileSystem.writeAsStringAsync(localPath, base64String, {
      encoding: FileSystem.EncodingType.Base64,
    });

    // 4. Get file size
    const fileInfo = await FileSystem.getInfoAsync(localPath);
    const sizeBytes = fileInfo.size || 0;

    // 5. Save metadata
    const metadata = await this.getAllMetadata();
    metadata[localImageId] = {
      localImageId,
      createdAt: Date.now(),
      sizeBytes,
      extension,
      fileName,
    };
    await this.saveAllMetadata(metadata);

    console.log(`[LocalImageService] Saved image from base64: ${localImageId}`);
    return localImageId;
  }

  /**
   * Get image as base64 data URL for display or AI analysis
   */
  async getImageAsBase64(localImageId: string): Promise<string | null> {
    await this.initialize();

    const metadata = await this.getAllMetadata();
    const entry = metadata[localImageId];
    
    if (!entry) {
      console.warn(`[LocalImageService] Image not found: ${localImageId}`);
      return null;
    }

    const localPath = `${SCAN_IMAGES_DIR}${entry.fileName}`;
    
    try {
      const fileInfo = await FileSystem.getInfoAsync(localPath);
      if (!fileInfo.exists) {
        console.warn(`[LocalImageService] Image file missing: ${localPath}`);
        return null;
      }

      const base64String = await FileSystem.readAsStringAsync(localPath, {
        encoding: FileSystem.EncodingType.Base64,
      });

      // Determine MIME type
      const mimeType = entry.extension === 'png' ? 'image/png' : 'image/jpeg';
      return `data:${mimeType};base64,${base64String}`;
    } catch (error) {
      console.error(`[LocalImageService] Error reading image: ${localImageId}`, error);
      return null;
    }
  }

  /**
   * Get the local file URI for an image
   */
  async getImageUri(localImageId: string): Promise<string | null> {
    await this.initialize();

    const metadata = await this.getAllMetadata();
    const entry = metadata[localImageId];
    
    if (!entry) return null;

    const localPath = `${SCAN_IMAGES_DIR}${entry.fileName}`;
    const fileInfo = await FileSystem.getInfoAsync(localPath);
    
    return fileInfo.exists ? localPath : null;
  }

  /**
   * Delete a single image by localImageId
   */
  async deleteImage(localImageId: string): Promise<boolean> {
    await this.initialize();

    const metadata = await this.getAllMetadata();
    const entry = metadata[localImageId];
    
    if (!entry) return false;

    const localPath = `${SCAN_IMAGES_DIR}${entry.fileName}`;

    try {
      // Delete physical file
      const fileInfo = await FileSystem.getInfoAsync(localPath);
      if (fileInfo.exists) {
        await FileSystem.deleteAsync(localPath);
      }

      // Remove from metadata
      delete metadata[localImageId];
      await this.saveAllMetadata(metadata);

      console.log(`[LocalImageService] Deleted image: ${localImageId}`);
      return true;
    } catch (error) {
      console.error(`[LocalImageService] Error deleting image: ${localImageId}`, error);
      return false;
    }
  }

  /**
   * Get cleanup interval setting (default: 90 days)
   */
  async getCleanupInterval(): Promise<number> {
    try {
      const stored = await AsyncStorage.getItem(CLEANUP_INTERVAL_KEY);
      return stored ? parseInt(stored, 10) : 90;
    } catch (error) {
      return 90;
    }
  }

  /**
   * Set cleanup interval setting
   */
  async setCleanupInterval(days: number): Promise<void> {
    await AsyncStorage.setItem(CLEANUP_INTERVAL_KEY, days.toString());
  }

  /**
   * Clean up old images based on cleanup interval
   * Returns count of deleted images
   */
  async cleanupOldImages(daysOld?: number): Promise<number> {
    await this.initialize();

    // Use stored preference if no value provided
    const effectiveDays = daysOld ?? await this.getCleanupInterval();

    // Calculate cutoff date
    const cutoffDate = Date.now() - (effectiveDays * 24 * 60 * 60 * 1000);

    const metadata = await this.getAllMetadata();
    let deletedCount = 0;

    for (const [localImageId, meta] of Object.entries(metadata)) {
      if (meta.createdAt < cutoffDate) {
        // Image is older than threshold
        const deleted = await this.deleteImage(localImageId);
        if (deleted) {
          deletedCount++;
        }
      }
    }

    console.log(`[LocalImageService] Cleaned up ${deletedCount} old images (>${effectiveDays} days)`);
    return deletedCount;
  }

  /**
   * Clear ALL local images
   * Returns count of deleted images
   */
  async clearAllImages(): Promise<number> {
    await this.initialize();

    const metadata = await this.getAllMetadata();
    const imageIds = Object.keys(metadata);
    let deletedCount = 0;

    for (const localImageId of imageIds) {
      const deleted = await this.deleteImage(localImageId);
      if (deleted) {
        deletedCount++;
      }
    }

    // Clear metadata completely
    await AsyncStorage.removeItem(IMAGE_METADATA_KEY);

    console.log(`[LocalImageService] Cleared all ${deletedCount} images`);
    return deletedCount;
  }

  /**
   * Get storage statistics
   */
  async getStorageStats(): Promise<StorageStats> {
    await this.initialize();

    const metadata = await this.getAllMetadata();
    const entries = Object.values(metadata);

    if (entries.length === 0) {
      return {
        totalImages: 0,
        totalSizeBytes: 0,
        totalSizeMB: '0.00',
        oldestImage: null,
      };
    }

    const totalImages = entries.length;
    const totalSizeBytes = entries.reduce((sum, m) => sum + m.sizeBytes, 0);
    const totalSizeMB = (totalSizeBytes / (1024 * 1024)).toFixed(2);
    const oldestTimestamp = Math.min(...entries.map(m => m.createdAt));

    return {
      totalImages,
      totalSizeBytes,
      totalSizeMB,
      oldestImage: new Date(oldestTimestamp),
    };
  }

  /**
   * Get all image entries with metadata
   */
  async getAllImages(): Promise<ImageMetadata[]> {
    const metadata = await this.getAllMetadata();
    return Object.values(metadata);
  }

  /**
   * Check if an image exists
   */
  async imageExists(localImageId: string): Promise<boolean> {
    const metadata = await this.getAllMetadata();
    const entry = metadata[localImageId];
    
    if (!entry) return false;

    const localPath = `${SCAN_IMAGES_DIR}${entry.fileName}`;
    const fileInfo = await FileSystem.getInfoAsync(localPath);
    
    return fileInfo.exists;
  }
}

// Export singleton instance
export const LocalImageService = new LocalImageServiceClass();

// Export types
export type { ImageMetadata, StorageStats };
