"""
Cloudflare R2 Storage Service

Handles image upload and retrieval for deer scan images.
Uses S3-compatible API via boto3.

Features:
- Upload base64 images to R2
- Generate public URLs for cross-device access
- Automatic content-type detection
- UUID-based file naming for security through obscurity
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

load_dotenv()

logger = logging.getLogger(__name__)

# R2 Configuration
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "ironstag-images")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")

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


def upload_scan_image(scan_id: str, base64_image: str) -> Optional[str]:
    """
    Upload a scan image to R2 storage.
    
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
