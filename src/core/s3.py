"""
core/s3.py — S3 asset storage and pre-signed URL generation.
"""
import logging
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from core import config

logger = logging.getLogger(__name__)

s3_client = boto3.client("s3", region_name=config.AWS_REGION)

def upload_file(local_path: Path, s3_key: str, bucket: str = None, content_type: str = "video/mp4") -> str:
    bucket = bucket or config.OUTPUT_S3_BUCKET
    extra_args = {"ContentType": content_type}
    try:
        logger.info(f"Uploading {local_path} to s3://{bucket}/{s3_key}...")
        s3_client.upload_file(str(local_path), bucket, s3_key, ExtraArgs=extra_args)
        logger.info(f"Upload complete: s3://{bucket}/{s3_key}")
        return f"s3://{bucket}/{s3_key}"
    except ClientError as e:
        logger.error(f"Failed to upload to S3: {e}")
        raise

def generate_presigned_url(s3_key: str, bucket: str = None, expires_in: int = 86400) -> str:
    """Generate a pre-signed HTTPS URL valid for 24 hours (default)."""
    bucket = bucket or config.OUTPUT_S3_BUCKET
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=expires_in
        )
        return url
    except ClientError as e:
        logger.error(f"Failed to generate pre-signed URL: {e}")
        return ""

def upload_video_package(video_path: Path, thumbnail_path: Path = None, project_name: str = "short") -> dict:
    bucket = config.OUTPUT_S3_BUCKET
    video_key = f"renders/{project_name}/{video_path.name}"
    upload_file(video_path, video_key, bucket=bucket, content_type="video/mp4")
    video_url = generate_presigned_url(video_key, bucket=bucket)

    thumb_url = ""
    if thumbnail_path and thumbnail_path.exists():
        thumb_key = f"renders/{project_name}/{thumbnail_path.name}"
        upload_file(thumbnail_path, thumb_key, bucket=bucket, content_type="image/jpeg")
        thumb_url = generate_presigned_url(thumb_key, bucket=bucket)

    return {
        "s3_bucket": bucket,
        "video_s3_key": video_key,
        "video_download_url": video_url,
        "thumbnail_s3_key": thumb_key if thumb_url else "",
        "thumbnail_url": thumb_url
    }
