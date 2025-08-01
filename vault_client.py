# vault_client.py
import os
import hvac
import logging
# Import Optional for attributes that might be None initially
from typing import Dict, Union, Optional

logger = logging.getLogger(__name__)


class VaultClient:
    """
    A client to interact with HashiCorp Vault for retrieving secrets.
    """
    # Define instance variables with type hints
    vault_addr: str
    vault_token: str
    vault_mount: str
    vault_path: str
    _client: hvac.Client  # Internal HVAC client instance

    def __init__(self, vault_addr: str, vault_token: str, vault_mount: str, vault_path: str):
        self.vault_addr = vault_addr
        self.vault_token = vault_token
        self.vault_mount = vault_mount
        self.vault_path = vault_path
        # Initialize _client during instantiation
        self._client = self._initialize_client()

    def _initialize_client(self) -> hvac.Client:
        """Initializes and returns an HVAC client."""
        if not self.vault_token:
            logger.error(
                "VAULT_SERVICE_TOKEN is not set. Cannot initialize Vault client.")
            raise ValueError("VAULT_SERVICE_TOKEN must be provided.")

        client = hvac.Client(url=self.vault_addr, token=self.vault_token)
        if not client.is_authenticated():
            logger.error(
                "Failed to authenticate to Vault. Check VAULT_SERVICE_TOKEN validity/expiration.")
            raise hvac.exceptions.VaultError(
                "Failed to authenticate to Vault with service token.")

        logger.info("Successfully initialized and authenticated HVAC client.")
        return client

    def get_aws_credentials(self) -> Dict[str, str]:
        """
        Retrieves AWS credentials from the configured Vault KV path.
        """
        logger.info(
            f"Attempting to retrieve AWS credentials from Vault path: {self.vault_mount}/data/{self.vault_path}")

        try:
            read_response: Dict[str, Any] = self._client.secrets.kv.v2.read_secret_version(  # Added type hint for read_response
                path=self.vault_path,
                mount_point=self.vault_mount
            )

            if read_response and 'data' in read_response and 'data' in read_response['data']:
                # Added type hint for credentials
                credentials: Dict[str, str] = read_response['data']['data']
                if not credentials.get('access_key') or not credentials.get('secret_access_key'):
                    logger.error(
                        "AWS credentials obtained from Vault are incomplete (missing access_key or secret_access_key).")
                    raise ValueError(
                        "Incomplete AWS credentials retrieved from Vault.")

                logger.info(
                    f"Successfully retrieved AWS credentials from Vault path: {self.vault_mount}/{self.vault_path}")
                return credentials
            else:
                logger.error(
                    f"No data found at Vault path: {self.vault_mount}/data/{self.vault_path} or secret structure is unexpected.")
                raise ValueError(
                    f"Failed to retrieve data from Vault path: {self.vault_mount}/data/{self.vault_path}")

        except hvac.exceptions.VaultError as e:
            logger.exception(
                f"Vault error occurred during credential retrieval: {e}")
            # Added type hint for error_detail
            error_detail: str = f"Vault error: {e}"
            if "forbidden" in str(e).lower():
                error_detail += f". Check if VAULT_SERVICE_TOKEN has 'read' capabilities on '{self.vault_mount}/data/{self.vault_path}'."
            elif "connection refused" in str(e).lower():
                error_detail = "Vault connection refused. Is Vault running and accessible at the specified address?"
            elif "unauthorized" in str(e).lower():
                error_detail = "Vault authentication failed (token may be expired or invalid)."
            elif "not found" in str(e).lower() and "404" in str(e).lower():
                error_detail = f"Vault path '{self.vault_mount}/data/{self.vault_path}' not found. Check the path and mount point."
            raise ValueError(error_detail)
        except Exception as e:
            logger.exception(
                f"An unexpected error occurred while reading from Vault: {e}")
            raise ValueError(f"Internal error while fetching from Vault: {e}")
