# s3_manager.py
import boto3
import logging
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from typing import Dict, List, Any, Optional
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class S3Manager:
    """
    Manages AWS S3 bucket operations (create, list, delete, empty).
    """
    # Define instance variables with type hints
    region_name: str
    _s3_client: BaseClient

    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, region_name: str, aws_session_token: Optional[str] = None):
        self.region_name = region_name
        self._s3_client = self._initialize_s3_client(
            aws_access_key_id, aws_secret_access_key, aws_session_token)

    def _initialize_s3_client(self, access_key: str, secret_key: str, session_token: Optional[str] = None) -> BaseClient:
        """Initializes and returns an S3 client."""
        s3_client_kwargs: Dict[str, Any] = {  # Added type hint for s3_client_kwargs
            'aws_access_key_id': access_key,
            'aws_secret_access_key': secret_key,
            'region_name': self.region_name
        }
        if session_token:
            s3_client_kwargs['aws_session_token'] = session_token
            logger.info(
                "Initializing S3 client with temporary STS credentials.")
        else:
            logger.info("Initializing S3 client with static AWS credentials.")

        return boto3.client('s3', **s3_client_kwargs)

    def create_bucket(self, bucket_name: str) -> bool:
        """
        Creates an S3 bucket with the specified name in the given region.
        """
        logger.info(
            f"Attempting to create S3 bucket: '{bucket_name}' in region: '{self.region_name}'")
        try:
            if self.region_name == 'us-east-1':
                self._s3_client.create_bucket(Bucket=bucket_name)
            else:
                self._s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': self.region_name}
                )
            logger.info(f"S3 bucket '{bucket_name}' created successfully.")
            return True
        except ClientError as e:
            error_code: str = e.response.get(
                "Error", {}).get("Code")  # Added type hint
            error_message: str = e.response.get(
                "Error", {}).get("Message")  # Added type hint
            logger.error(
                f"Failed to create S3 bucket '{bucket_name}'. AWS ClientError: Code={error_code}, Message={error_message}", exc_info=True)
            if error_code == 'BucketAlreadyOwnedByYou':
                logger.warning(
                    f"Bucket '{bucket_name}' already exists and is owned by you. Considering it successful.")
                return True
            elif error_code == 'BucketAlreadyExists':
                logger.error(
                    f"Bucket '{bucket_name}' already exists and is owned by another account. Cannot create.")
                return False
            elif error_code == 'AccessDenied':
                logger.error(
                    f"Access Denied: The provided AWS credentials do not have permission to create buckets in '{self.region_name}'.")
                return False
            elif error_code == 'InvalidAccessKeyId' or error_code == 'SignatureDoesNotMatch':
                logger.error(
                    f"Invalid AWS credentials. Check the credentials provided to S3Manager.")
                return False
            else:
                return False
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred while creating S3 bucket '{bucket_name}': {e}")
            return False

    def list_buckets(self) -> List[Dict[str, Any]]:
        """
        Lists all S3 buckets in the AWS account.
        """
        logger.info("Attempting to list S3 buckets.")
        # Added type hint
        response: Dict[str, Any] = self._s3_client.list_buckets()

        buckets_list: List[Dict[str, Any]] = []  # Added type hint
        for bucket in response.get('Buckets', []):
            buckets_list.append({
                "Name": bucket.get('Name'),
                "CreationDate": bucket.get('CreationDate').isoformat() if bucket.get('CreationDate') else None
            })

        logger.info(f"Successfully listed {len(buckets_list)} S3 buckets.")
        return buckets_list

    def empty_bucket(self, bucket_name: str) -> None:
        """
        Deletes all objects and object versions from an S3 bucket.
        Required before deleting the bucket itself.
        """
        logger.info(f"Attempting to empty S3 bucket: '{bucket_name}'")
        try:
            # List all objects
            objects: Dict[str, Any] = self._s3_client.list_objects_v2(
                Bucket=bucket_name)  # Added type hint
            if 'Contents' in objects:
                delete_keys: List[Dict[str, str]] = [
                    # Added type hint
                    {'Key': obj['Key']} for obj in objects['Contents']]
                self._s3_client.delete_objects(Bucket=bucket_name, Delete={
                                               'Objects': delete_keys})
                logger.info(
                    f"Deleted {len(delete_keys)} objects from '{bucket_name}'.")

            # List all object versions (for versioned buckets)
            versions: Dict[str, Any] = self._s3_client.list_object_versions(
                Bucket=bucket_name)  # Added type hint
            if 'Versions' in versions:
                delete_versions: List[Dict[str, str]] = [
                    # Added type hint
                    {'Key': v['Key'], 'VersionId': v['VersionId']} for v in versions['Versions']]
                self._s3_client.delete_objects(Bucket=bucket_name, Delete={
                                               'Objects': delete_versions})
                logger.info(
                    f"Deleted {len(delete_versions)} versions from '{bucket_name}'.")

            if 'DeleteMarkers' in versions:
                delete_markers: List[Dict[str, str]] = [
                    # Added type hint
                    {'Key': dm['Key'], 'VersionId': dm['VersionId']} for dm in versions['DeleteMarkers']]
                self._s3_client.delete_objects(Bucket=bucket_name, Delete={
                                               'Objects': delete_markers})
                logger.info(
                    f"Deleted {len(delete_markers)} delete markers from '{bucket_name}'.")

            logger.info(f"S3 bucket '{bucket_name}' successfully emptied.")

        except ClientError as e:
            error_code: str = e.response.get("Error", {}).get("Code")
            error_message: str = e.response.get("Error", {}).get("Message")
            logger.error(
                f"AWS ClientError while emptying bucket '{bucket_name}': Code={error_code}, Message={error_message}"
            )
            raise e
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred while emptying bucket '{bucket_name}': {e}")
            raise e

    def delete_bucket(self, bucket_name: str) -> None:
        """
        Deletes an S3 bucket after emptying it.
        Raises HTTPException if the bucket cannot be deleted.
        """
        logger.info(f"Attempting to delete S3 bucket: '{bucket_name}'")

        try:
            # First, empty the bucket
            self.empty_bucket(bucket_name)

            # Then, delete the bucket
            self._s3_client.delete_bucket(Bucket=bucket_name)
            logger.info(f"S3 bucket '{bucket_name}' successfully deleted.")
        except ClientError as e:
            error_code: str = e.response.get("Error", {}).get("Code")
            error_message: str = e.response.get("Error", {}).get("Message")
            logger.error(
                f"AWS ClientError occurred during S3 bucket deletion: Code={error_code}, Message={error_message}"
            )
            if error_code == 'NoSuchBucket':
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Bucket '{bucket_name}' not found.")
            elif error_code == 'AccessDenied':
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail=f"Access denied to delete bucket '{bucket_name}'. Check AWS permissions.")
            elif error_code == 'BucketNotEmpty':
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"Bucket '{bucket_name}' is not empty after emptying attempt. Manual verification needed.")
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail=f"AWS ClientError during deletion: Code={error_code}, Message={error_message}")
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred during S3 bucket deletion: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"An unexpected error occurred: {e}")
