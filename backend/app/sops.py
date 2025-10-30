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
        """Return default/sample table of contents."""
        return {
            "categories": {
                "Advertising": [
                    {
                        "id": "advertising-sop-prime-day-advertising-actions",
                        "title": "Advertising SOP: Prime Day Advertising Actions",
                        "keywords": [
                            "Prime Day Ads",
                            "Amazon Ads",
                            "ACOS optimization",
                            "Bulk file edits",
                            "Budget rules"
                        ]
                    },
                    {
                        "id": "advertising-sop-setting-up-a-sponsored-display-campaign",
                        "title": "Advertising SOP: Setting Up a Sponsored Display Campaign",
                        "keywords": [
                            "Sponsored Display",
                            "Amazon Advertising",
                            "PPC Campaigns",
                            "Remarketing Audiences",
                            "ASIN Selection"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-to-download-advertising-invoice",
                        "title": "Advertising SOP: How to Download Advertising Invoice",
                        "keywords": [
                            "Seller Central",
                            "Sponsored Ads Billing",
                            "Advertising invoice",
                            "Campaign Manager",
                            "Download invoice"
                        ]
                    },
                    {
                        "id": "ppc-faqs-to-enrich-your-amazon-advertising-knowledge",
                        "title": "PPC FAQs To Enrich Your Amazon Advertising Knowledge",
                        "keywords": [
                            "Amazon PPC",
                            "Search Term Reports",
                            "duplicate keywords",
                            "negative keywords",
                            "long-tail keywords"
                        ]
                    },
                    {
                        "id": "advertising-sop-best-practices-on-campaign-segmentation",
                        "title": "Advertising SOP: Best Practices on Campaign Segmentation",
                        "keywords": [
                            "Amazon PPC",
                            "campaign segmentation",
                            "keyword targeting",
                            "Sponsored Products",
                            "ASIN segmentation"
                        ]
                    },
                    {
                        "id": "advertising-sop-budget-expectation",
                        "title": "Advertising SOP: Budget Expectation",
                        "keywords": [
                            "Amazon advertising",
                            "budget checks",
                            "ACOS optimization",
                            "negative keywords",
                            "bid calculation"
                        ]
                    },
                    {
                        "id": "advertising-sop-for-excel-macro-usage-streamlining-bulk-file-filtering-and-bulk-optimizations",
                        "title": "Advertising SOP for Excel Macro Usage: Streamlining Bulk File Filtering and Bulk Optimizations",
                        "keywords": [
                            "Amazon Advertising",
                            "Excel Macros",
                            "Bulk File",
                            "Sponsored Brands",
                            "Bulk Optimizations"
                        ]
                    },
                    {
                        "id": "advertising-sop-adding-a-sku-to-an-existing-campaign-using-bulk-file",
                        "title": "Advertising SOP: Adding a SKU to an Existing Campaign Using Bulk File",
                        "keywords": [
                            "Amazon Advertising",
                            "Sponsored Products",
                            "Bulk file upload",
                            "Add SKU",
                            "ASIN mapping"
                        ]
                    },
                    {
                        "id": "advertising-sop-setting-budget-for-campaigns",
                        "title": "Advertising SOP: Setting Budget for Campaigns",
                        "keywords": [
                            "Amazon advertising",
                            "campaign budget",
                            "Sponsored Products",
                            "daily budget formula",
                            "ASIN campaign strategy"
                        ]
                    },
                    {
                        "id": "advertising-sop-bulk-operations---bid-adjustment",
                        "title": "Advertising SOP: Bulk Operations - Bid Adjustment",
                        "keywords": [
                            "Amazon Advertising",
                            "Bulk Bid Adjustment",
                            "Sponsored Products",
                            "ACOS Optimization",
                            "Campaign Manager"
                        ]
                    },
                    {
                        "id": "advertising-sop-uploading-backup-file-through-bulk-operations",
                        "title": "Advertising SOP: Uploading Backup File through Bulk Operations",
                        "keywords": [
                            "Amazon Advertising",
                            "Bulk Operations",
                            "Bulk Spreadsheet",
                            "Campaign upload",
                            "Bid management"
                        ]
                    },
                    {
                        "id": "advertising-sop-creating-an-advertising-report",
                        "title": "Advertising SOP: Creating an Advertising Report",
                        "keywords": [
                            "Amazon advertising",
                            "Sponsored Ads Report",
                            "Seller Central reports",
                            "Campaign Manager",
                            "Advertising analytics"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-to-change-campaign-names-in-bulk",
                        "title": "Advertising SOP: How to Change Campaign Names in Bulk",
                        "keywords": [
                            "Amazon Advertising",
                            "bulk campaign rename",
                            "Bulk Sheet",
                            "ad group rename",
                            "PPC bulk edits"
                        ]
                    },
                    {
                        "id": "advertising-sop-advertising-first-time-setup-and-segmentation",
                        "title": "Advertising SOP: Advertising First-Time Setup and Segmentation",
                        "keywords": [
                            "Amazon PPC",
                            "ad segmentation",
                            "keyword research",
                            "campaign structure",
                            "bid strategy"
                        ]
                    },
                    {
                        "id": "advertising-sop-deduplicator-tool",
                        "title": "Advertising SOP: DEDUPLICATOR TOOL",
                        "keywords": [
                            "Amazon PPC",
                            "keyword deduplication",
                            "Sponsored Products",
                            "Sponsored Brands",
                            "match type"
                        ]
                    },
                    {
                        "id": "advertising-sop-sponsored-products-purchased-product-report",
                        "title": "Advertising SOP: Sponsored Products Purchased Product Report",
                        "keywords": [
                            "Sponsored Products",
                            "Purchased Product Report",
                            "Campaign Manager",
                            "Purchase attribution",
                            "Pivot table"
                        ]
                    },
                    {
                        "id": "advertising-sop-sponsored-products-placement-report",
                        "title": "Advertising SOP: Sponsored Products Placement Report",
                        "keywords": [
                            "Sponsored Products",
                            "Placement report",
                            "Amazon Seller Central",
                            "ACOS optimization",
                            "Pivot table"
                        ]
                    },
                    {
                        "id": "advertising-sop-steps-to-reduction-of-wasted-spend-overspending-account",
                        "title": "Advertising SOP: Steps to Reduction of Wasted Spend (Overspending Account)",
                        "keywords": [
                            "Amazon Advertising",
                            "Search Term Negations",
                            "Bulk File Analysis",
                            "Down Only Bidding",
                            "ACOS Reduction"
                        ]
                    },
                    {
                        "id": "quick-reference-guide-uploading-keywords-and-bids-via-file-in-ppc-campaigns",
                        "title": "Quick Reference Guide: Uploading Keywords and Bids via File in PPC Campaigns",
                        "keywords": [
                            "PPC bulk upload",
                            "CSV keyword upload",
                            "Excel keyword upload",
                            "bid management",
                            "campaign keyword import"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-to-conduct-keyword-and-asin-research",
                        "title": "Advertising SOP: How to Conduct Keyword and ASIN Research",
                        "keywords": [
                            "Amazon keyword research",
                            "ASIN research",
                            "Helium 10 Cerebro",
                            "Brand Analytics",
                            "Amazon PPC"
                        ]
                    },
                    {
                        "id": "advertising-sop-sponsored-product-targeting-report",
                        "title": "Advertising SOP: Sponsored Product Targeting Report",
                        "keywords": [
                            "Sponsored Products",
                            "Targeting report",
                            "Amazon Advertising",
                            "ASIN targeting",
                            "Keyword targeting"
                        ]
                    },
                    {
                        "id": "advertising-sop-bulk-negation-tool",
                        "title": "Advertising SOP: Bulk Negation Tool",
                        "keywords": [
                            "Bulk Negation",
                            "Search Term Negation",
                            "Sponsored Products",
                            "Negative Keywords",
                            "ACOS Thresholds"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-to-find-skus-that-are-not-being-advertised",
                        "title": "Advertising SOP: How to find SKUs that are not being advertised",
                        "keywords": [
                            "Amazon PPC",
                            "SKU audit",
                            "Sponsored Products",
                            "Active Listing Report",
                            "Bulk file"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-advertising-bidding-strategies-work",
                        "title": "Advertising SOP: How Advertising Bidding Strategies Work",
                        "keywords": [
                            "Amazon ad bidding",
                            "Fixed bids",
                            "Dynamic bids",
                            "Rule-based bidding",
                            "ACOS optimization"
                        ]
                    },
                    {
                        "id": "catalog-sop-download-a-sales-dashboard-report",
                        "title": "Catalog SOP: Download a Sales Dashboard Report",
                        "keywords": [
                            "Sales Dashboard",
                            "Business Reports",
                            "Seller Central",
                            "Download CSV",
                            "Fulfillment Channel"
                        ]
                    },
                    {
                        "id": "advertising-sop-setting-up-a-budget-cap",
                        "title": "Advertising SOP: Setting Up a Budget Cap",
                        "keywords": [
                            "Amazon Advertising",
                            "Budget cap",
                            "Sponsored Products",
                            "Campaign daily budget",
                            "ACOS optimization"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-to-convert-up--down-bidding-strategy-account-to-down-only",
                        "title": "Advertising SOP: How to Convert Up & Down Bidding Strategy Account to Down Only",
                        "keywords": [
                            "Amazon Advertising",
                            "Down Only bidding",
                            "Up & Down bidding",
                            "Bulk upload",
                            "CPC adjustment"
                        ]
                    },
                    {
                        "id": "advertising-sop-master-ads-sop-with-existing-campaigns",
                        "title": "Advertising SOP: Master Ads SOP (With Existing Campaigns)",
                        "keywords": [
                            "Amazon Ads SOP",
                            "Master Campaigns",
                            "ASIN segmentation",
                            "ACOS optimization",
                            "Sponsored Products strategy"
                        ]
                    },
                    {
                        "id": "advertising-sop-campaigns-in-every-account",
                        "title": "Advertising SOP: Campaigns in every Account",
                        "keywords": [
                            "Amazon PPC",
                            "ASIN grouping",
                            "Sponsored Products",
                            "Campaign structure",
                            "Sponsored Display"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-to-set-up-ad-campaigns-on-seller-central",
                        "title": "Advertising SOP: How to Set Up Ad Campaigns on Seller Central",
                        "keywords": [
                            "Seller Central ads",
                            "Amazon PPC",
                            "Sponsored Products",
                            "Down Only bidding",
                            "Competitor targeting"
                        ]
                    },
                    {
                        "id": "advertising-sop-analyzing-ad-account-using-restock-report",
                        "title": "Advertising SOP: Analyzing Ad Account using Restock Report",
                        "keywords": [
                            "Amazon FBA",
                            "Restock Report",
                            "Advertised Product Report",
                            "Ad account audit",
                            "Organic FBA sales"
                        ]
                    },
                    {
                        "id": "advertising-sop-amazon-advertising-reports",
                        "title": "Advertising SOP: Amazon Advertising Reports",
                        "keywords": [
                            "Amazon Advertising",
                            "Search Term Impression Share",
                            "Targeting Report",
                            "Budget Report",
                            "ACoS"
                        ]
                    },
                    {
                        "id": "advertising-sop-find-overoptimized-underoptimized-or-wasted-spend-targets-using-bulk",
                        "title": "Advertising SOP: Find Overoptimized, Underoptimized, or Wasted Spend Targets Using Bulk",
                        "keywords": [
                            "Amazon Advertising",
                            "Bulk File",
                            "Bid Optimization",
                            "ACoS Analysis",
                            "Wasted Ad Spend"
                        ]
                    },
                    {
                        "id": "advertising-sop-budget-rules",
                        "title": "Advertising SOP: Budget Rules",
                        "keywords": [
                            "Amazon PPC",
                            "Budget rules",
                            "ACOS optimization",
                            "Campaign budgeting",
                            "Ad spend automation"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-to-delete-scheduled-advertising-reports",
                        "title": "Advertising SOP: How to Delete Scheduled Advertising Reports",
                        "keywords": [
                            "Seller Central",
                            "Advertising Reports",
                            "Scheduled Reports",
                            "Report Deletion",
                            "Amazon Advertising"
                        ]
                    },
                    {
                        "id": "advertising-sop-negation-guidance",
                        "title": "Advertising SOP: Negation Guidance",
                        "keywords": [
                            "Search term negation",
                            "ASIN negation",
                            "Sponsored Products",
                            "ACOS threshold",
                            "Amazon ad optimization"
                        ]
                    },
                    {
                        "id": "advertising-sop-how-to-find-asin-based-acos-and-conversion-rate-in-ad-account",
                        "title": "Advertising SOP: How to find ASIN-based ACOS and Conversion Rate in Ad Account",
                        "keywords": [
                            "Amazon Advertising",
                            "ASIN ACOS",
                            "ASIN Conversion Rate",
                            "Campaign Manager",
                            "Seller Central"
                        ]
                    }
                ]
            }
        }
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
