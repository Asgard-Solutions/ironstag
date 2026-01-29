"""
Cloudflare R2 Storage Service

Handles image upload and retrieval for deer scan images.
Uses S3-compatible API via boto3.

Features:
- Upload base64 images to R2
- Generate public URLs for cross-device access
- Automatic content-type detection
- UUID-based file naming for security through obscurity
- Image compression to reduce storage costs
"""

import os
import base64
import uuid
import logging
from typing import Optional, Tuple
from io import BytesIO

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Image processing for compression
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL not available - image compression disabled")

load_dotenv()

logger = logging.getLogger(__name__)

# R2 Configuration
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "ironstag-images")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")

# Compression settings
MAX_IMAGE_DIMENSION = 1920  # Max width or height
JPEG_QUALITY = 85  # Quality for JPEG compression (1-100)
MAX_FILE_SIZE_KB = 500  # Target max file size in KB

# Check if R2 is configured
R2_ENABLED = all([R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME])

if R2_ENABLED:
    logger.info(f"R2 Storage enabled: bucket={R2_BUCKET_NAME}")
else:
    logger.warning("R2 Storage not configured - images will not be stored in cloud")


def get_r2_client():
    """Get a configured boto3 S3 client for R2."""
    if not R2_ENABLED:
        return None
    
    return boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name='auto',  # R2 uses 'auto' for region
    )


def parse_base64_image(base64_string: str) -> Tuple[bytes, str]:
    """
    Parse a base64 image string and return bytes and content type.
    
    Handles both formats:
    - data:image/jpeg;base64,/9j/4AAQ...
    - /9j/4AAQ... (raw base64)
    
    Returns:
        Tuple of (image_bytes, content_type)
    """
    content_type = "image/jpeg"  # Default
    
    if base64_string.startswith("data:"):
        # Parse data URL format
        header, base64_data = base64_string.split(",", 1)
        # Extract content type: data:image/jpeg;base64 -> image/jpeg
        if ":" in header and ";" in header:
            content_type = header.split(":")[1].split(";")[0]
    else:
        base64_data = base64_string
    
    # Decode base64 to bytes
    image_bytes = base64.b64decode(base64_data)
    
    return image_bytes, content_type


