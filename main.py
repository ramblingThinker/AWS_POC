# main.py
from dotenv import load_dotenv
import os
import datetime
import random
import logging
from logging.handlers import RotatingFileHandler
import contextlib
from typing import Optional  # Import Optional for global variables

from fastapi import FastAPI, HTTPException, status, Body

# Import the new classes
from vault_client import VaultClient
from s3_manager import S3Manager

# Load environment variables from .env file
load_dotenv(override=True)

# --- Configure Logging ---
current_script_dir: str = os.path.dirname(
    os.path.abspath(__file__))  # Added type hint
log_file_path: str = os.path.join(
    current_script_dir, 'app.log')  # Added type hint

logger: logging.Logger = logging.getLogger(__name__)  # Added type hint
logger.setLevel(logging.INFO)

console_handler: logging.StreamHandler = logging.StreamHandler()  # Added type hint
formatter: logging.Formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')  # Added type hint
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler: RotatingFileHandler = RotatingFileHandler(
    log_file_path, maxBytes=5 * 1024 * 1024, backupCount=2)  # Added type hint
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# --- End Logging Configuration ---

# Configuration from environment variables
VAULT_ADDR: str = os.getenv(
    'VAULT_ADDR', 'http://127.0.0.1:8200')  # Added type hint
VAULT_SERVICE_TOKEN: Optional[str] = os.getenv(
    'VAULT_SERVICE_TOKEN')  # Added type hint
AWS_CREDS_VAULT_KV_PATH: str = "aws/credentials"  # Added type hint
AWS_CREDS_VAULT_MOUNT: str = "secrets"  # Added type hint
AWS_REGION: str = os.getenv('AWS_REGION', 'us-east-1')  # Added type hint

# Declare global variables for instances with Optional type hints
vault_client_instance: Optional[VaultClient] = None
s3_manager_instance: Optional[S3Manager] = None

