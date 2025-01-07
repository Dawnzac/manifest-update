import requests
#import yaml
from pathlib import Path
import os
import hashlib
from azure.storage.blob import BlobServiceClient


WINGET_REPO = "https://api.github.com/repos/microsoft/winget-pkgs/contents/manifests"
WINGET_REPO_RAW_URL = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests"
DOWNLOAD_FOLDER = "manifests"
APPS_FILE = "apps.txt"





def get_latest_version_url(app_id):
    """
    Fetch the latest version manifest URL using GitHub API.
    """
    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    api_url = f"{WINGET_REPO}/{app_path}"
    manifest_url = f"{WINGET_REPO_RAW_URL}/{app_path}"
    
    print(f"Fetching manifest data from: {api_url}")
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        versions = [item['name'] for item in data if item['type'] == 'dir' and any(char.isdigit() for char in item['name'])]
        if not versions:
            print(f"No versions found for {app_id}")
            return None
        latest_version = versions[-1]
        latest_url = f"{manifest_url}/{latest_version}/{app_id}.installer.yaml"
        print(f"Latest manifest URL for {app_id}: {latest_url}")
        return latest_url
    else:
        print(f"Failed to fetch data from GitHub API. Status code: {response.status_code}")
        return None

def download_manifest(manifest_url, app_id):
    """
    Download the manifest file for the latest version of the app.
    """
    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    app_download_folder = Path(DOWNLOAD_FOLDER) / app_path
    app_download_folder.mkdir(parents=True, exist_ok=True)
    
    file_name = manifest_url.split('/')[-1]
    file_path = app_download_folder / file_name
    
    print(f"Downloading {manifest_url} to {file_path}...")
    response = requests.get(manifest_url)
    if response.status_code == 200:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(response.text)
        print(f"Downloaded {file_name} to {app_download_folder}")
        return file_path
    else:
        print(f"Failed to download {manifest_url}. HTTP status code: {response.status_code}")
        return None


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


def read_yaml_file(file_path):
    """
    Reads and parses the YAML file to ensure it is valid.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            print(f"YAML file content for {file_path}:\n{data}")
            return data
    except Exception as e:
        print(f"Error reading YAML file {file_path}: {e}")
        return None

def main():

    # List of apps to fetch
    if not Path(APPS_FILE).exists():
        print(f"Error: {APPS_FILE} not found!")
        return

    with open(APPS_FILE, "r") as f:
        apps = [line.strip() for line in f if line.strip()]
    
    if not apps:
        print("Error: No apps found in the apps.txt file!")
        return

    Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

    for app_id in apps:
        manifest_url = get_latest_version_url(app_id)
        if manifest_url:
            downloaded_file = download_manifest(manifest_url, app_id)
            if downloaded_file:
                blob_name = f"manifests/{app_id}.installer.yaml"
                # Upload to Azure if the file has changed
                upload_to_azure(downloaded_file, blob_name)

                # Verify and read the downloaded YAML file
                #read_yaml_file(downloaded_file)

if __name__ == "__main__":
    STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
    #SOURCE_FOLDER = "./manifests"

    main()
