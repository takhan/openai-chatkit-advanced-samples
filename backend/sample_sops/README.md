# Sample SOP Files for Seller Assistant

This directory contains sample Standard Operating Procedure (SOP) JSON files for testing the Seller Assistant chatbot.

## Sample SOPs

1. **sop-handling-returns.json** - Customer Service category
   - Covers the process for handling customer returns on Amazon
   - Includes steps for authorization, refunds, and inventory management

2. **sop-fba-prep.json** - Fulfillment category
   - Details FBA preparation and shipping requirements
   - Covers packaging standards, labeling, and common mistakes

3. **sop-listing-optimization.json** - Product Listings category
   - Guide for optimizing Amazon product listings for search
   - Includes title, bullets, images, and keyword research strategies

## JSON Structure

Each SOP JSON file follows this structure:

```json
{
  "id": "unique-sop-identifier",
  "title": "Human-readable SOP title",
  "category": "Category name",
  "keywords": ["keyword1", "keyword2", "..."],
  "content": "Full SOP content in markdown format",
  "images": [
    "s3://bucket-name/path/to/image1.jpg",
    "s3://bucket-name/path/to/image2.jpg"
  ],
  "last_updated": "YYYY-MM-DD"
}
```

## Uploading to S3 for Testing

### Option 1: Upload via AWS CLI

```bash
# Upload SOP files
aws s3 cp sop-handling-returns.json s3://seller-assistant-sops/sops/sop-handling-returns.json
aws s3 cp sop-fba-prep.json s3://seller-assistant-sops/sops/sop-fba-prep.json
aws s3 cp sop-listing-optimization.json s3://seller-assistant-sops/sops/sop-listing-optimization.json

# Upload placeholder images (create placeholder images first)
aws s3 cp placeholder.jpg s3://seller-assistant-images/returns/return-dashboard.jpg
aws s3 cp placeholder.jpg s3://seller-assistant-images/returns/authorize-return.jpg
# ... etc
```

### Option 2: Upload via AWS Console

1. Log into AWS Console
2. Navigate to S3
3. Create buckets:
   - `seller-assistant-sops` (for SOP JSON files)
   - `seller-assistant-images` (for images)
4. Create folder structure:
   - `seller-assistant-sops/sops/`
   - `seller-assistant-images/returns/`
   - `seller-assistant-images/fba/`
   - `seller-assistant-images/listings/`
5. Upload JSON files to the `sops/` folder
6. Upload images to their respective folders

### Option 3: Mock Mode (for Local Testing)

Modify `backend/app/sops.py` to use local files instead of S3:

```python
async def get_sop(self, sop_id: str) -> SOP | None:
    """Fetch SOP from local file system for testing."""
    try:
        local_path = f"sample_sops/{sop_id}.json"
        with open(local_path, 'r') as f:
            content = f.read()
        sop_data = json.loads(content)
        sop = SOP.from_dict(sop_data)
        # For local testing, use placeholder images or local paths
        sop.images = ["https://via.placeholder.com/800x600" for _ in sop.images]
        return sop
    except Exception as e:
        logger.error(f"Failed to load local SOP: {str(e)}")
        return None
```

## Testing with Placeholder Images

If you don't have actual images yet, you can use placeholder services:

- https://via.placeholder.com/800x600
- https://placehold.co/800x600
- https://dummyimage.com/800x600

Replace the S3 image URLs in the JSON files with placeholder URLs for initial testing.

## Adding More SOPs

To add more SOPs to the system:

1. Create a new JSON file following the structure above
2. Add the SOP entry to the Table of Contents in `backend/app/sops.py` (in the `_get_default_toc()` method)
3. Upload the JSON file to S3 (or keep it local for testing)
4. Upload any associated images to S3

## Image Requirements

- Format: JPG or PNG
- Recommended size: 800x600 or larger
- Should clearly illustrate the step or concept being explained
- Named descriptively for easy reference