# --- Lifespan Context Manager ---


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles the startup and shutdown events for the FastAPI application.
    Initializes VaultClient and S3Manager during startup.
    """
    global vault_client_instance, s3_manager_instance
    logger.info("Application lifespan: Startup initiated.")

    try:
        # Initialize VaultClient
        vault_client_instance = VaultClient(
            vault_addr=VAULT_ADDR,
            # type: ignore # Mypy might complain here if VAULT_SERVICE_TOKEN is Optional[str] but VaultClient expects str
            vault_token=VAULT_SERVICE_TOKEN,
            vault_mount=AWS_CREDS_VAULT_MOUNT,
            vault_path=AWS_CREDS_VAULT_KV_PATH
        )

        # Retrieve AWS credentials
        # Added type hint
        aws_creds: Dict[str, str] = vault_client_instance.get_aws_credentials()

        # Initialize S3Manager
        s3_manager_instance = S3Manager(
            aws_access_key_id=aws_creds['access_key'],
            aws_secret_access_key=aws_creds['secret_access_key'],
            region_name=AWS_REGION,
            aws_session_token=aws_creds.get(
                'security_token') or aws_creds.get('session_token')
        )
        logger.info(
            "VaultClient and S3Manager initialized successfully during startup.")

    except ValueError as e:
        logger.critical(
            f"FATAL: Failed to initialize application due to Vault/Credential issue: {e}")
        raise RuntimeError(f"Application startup failed: {e}")
    except Exception as e:
        logger.critical(
            f"FATAL: An unexpected error occurred during application startup: {e}")
        raise RuntimeError(f"Application startup failed: {e}")

    yield

    logger.info("Application lifespan: Shutting down.")
    logger.info("Application lifespan: Shutdown complete.")

# --- Initialize FastAPI app with lifespan ---
app = FastAPI(
    title="FastAPI: Vault & S3 Management (OOP)",
    description="A FastAPI application leveraging OOP to manage AWS S3 buckets "
                "with credentials retrieved from HashiCorp Vault.",
    lifespan=lifespan
)


# --- FastAPI Endpoints ---

@app.get("/")
async def read_root():
    """
    Root endpoint. Provides general information about the application.
    """
    logger.info("Accessed root endpoint.")
    return {"message": "Welcome to the FastAPI App. Use /docs for API documentation."}


@app.get("/generate-unique-bucket-name")
async def generate_unique_bucket_name_api():
    """
    Generates a globally unique S3 bucket name suggestion based on timestamp and random string,
    ensuring it conforms to AWS S3 bucket naming rules (lowercase, no underscores).
    """
    timestamp: str = datetime.datetime.now().strftime(
        '%Y%m%d%H%M%S%f')[:-3]  # Added type hint
    random_str: str = ''.join(random.choices(
        'abcdefghijklmnopqrstuvwxyz0123456789', k=6))  # Added type hint
    # Added type hint
    suggested_name: str = f"my-app-s3-kv2-{timestamp}-{random_str}".lower(
    ).replace('_', '-')
    logger.info(f"Generated unique bucket name suggestion: {suggested_name}")
    return {"suggested_bucket_name": suggested_name}


@app.post("/create-s3-bucket")
async def create_s3_bucket_endpoint(
    bucket_name: str = Body(..., embed=True,
                            description="The name of the S3 bucket to create. Must be globally unique.")
):
    """
    Creates a new S3 bucket using credentials managed by the S3Manager.
    """
    logger.info(f"Received request to create S3 bucket: '{bucket_name}'")
    if s3_manager_instance is None:  # Explicit check for None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="S3 Manager not initialized.")

    success: bool = s3_manager_instance.create_bucket(
        bucket_name)  # Added type hint
    if success:
        return {"message": f"Bucket '{bucket_name}' creation initiated successfully in region '{AWS_REGION}'."}
    else:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create bucket '{bucket_name}'. Check logs for details.")


@app.get("/list-s3-buckets")
async def list_s3_buckets_api():
    """
    Lists all S3 buckets in the AWS account using credentials managed by the S3Manager.
    """
    logger.info("Attempting to list S3 buckets.")
    if s3_manager_instance is None:  # Explicit check for None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="S3 Manager not initialized.")

    try:
        # Added type hint
        buckets: List[Dict[str, Any]] = s3_manager_instance.list_buckets()
        return {"buckets": buckets}
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during S3 bucket listing: {e}")
        if isinstance(e, HTTPException):
            raise e
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"An unexpected error occurred: {e}")


@app.delete("/delete-s3-bucket/{bucket_name}")
async def delete_s3_bucket_api(bucket_name: str):
    """
    Deletes an S3 bucket after emptying it, using credentials managed by the S3Manager.
    Note: Deleting a bucket is a destructive operation and cannot be undone.
    """
    logger.info(f"Received request to delete S3 bucket: '{bucket_name}'")
    if s3_manager_instance is None:  # Explicit check for None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="S3 Manager not initialized.")

    try:
        s3_manager_instance.delete_bucket(bucket_name)
        return {"message": f"S3 bucket '{bucket_name}' deleted successfully."}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during S3 bucket deletion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An unexpected error occurred: {e}")


# --- Main execution block for Uvicorn ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI application via uvicorn...")
    logger.info(f"Vault Address (from ENV): {VAULT_ADDR}")
    logger.info(
        f"Vault Service Token (from ENV): {'Set' if VAULT_SERVICE_TOKEN else 'NOT SET - Vault/AWS operations will fail!'}")
    logger.info(f"Vault KV Mount: {AWS_CREDS_VAULT_MOUNT}")
    logger.info(f"Vault KV Path: {AWS_CREDS_VAULT_KV_PATH}")
    logger.info(f"AWS Region (from ENV): {AWS_REGION}")
    logger.info(f"Logs will be written to: {log_file_path}")

    if not VAULT_SERVICE_TOKEN:
        logger.critical(
            "\n!!! WARNING: VAULT_SERVICE_TOKEN environment variable is NOT SET. Vault and AWS S3 operations will fail! !!!\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
