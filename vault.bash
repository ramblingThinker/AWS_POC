#!/bin/bash

# ================================================================
# HashiCorp Vault Demo Script (Updated with 'secrets enable')
#
# This script is designed to run on a machine where a HashiCorp
# Vault server is already running. It performs the following steps:
# 1. Authenticates by setting a VAULT_TOKEN environment variable.
# 2. Enables a new Key/Value (KV) v2 secret engine.
# 3. Writes a secret to the new KV v2 engine.
# 4. Reads the secret.
# 5. Provides the Vault token for external API use.
#
# This is for demonstration and development purposes only.
# ================================================================

# --- Step 1: Set environment variables for authentication ---
echo "--- Setting VAULT_TOKEN ---"
# Set this to match your running Vault instance.
# The token should be a valid token with appropriate permissions.
export VAULT_TOKEN='dev-only-token'
echo "VAULT_TOKEN set to: $VAULT_TOKEN"
echo ""

# --- Step 2: Enable a new KV v2 secret engine at the 'secrets' path ---
echo "--- Enabling KV v2 secret engine at 'secrets/' ---"
vault secrets enable -path=secrets kv-v2
if [ $? -ne 0 ]; then
    echo "Error: Failed to enable secret engine. Exiting."
    exit 1
fi
echo "KV v2 secret engine enabled successfully."
echo ""

# --- Step 3: Write a secret to the KV v2 engine ---
echo "--- Writing secret to 'secrets/aws/credentials' ---"
vault kv put secrets/aws/credentials access_key="********" secret_access_key="********"
if [ $? -ne 0 ]; then
    echo "Error: Failed to write secret. Exiting."
    exit 1
fi
echo "Secret written successfully."
echo ""

# --- Step 4: Read the secret and its metadata ---
echo "--- Reading secret from 'secrets/aws/credentials' ---"
# This command reads the secret and its metadata, demonstrating KV v2 functionality.
vault kv get secrets/aws/credentials
if [ $? -ne 0 ]; then
    echo "Error: Failed to read secret. Exiting."
    exit 1
fi
echo "Secret read successfully."
echo ""

# --- Step 5: Provide token for API use ---
echo "--- Vault Token for API use ---"
echo "Your Vault token is: $VAULT_TOKEN"
echo "You can use this token to authenticate API requests, for example:"
echo "curl --header 'X-Vault-Token: $VAULT_TOKEN' http://127.0.0.1:8200/v1/secrets/data/aws/credentials"
echo ""

echo "Script finished successfully."
