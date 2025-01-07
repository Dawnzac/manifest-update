from pathlib import Path
import hashlib
import requests
from azure.storage.blob import BlobServiceClient

# Constants
DOWNLOAD_FOLDER = "./manifests"
APPS_FILE = "apps.txt"
AZURE_STORAGE_CONNECTION_STRING = "<Your Azure Storage Connection String>"
AZURE_CONTAINER_NAME = "<Your Azure Container Name>"

def calculate_file_hash(file_path):
    """Calculate the SHA256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_blob_hash(blob_client):
    """Retrieve the SHA256 hash of a blob."""
    try:
        blob_data = blob_client.download_blob().readall()
        return hashlib.sha256(blob_data).hexdigest()
    except Exception as e:
        print(f"Error fetching blob hash: {e}")
        return None

def upload_to_azure(file_path, blob_name):
    """Upload a file to Azure Blob Storage only if it has changed."""
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=blob_name)

    # Calculate file hash
    local_file_hash = calculate_file_hash(file_path)
    print(f"Local file hash for {file_path}: {local_file_hash}")

    # Compare with the existing blob's hash
    existing_blob_hash = get_blob_hash(blob_client)
    if existing_blob_hash:
        print(f"Existing blob hash for {blob_name}: {existing_blob_hash}")
        if local_file_hash == existing_blob_hash:
            print(f"No changes detected for {blob_name}. Skipping upload.")
            return

    # Upload the file if it has changed or doesn't exist
    try:
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        print(f"Uploaded {file_path} to Azure Blob Storage as {blob_name}")
    except Exception as e:
        print(f"Error uploading {file_path}: {e}")

def main():
    # Ensure download folder exists
    Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

    # Read apps from the txt file
    if not Path(APPS_FILE).exists():
        print(f"Error: {APPS_FILE} not found!")
        return

    with open(APPS_FILE, "r") as f:
        apps = [line.strip() for line in f if line.strip()]
    
    if not apps:
        print("Error: No apps found in the apps.txt file!")
        return

    # Process each app
    for app_id in apps:
        manifest_url = get_latest_version_url(app_id)
        if manifest_url:
            downloaded_file = download_manifest(manifest_url, app_id)
            if downloaded_file:
                # Define blob name based on file path
                blob_name = f"manifests/{app_id}.installer.yaml"
                # Upload to Azure if the file has changed
                upload_to_azure(downloaded_file, blob_name)

if __name__ == "__main__":
    main()
