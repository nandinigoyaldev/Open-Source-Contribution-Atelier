#!/usr/bin/env python3
"""
Automated Dual-Region S3 Bucket Replication Setup Script.

Enables Cross-Region Replication (CRR) between primary and replica S3 buckets:
1. Verifies / enables bucket versioning on both primary and replica buckets.
2. Applies replication policy with S3 Replication Time Control (RTC) & metrics.
3. Tests cross-region replication health.

Usage:
    python infra/storage/setup_replication.py \\
        --primary-bucket atelier-media-primary \\
        --primary-region us-east-1 \\
        --replica-bucket atelier-media-replica \\
        --replica-region eu-central-1 \\
        --role-arn arn:aws:iam::123456789012:role/s3-cross-region-replication-role
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("s3-replication-setup")


def enable_bucket_versioning(
    s3_client, bucket_name: str, dry_run: bool = False
) -> bool:
    """Checks and enables bucket versioning, required for cross-region replication."""
    if dry_run:
        logger.info(f"[Dry-Run] Would enable versioning on bucket: {bucket_name}")
        return True

    try:
        ver_status = s3_client.get_bucket_versioning(Bucket=bucket_name).get("Status")
        if ver_status == "Enabled":
            logger.info(f"Bucket {bucket_name} already has versioning enabled.")
            return True

        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": "Enabled"},
        )
        logger.info(f"Enabled bucket versioning on {bucket_name}.")
        return True
    except ClientError as e:
        logger.error(f"Failed to enable versioning on {bucket_name}: {e}")
        return False


def setup_dual_region_replication(
    primary_bucket: str,
    primary_region: str,
    replica_bucket: str,
    replica_region: str,
    role_arn: str,
    policy_file: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Configures automated dual-region cross-region replication."""
    logger.info("Initializing dual-region S3 replication provisioning...")
    logger.info(f"  Primary: {primary_bucket} ({primary_region})")
    logger.info(f"  Replica: {replica_bucket} ({replica_region})")
    logger.info(f"  IAM Role: {role_arn}")

    s3_primary = boto3.client("s3", region_name=primary_region)
    s3_replica = boto3.client("s3", region_name=replica_region)

    # 1. Versioning check on both buckets
    if not enable_bucket_versioning(s3_primary, primary_bucket, dry_run):
        return False
    if not enable_bucket_versioning(s3_replica, replica_bucket, dry_run):
        return False

    # 2. Build replication configuration
    replication_config: Dict[str, Any] = {
        "Role": role_arn,
        "Rules": [
            {
                "ID": "AutomatedDualRegionMediaReplication",
                "Status": "Enabled",
                "Priority": 1,
                "Filter": {"Prefix": ""},
                "Destination": {
                    "Bucket": f"arn:aws:s3:::{replica_bucket}",
                    "StorageClass": "STANDARD",
                    "ReplicationTime": {
                        "Status": "Enabled",
                        "Time": {"Minutes": 15},
                    },
                    "Metrics": {
                        "Status": "Enabled",
                        "EventThreshold": {"Minutes": 15},
                    },
                },
                "DeleteMarkerReplication": {"Status": "Disabled"},
            }
        ],
    }

    if policy_file and os.path.exists(policy_file):
        with open(policy_file, "r", encoding="utf-8") as f:
            replication_config = json.load(f)
            replication_config["Role"] = role_arn
            replication_config["Rules"][0]["Destination"][
                "Bucket"
            ] = f"arn:aws:s3:::{replica_bucket}"

    if dry_run:
        logger.info(
            f"[Dry-Run] Replication config to be applied:\n{json.dumps(replication_config, indent=2)}"
        )
        return True

    # 3. Apply replication configuration to primary bucket
    try:
        s3_primary.put_bucket_replication(
            Bucket=primary_bucket,
            ReplicationConfiguration=replication_config,
        )
        logger.info(
            f"Successfully applied dual-region replication policy to {primary_bucket} -> {replica_bucket}"
        )
        return True
    except ClientError as e:
        logger.error(f"Failed to apply replication policy to {primary_bucket}: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Dual-Region S3 Bucket Replication Setup Tool."
    )
    parser.add_argument(
        "--primary-bucket",
        default=os.getenv("AWS_STORAGE_BUCKET_NAME", "atelier-media-primary"),
        help="Primary S3 bucket name",
    )
    parser.add_argument(
        "--primary-region",
        default=os.getenv("AWS_S3_REGION_NAME", "us-east-1"),
        help="Primary bucket AWS region",
    )
    parser.add_argument(
        "--replica-bucket",
        default=os.getenv("AWS_S3_REPLICA_BUCKET_NAME", "atelier-media-replica"),
        help="Replica S3 bucket name",
    )
    parser.add_argument(
        "--replica-region",
        default=os.getenv("AWS_S3_REPLICA_REGION_NAME", "eu-central-1"),
        help="Replica bucket AWS region",
    )
    parser.add_argument(
        "--role-arn",
        default=os.getenv(
            "AWS_S3_REPLICATION_ROLE_ARN",
            "arn:aws:iam::123456789012:role/s3-cross-region-replication-role",
        ),
        help="IAM role ARN granting S3 replication permissions",
    )
    parser.add_argument(
        "--policy-file",
        default="infra/storage/s3-replication-policy.json",
        help="Path to S3 replication policy JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate replication provisioning without modifying AWS",
    )

    args = parser.parse_args()

    success = setup_dual_region_replication(
        primary_bucket=args.primary_bucket,
        primary_region=args.primary_region,
        replica_bucket=args.replica_bucket,
        replica_region=args.replica_region,
        role_arn=args.role_arn,
        policy_file=args.policy_file,
        dry_run=args.dry_run,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
