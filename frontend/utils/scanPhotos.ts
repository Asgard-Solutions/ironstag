import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';

export const MAX_SCAN_PHOTOS = 3;
// Bound upload + model cost: longest edge sent to the server
const MAX_UPLOAD_EDGE = 2048;
const UPLOAD_JPEG_QUALITY = 0.85;
export const MIN_CROP_FRACTION = 0.2;

export type CropRect = { x: number; y: number; width: number; height: number };

export type ScanPhoto = {
  key: string;
  uri: string; // data:image/jpeg;base64,... (orientation baked in)
  width: number;
  height: number;
  capturedAt?: string;
  crop?: CropRect | null;
};

export type ScanRequestImage = {
  image_base64: string;
  image_id: string;
  local_image_id?: string;
  captured_at?: string;
  crop_rect?: CropRect;
};

export const newId = () =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;

function exifCaptureDate(exif?: Record<string, any> | null): string | undefined {
  if (!exif) return undefined;
  const nested = exif['{Exif}'] || {};
  const raw = exif.DateTimeOriginal || nested.DateTimeOriginal || exif.DateTime || nested.DateTimeDigitized;
  return typeof raw === 'string' && raw.trim() ? raw.trim() : undefined;
}

/** Re-encode to a bounded JPEG (keeps orientation upright) and keep capture metadata. */
export async function normalizePhoto(
  uri: string,
  width?: number,
  height?: number,
  exif?: Record<string, any> | null,
): Promise<ScanPhoto> {
  const context = ImageManipulator.manipulate(uri);
  const longest = Math.max(width || 0, height || 0);
  if (longest > MAX_UPLOAD_EDGE) {
    context.resize((width || 0) >= (height || 0) ? { width: MAX_UPLOAD_EDGE } : { height: MAX_UPLOAD_EDGE });
  }
  const rendered = await context.renderAsync();
  const saved = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: UPLOAD_JPEG_QUALITY, base64: true });
  return {
    key: newId(),
    uri: `data:image/jpeg;base64,${saved.base64}`,
    width: saved.width,
    height: saved.height,
    capturedAt: exifCaptureDate(exif),
    crop: null,
  };
}

export function toRequestImages(photos: ScanPhoto[], localIds: (string | undefined)[]): ScanRequestImage[] {
  return photos.map((photo, index) => ({
    image_base64: photo.uri,
    image_id: `img_${index + 1}`,
    local_image_id: localIds[index],
    captured_at: photo.capturedAt,
    ...(photo.crop ? { crop_rect: photo.crop } : {}),
  }));
}
