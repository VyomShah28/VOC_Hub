import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import uuid
import os

s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION_NAME
)

def ensure_bucket_exists():
    """Ensure the S3 bucket exists, if not, create it."""
    try:
        s3_client.head_bucket(Bucket=settings.AWS_S3_BUCKET_NAME)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            try:
                # If us-east-1, LocationConstraint must not be specified
                if settings.AWS_REGION_NAME == 'us-east-1':
                    s3_client.create_bucket(Bucket=settings.AWS_S3_BUCKET_NAME)
                else:
                    s3_client.create_bucket(
                        Bucket=settings.AWS_S3_BUCKET_NAME,
                        CreateBucketConfiguration={
                            'LocationConstraint': settings.AWS_REGION_NAME
                        }
                    )
                print(f"[S3] Created bucket: {settings.AWS_S3_BUCKET_NAME}")
            except Exception as create_err:
                print(f"[S3] Failed to create bucket: {create_err}")
        else:
            print(f"[S3] Error accessing bucket: {e}")

def upload_file_to_s3(file_bytes: bytes, original_filename: str) -> str:
    """
    Uploads a file directly to S3 and returns the S3 key (path).
    """
    ensure_bucket_exists()
    
    file_extension = os.path.splitext(original_filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    s3_key = f"knowledge_base/{unique_filename}"
    
    try:
        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType="application/pdf"
        )
        return s3_key
    except Exception as e:
        print(f"[S3] Upload failed: {e}")
        raise e

def generate_presigned_url(s3_key: str, expiration=3600, inline: bool = False, filename: str = None) -> str:
    """
    Generate a presigned URL to securely download or view the file directly from S3.
    """
    try:
        params = {
            'Bucket': settings.AWS_S3_BUCKET_NAME,
            'Key': s3_key
        }
        
        if inline:
            params['ResponseContentDisposition'] = 'inline'
            params['ResponseContentType'] = 'application/pdf'
        elif filename:
            params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'
            
        response = s3_client.generate_presigned_url(
            'get_object',
            Params=params,
            ExpiresIn=expiration
        )
        return response
    except Exception as e:
        print(f"[S3] Presigned URL generation failed: {e}")
        raise e
