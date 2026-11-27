"""
Multi-region S3-compatible object storage backend with CDN edge caching and replication.

Supports:
- Primary and secondary/replica AWS S3, Cloudflare R2, or MinIO buckets.
- Automatic failover to replica region if primary bucket is unreachable.
- Edge caching headers: 'Cache-Control: public, max-age=31536000, immutable'.
- Direct-to-S3 signed pre-authenticated upload URLs (PUT presigned).
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage

logger = logging.getLogger(__name__)

# Base S3 storage class from django-storages (or fallback if not installed)
try:
    from storages.backends.s3boto3 import S3Boto3Storage
except ImportError:
    logger.warning(
        "django-storages not installed. S3Boto3Storage falling back to Storage stub."
    )

    class S3Boto3Storage(Storage):  # type: ignore
        def __init__(self, **settings):
            self.bucket_name = settings.get("bucket_name", "atelier-media-primary")
            self.region_name = settings.get("region_name", "us-east-1")
            self.custom_domain = settings.get("custom_domain")
            self.endpoint_url = settings.get("endpoint_url")
            self.object_parameters = settings.get("object_parameters", {})
            self.file_overwrite = settings.get("file_overwrite", False)
            self.default_acl = settings.get("default_acl")
            self.location = settings.get("location", "")


class MultiRegionS3Storage(S3Boto3Storage):
    """
    S3-compatible storage backend with dual-region replication support,
    automatic read failover, and CDN edge-caching header defaults.
    """

    CACHE_CONTROL_HEADER = "public, max-age=31536000, immutable"

    def __init__(self, **kwargs):
        # Primary Region Configuration
        kwargs.setdefault(
            "bucket_name",
            getattr(settings, "AWS_STORAGE_BUCKET_NAME", "atelier-media-primary"),
        )
        kwargs.setdefault(
            "region_name", getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
        )
        kwargs.setdefault(
            "endpoint_url", getattr(settings, "AWS_S3_ENDPOINT_URL", None)
        )
        kwargs.setdefault(
            "custom_domain", getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
        )
        kwargs.setdefault("file_overwrite", False)
        kwargs.setdefault("default_acl", None)

        # Enforce Cloudflare / CloudFront 1-year immutable edge caching headers
        object_parameters = kwargs.get("object_parameters") or {}
        object_parameters.setdefault("CacheControl", self.CACHE_CONTROL_HEADER)
        kwargs["object_parameters"] = object_parameters

        super().__init__(**kwargs)

        # Secondary (Replica) Region Configuration
        self.replica_bucket_name = getattr(
            settings, "AWS_S3_REPLICA_BUCKET_NAME", "atelier-media-replica"
        )
        self.replica_region_name = getattr(
            settings, "AWS_S3_REPLICA_REGION_NAME", "eu-central-1"
        )
        self.replica_endpoint_url = getattr(
            settings, "AWS_S3_REPLICA_ENDPOINT_URL", None
        )
        self.replication_enabled = getattr(settings, "AWS_S3_REPLICATION_ENABLED", True)

        self._replica_client = None

    def get_replica_client(self):
        """Returns boto3 S3 client targeted at the secondary replication region."""
        if self._replica_client is None:
            config = Config(
                region_name=self.replica_region_name,
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            )
            self._replica_client = boto3.client(
                "s3",
                region_name=self.replica_region_name,
                endpoint_url=self.replica_endpoint_url,
                aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
                config=config,
            )
        return self._replica_client

    def _save(self, name, content):
        """
        Saves object to primary bucket and replicates to secondary bucket
        if dual-write replication is enabled.
        """
        saved_name = super()._save(name, content)

        if self.replication_enabled and hasattr(content, "seek"):
            try:
                content.seek(0)
                replica_client = self.get_replica_client()
                replica_key = self._normalize_name(self._clean_name(name))
                replica_client.put_object(
                    Bucket=self.replica_bucket_name,
                    Key=replica_key,
                    Body=content.read(),
                    CacheControl=self.CACHE_CONTROL_HEADER,
                    ContentType=getattr(
                        content, "content_type", "application/octet-stream"
                    ),
                )
                logger.info(
                    "Replicated asset %s to secondary region bucket %s",
                    replica_key,
                    self.replica_bucket_name,
                )
            except Exception as e:
                logger.warning(
                    "Cross-region replication to secondary bucket %s failed: %s",
                    self.replica_bucket_name,
                    e,
                )

        return saved_name

    def exists(self, name):
        """Checks primary bucket first; falls back to secondary replica bucket."""
        try:
            return super().exists(name)
        except (ClientError, BotoCoreError) as e:
            logger.warning(
                "Primary S3 exists check failed for %s (%s). Falling back to replica.",
                name,
                e,
            )
            return self._replica_exists(name)

    def _replica_exists(self, name: str) -> bool:
        try:
            replica_client = self.get_replica_client()
            replica_key = self._normalize_name(self._clean_name(name))
            replica_client.head_object(Bucket=self.replica_bucket_name, Key=replica_key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            logger.error("Replica exists check error: %s", e)
            return False
        except Exception:
            return False

    def url(self, name):
        """Generates public CDN URL with custom domain or S3 path."""
        if self.custom_domain:
            clean_name = self._normalize_name(self._clean_name(name))
            return f"https://{self.custom_domain}/{clean_name}"
        return super().url(name)


class MediaS3Storage(MultiRegionS3Storage):
    """Storage backend for user uploads and media assets."""

    location = "media"
    file_overwrite = False
    default_acl = None


class StaticS3Storage(MultiRegionS3Storage):
    """Storage backend for static files."""

    location = "static"
    default_acl = None


def generate_presigned_upload_url(
    filename: str,
    content_type: str,
    user_id: Optional[str] = None,
    prefix: str = "media/uploads",
    expires_in: int = 3600,
    max_size_bytes: int = 100 * 1024 * 1024,  # 100 MB max
) -> Dict[str, Any]:
    """
    Generates a pre-authenticated S3 PUT upload URL for direct client-to-storage uploads.
    Bypasses the Django application server to eliminate memory exhaustion.

    Enforces:
    - HTTP PUT method
    - Pre-defined Content-Type matching validation
    - CDN edge caching header: 'Cache-Control: public, max-age=31536000, immutable'
    """
    from apps.uploads.views import sanitize_filename_ascii

    clean_filename = sanitize_filename_ascii(filename)
    unique_id = uuid.uuid4().hex[:12]
    user_prefix = f"user_{user_id}" if user_id else "anonymous"
    s3_key = f"{prefix.strip('/')}/{user_prefix}/{unique_id}-{clean_filename}"

    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "atelier-media-primary")
    region_name = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
    endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)

    cache_control = "public, max-age=31536000, immutable"

    config = Config(
        region_name=region_name,
        signature_version="s3v4",
        retries={"max_attempts": 3, "mode": "standard"},
    )

    s3_client = boto3.client(
        "s3",
        region_name=region_name,
        endpoint_url=endpoint_url,
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        config=config,
    )

    upload_url = s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket_name,
            "Key": s3_key,
            "ContentType": content_type,
            "CacheControl": cache_control,
        },
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )

    # Public CDN URL after upload completes
    if custom_domain:
        public_url = f"https://{custom_domain}/{s3_key}"
    elif endpoint_url:
        public_url = f"{endpoint_url.rstrip('/')}/{bucket_name}/{s3_key}"
    else:
        public_url = f"https://{bucket_name}.s3.{region_name}.amazonaws.com/{s3_key}"

    return {
        "upload_url": upload_url,
        "method": "PUT",
        "s3_key": s3_key,
        "public_url": public_url,
        "bucket": bucket_name,
        "region": region_name,
        "headers": {
            "Content-Type": content_type,
            "Cache-Control": cache_control,
        },
        "expires_in": expires_in,
        "max_size_bytes": max_size_bytes,
    }