def compress_image(image_bytes: bytes, content_type: str) -> Tuple[bytes, str]:
    """
    Compress an image to reduce file size while maintaining quality.
    
    - Resizes if larger than MAX_IMAGE_DIMENSION
    - Converts to JPEG for better compression
    - Applies quality setting
    
    Args:
        image_bytes: Original image bytes
        content_type: Original content type
        
    Returns:
        Tuple of (compressed_bytes, new_content_type)
    """
    if not PIL_AVAILABLE:
        logger.debug("PIL not available, skipping compression")
        return image_bytes, content_type
    
    try:
        original_size = len(image_bytes) / 1024  # KB
        
        # Open image
        img = Image.open(BytesIO(image_bytes))
        
        # Convert RGBA to RGB (for JPEG compatibility)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize if too large
        width, height = img.size
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            # Calculate new size maintaining aspect ratio
            if width > height:
                new_width = MAX_IMAGE_DIMENSION
                new_height = int(height * (MAX_IMAGE_DIMENSION / width))
            else:
                new_height = MAX_IMAGE_DIMENSION
                new_width = int(width * (MAX_IMAGE_DIMENSION / height))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.debug(f"Resized image from {width}x{height} to {new_width}x{new_height}")
        
        # Compress to JPEG
        output = BytesIO()
        img.save(output, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        compressed_bytes = output.getvalue()
        
        compressed_size = len(compressed_bytes) / 1024  # KB
        savings = ((original_size - compressed_size) / original_size) * 100 if original_size > 0 else 0
        
        logger.info(f"Image compressed: {original_size:.1f}KB -> {compressed_size:.1f}KB ({savings:.1f}% reduction)")
        
        return compressed_bytes, "image/jpeg"
        
    except Exception as e:
        logger.warning(f"Image compression failed, using original: {e}")
        return image_bytes, content_type


def upload_scan_image(scan_id: str, base64_image: str) -> Optional[str]:
    """
    Upload a scan image to R2 storage.
    
    - Compresses image before upload to reduce storage costs
    - Uses scan_id as filename for easy retrieval
    
    Args:
        scan_id: The scan's UUID (used as filename)
        base64_image: Base64 encoded image string
        
    Returns:
        Public URL of the uploaded image, or None if upload failed
    """
    if not R2_ENABLED:
        logger.debug("R2 not enabled, skipping image upload")
        return None
    
    try:
        client = get_r2_client()
        if not client:
            return None
        
        # Parse the base64 image
        image_bytes, content_type = parse_base64_image(base64_image)
        
        # Determine file extension from content type
        ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
        }
        ext = ext_map.get(content_type, "jpg")
        
        # Use scan_id as filename for easy retrieval
        object_key = f"scans/{scan_id}.{ext}"
        
        # Upload to R2
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=object_key,
            Body=image_bytes,
            ContentType=content_type,
        )
        
        # Generate public URL
        # R2 public URLs format: https://<bucket>.<account-id>.r2.dev/<key>
        # Or custom domain if configured
        if R2_PUBLIC_URL:
            image_url = f"{R2_PUBLIC_URL}/{object_key}"
        else:
            # Fallback to S3-style URL (requires bucket to be public)
            image_url = f"{R2_ENDPOINT_URL}/{R2_BUCKET_NAME}/{object_key}"
        
        logger.info(f"Uploaded image for scan {scan_id}: {object_key}")
        return image_url
        
    except ClientError as e:
        logger.error(f"Failed to upload image to R2: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error uploading to R2: {e}")
        return None


def delete_scan_image(scan_id: str) -> bool:
    """
    Delete a scan image from R2 storage.
    
    Args:
        scan_id: The scan's UUID
        
    Returns:
        True if deleted successfully, False otherwise
    """
    if not R2_ENABLED:
        return True  # Nothing to delete
    
    try:
        client = get_r2_client()
        if not client:
            return False
        
        # Try common extensions
        for ext in ["jpg", "png", "webp"]:
            object_key = f"scans/{scan_id}.{ext}"
            try:
                client.delete_object(Bucket=R2_BUCKET_NAME, Key=object_key)
                logger.info(f"Deleted image from R2: {object_key}")
                return True
            except ClientError:
                continue
        
        return True  # No image found is okay
        
    except Exception as e:
        logger.error(f"Failed to delete image from R2: {e}")
        return False


def get_image_url(scan_id: str, ext: str = "jpg") -> Optional[str]:
    """
    Get the public URL for a scan image.
    
    Args:
        scan_id: The scan's UUID
        ext: File extension (default: jpg)
        
    Returns:
        Public URL or None
    """
    if not R2_ENABLED or not R2_PUBLIC_URL:
        return None
    
    object_key = f"scans/{scan_id}.{ext}"
    return f"{R2_PUBLIC_URL}/{object_key}"


def check_image_exists(scan_id: str) -> Tuple[bool, Optional[str]]:
    """
    Check if an image exists in R2 for a given scan.
    
    Returns:
        Tuple of (exists, url_if_exists)
    """
    if not R2_ENABLED:
        return False, None
    
    try:
        client = get_r2_client()
        if not client:
            return False, None
        
        # Try common extensions
        for ext in ["jpg", "png", "webp"]:
            object_key = f"scans/{scan_id}.{ext}"
            try:
                client.head_object(Bucket=R2_BUCKET_NAME, Key=object_key)
                url = f"{R2_PUBLIC_URL}/{object_key}" if R2_PUBLIC_URL else None
                return True, url
            except ClientError:
                continue
        
        return False, None
        
    except Exception as e:
        logger.error(f"Error checking image existence: {e}")
        return False, None
