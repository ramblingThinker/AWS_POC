# Dockerfile

# Use the official Python Alpine image
FROM python:3.9-alpine

# Set non-sensitive environment variables.
# For sensitive data like VAULT_SERVICE_TOKEN, it is strongly
# recommended to pass them at runtime using `docker run -e`.
ENV VAULT_ADDR='https://8200-port-ec6bdvhfidnlyeyz.labs.kodekloud.com/' \
    AWS_REGION='us-east-1'

# Set the working directory inside the container
WORKDIR /app

# Install build dependencies and curl, then copy the requirements file.
# The build dependencies (build-base, etc.) are needed to compile
# Python packages with C extensions during the `pip install` step.
# `curl` is needed for the HEALTHCHECK command.
RUN apk add --no-cache \
    curl \
    build-base \
    libffi-dev \
    openssl-dev

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir reduces the image size.
RUN pip install --no-cache-dir -r requirements.txt

# Remove the temporary build dependencies to keep the final image size minimal.
# This is a crucial step for creating a lean Alpine-based image.
RUN apk del build-base libffi-dev openssl-dev

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Health check to ensure the application is running correctly
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s CMD curl -f http://localhost:8000/ || exit 1

# Command to run the application using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]