import requests
#import yaml
import json
from pathlib import Path
import os
import hashlib
from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage


WINGET_REPO = "https://api.github.com/repos/microsoft/winget-pkgs/contents/manifests"
WINGET_REPO_RAW_URL = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests"
DOWNLOAD_FOLDER = "test-manifest"
APPS_FILE = "apps.txt"

STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
QUEUE_NAME = "winget-update"



def get_latest_version_url(app_id):

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
        return latest_url, latest_version
    else:
        print(f"Failed to fetch data from GitHub API. Status code: {response.status_code}")
        return None

def download_manifest(manifest_url, app_id):

    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    app_download_folder = Path(DOWNLOAD_FOLDER) / app_path
    app_download_folder.mkdir(parents=True, exist_ok=True)
    
    file_name = manifest_url.split('/')[-1]
    #print(f'File name : {file_name}')

    file_path = app_download_folder / file_name
    #print(f'File path : {file_path}')

    #print(f'App Download folder : {app_download_folder}')

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

#Azure Stuff - checking if file already exist with file Hash

def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_blob_hash(blob_client):
    try:
        blob_data = blob_client.download_blob().readall()
        return hashlib.sha256(blob_data).hexdigest()
    except Exception as e:
        print(f"Error fetching blob hash: {e}")
        return None
    
#Azure service Bus

def send_service_bus_message(app_name, app_version, blob_url):
    service_bus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
    message_content = {
        "ApplicationName": app_name,
        "ApplicationVersion": app_version,
        "BlobUrl": blob_url,
    }
    message = ServiceBusMessage(json.dumps(message_content))
    
    try:
        with service_bus_client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            sender.send_messages(message)
        print(f"Message sent to Service Bus: {message_content}")
    except Exception as e:
        print(f"Error sending message to Service Bus: {e}")


def upload_to_azure(file_path, blob_name, latest_verion, app_id):
    blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)

    # Calculate file hash
    local_file_hash = calculate_file_hash(file_path)
    print(f"Local file hash for {file_path}: {local_file_hash}")

    existing_blob_hash = get_blob_hash(blob_client)
    if existing_blob_hash:
        print(f"Existing blob hash for {blob_name}: {existing_blob_hash}")
        if local_file_hash == existing_blob_hash:
            print(f"No changes detected for {blob_name}. Skipping upload.")
            return

    try:
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        print(f"Uploaded {file_path} to Azure Blob Storage as {blob_name}")
        send_service_bus_message(app_id, latest_verion, blob_name)
    except Exception as e:
        print(f"Error uploading {file_path}: {e}")


def read_yaml_file(file_path):
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
        manifest_url, latest_verion = get_latest_version_url(app_id)
        if manifest_url:
            downloaded_file = download_manifest(manifest_url, app_id)
            if downloaded_file:
                updated_downloaded_file = str(downloaded_file).replace("\\", "/")
                blob_name = "/".join(updated_downloaded_file.split("/", 1)[1:])
                #print(f"Blob_name : {blob_name}")
                upload_to_azure(downloaded_file, blob_name, latest_verion, app_id)
                print(QUEUE_NAME)

                # Verify and read the downloaded YAML file
                #read_yaml_file(downloaded_file)

if __name__ == "__main__":

    main()
