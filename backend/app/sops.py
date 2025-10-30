"""SOP management and S3 integration for Seller Assistant."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SOP:
    """Represents a Standard Operating Procedure from S3."""

    id: str
    title: str
    category: str
    keywords: list[str]
    content: str
    images: list[str]  # List of S3 URLs
    last_updated: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SOP:
        """Create SOP from JSON dict."""
        return cls(
            id=data["id"],
            title=data["title"],
            category=data.get("category", "General"),
            keywords=data.get("keywords", []),
            content=data["content"],
            images=data.get("images", []),
            last_updated=data.get("last_updated"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize the SOP for JSON responses."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "keywords": self.keywords,
            "content": self.content,
            "images": self.images,
            "last_updated": self.last_updated,
        }


class SOPS3Client:
    """Helper for fetching SOPs and images from S3."""

    def __init__(
        self,
        sop_bucket: str,
        images_bucket: str,
        region: str = "us-east-1",
        aws_profile: str | None = None,
    ) -> None:
        self.sop_bucket = sop_bucket
        self.images_bucket = images_bucket
        self.region = region

        # Initialize S3 client with AWS profile
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.s3_client = session.client(
                "s3",
                region_name=region,
                config=Config(signature_version="s3v4"),
            )
        else:
            # Fall back to default credentials (environment variables, IAM role, etc.)
            self.s3_client = boto3.client(
                "s3",
                region_name=region,
                config=Config(signature_version="s3v4"),
            )

    async def get_sop(self, sop_id: str) -> SOP | None:
        """Fetch SOP JSON from S3 and parse it."""
        try:
            # Construct S3 key 
            s3_key = f"{sop_id}.json"

            logger.info(f"Fetching SOP from S3: bucket={self.sop_bucket}, key={s3_key}")

            response = self.s3_client.get_object(Bucket=self.sop_bucket, Key=s3_key)
            content = response["Body"].read().decode("utf-8")
            sop_data = json.loads(content)

            sop = SOP.from_dict(sop_data)

            # Generate pre-signed URLs for images if they exist
            if sop.images:
                sop.images = [await self._generate_presigned_url(img_path) for img_path in sop.images]

            logger.info(f"Successfully fetched SOP: {sop.id} - {sop.title}")
            return sop

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 ClientError fetching SOP {sop_id}: {error_code} - {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse SOP JSON for {sop_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching SOP {sop_id}: {str(e)}")
            return None

    async def _generate_presigned_url(self, s3_path: str, expiration: int = 3600) -> str:
        """Generate a pre-signed URL for an S3 object.

        Args:
            s3_path: S3 path in format "s3://bucket/key" or just "images/filename.jpg"
            expiration: URL expiration time in seconds (default 1 hour)

        Returns:
            Pre-signed URL string
        """
        try:
            # Parse S3 path
            if s3_path.startswith("s3://"):
                # Format: s3://bucket/key
                parts = s3_path.replace("s3://", "").split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
            else:
                # Assume it's just the key, use images bucket
                bucket = self.images_bucket
                key = s3_path

            logger.debug(f"Generating presigned URL for bucket={bucket}, key={key}")

            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expiration,
            )

            return url

        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {s3_path}: {str(e)}")
            # Return original path as fallback
            return s3_path


class SOPTableOfContents:
    """Manages the SOP table of contents for agent context."""

    def __init__(self, toc_data: dict[str, Any] | None = None) -> None:
        """Initialize with TOC data.

        Args:
            toc_data: Dictionary with structure:
                {
                    "categories": {
                        "Category Name": [
                            {"id": "sop-id", "title": "Title", "keywords": ["kw1", "kw2"]},
                            ...
                        ],
                        ...
                    }
                }
        """
        self.toc_data = toc_data or self._get_default_toc()

    def _get_default_toc(self) -> dict[str, Any]:
        """Load table of contents from external JSON file."""
        toc_file = os.path.join(os.path.dirname(__file__), "sop_toc.json")

        try:
            with open(toc_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"TOC file not found: {toc_file}")
            return {"categories": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in TOC file: {e}")
            return {"categories": {}}
        except Exception as e:
            logger.error(f"Unexpected error loading TOC file: {e}")
            return {"categories": {}}
            
    def get_formatted_toc(self) -> str:
        """Get formatted table of contents for agent context."""
        lines = ["# Amazon Seller Assistant - SOP Library\n"]

        for category, entries in self.toc_data.get("categories", {}).items():
            lines.append(f"\n## {category}")
            for entry in entries:
                lines.append(f"- **{entry['id']}**: {entry['title']}")
                if entry.get("keywords"):
                    keywords_str = ", ".join(entry["keywords"])
                    lines.append(f"  - Keywords: {keywords_str}")

        return "\n".join(lines)


# Global instances
sop_toc = SOPTableOfContents()
sop_s3_client = SOPS3Client(
    sop_bucket=os.getenv("SOP_BUCKET", "lumian-sops"),
    images_bucket=os.getenv("IMAGES_BUCKET", "lumian-sop-images"),
    region=os.getenv("AWS_REGION", "us-east-2"),
    aws_profile=os.getenv("AWS_PROFILE"),
)


def get_formatted_sop_toc() -> str:
    """Get the formatted table of contents for agent instructions."""
    return sop_toc.get_formatted_toc()
