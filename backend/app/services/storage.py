from minio import Minio
import os
import uuid

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET_NAME = "trainflow-videos"

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def ensure_bucket_exists():
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)

def upload_file(file_obj, filename, content_type):
    ensure_bucket_exists()
    
    # Generate unique object name
    ext = filename.split('.')[-1]
    unique_name = f"{uuid.uuid4()}.{ext}"
    
    # Reset file pointer
    file_obj.seek(0)
    
    # Get size
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(0)
    
    client.put_object(
        BUCKET_NAME,
        unique_name,
        file_obj,
        size,
        content_type=content_type
    )
    return unique_name

def get_file_url(object_name):
    # Generates a presigned URL (valid for 1 hour by default)
    # Note: In docker network, "minio:9000" might not be reachable from browser 
    # so we might need to adjust endpoint or proxy it. 
    # For internal processing, minio:9000 is fine.
    return client.presigned_get_object(BUCKET_NAME, object_name)
