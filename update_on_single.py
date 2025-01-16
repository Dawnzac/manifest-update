import requests
import json
from pathlib import Path
import os
import hashlib
from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from datetime import datetime, timedelta, timezone
import time
import re


GITHUB_PULL_API_URL = "https://api.github.com/repos/microsoft/winget-pkgs/pulls"
HEADERS = {"Accept": "application/vnd.github+json"}

WINGET_REPO = "https://api.github.com/repos/microsoft/winget-pkgs/contents/manifests"
WINGET_REPO_RAW_URL = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests"
DOWNLOAD_FOLDER = "manifests"
APPS_FILE = "apps.txt"

STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
#QUEUE_NAME = "winget-update"
QUEUE_NAME = "patchjob"

#for testing purpose only remove for production

SAVE_FILE = "recent_merged_prs.json"

def save_to_file(data, filename):
    """Save data to a JSON file."""
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Data saved to {filename}")

def load_from_file(filename):
    """Load data from a JSON file."""
    try:
        with open(filename, "r") as f:
            data = json.load(f)
        print(f"Data loaded from {filename}")
        return data
    except FileNotFoundError:
        print(f"{filename} not found. Returning an empty list.")
        return []

#Testing code ends

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

def download_manifest(manifest_url, app_id, latest_version):

    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    app_download_folder = Path(DOWNLOAD_FOLDER) / app_path
    app_download_folder.mkdir(parents=True, exist_ok=True)
    
    file_name = manifest_url.split('/')[-1]
    file_path = app_download_folder / file_name / latest_version

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


def load_apps_from_file(file_path):
    """Load app names from a text file."""
    with open(file_path, "r") as file:
        return {line.strip() for line in file if line.strip()}

def fetch_merged_pull_requests():
    last_24_hours = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    print(f"last 24 Hours: {last_24_hours}")

    apps = load_apps_from_file(APPS_FILE)
    recent_merged_prs = []
    params = {
        "state": "closed",
        "per_page": 100,
        "page": 1
    }
    start_time = time.time()
    while True:
        response = requests.get(GITHUB_PULL_API_URL, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"Failed to fetch PRs: {response.status_code} - {response.text}")
            break

        prs = response.json()
        all_prs_outdated = True

        for pr in prs:
            merged_at = pr.get("merged_at")
            print(merged_at)
            if merged_at:
                merged_at_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                if merged_at_dt > last_24_hours and merged_at is not None:
                    recent_merged_prs.append(pr)
                    all_prs_outdated = False
                else:
                    continue
        if all_prs_outdated:
            print("All remaining PRs are older than 24 hours. Stopping pagination.")
            break

        if "next" in response.links:
            params["page"] += 1
        else:
            break

    end_time = time.time()
    
    execution_time = end_time - start_time
    print(f"Time taken for Fetch: {execution_time:.4f} seconds")
    return recent_merged_prs

def main():

    # List of apps to fetch
    if not Path(APPS_FILE).exists():
        print(f"Error: {APPS_FILE} not found!")
        return

    apps = load_apps_from_file(APPS_FILE)
    
    if not apps:
        print("Error: No apps found in the apps.txt file!")
        return

    Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

#for testing purpuse only
    recent_merged_prs = load_from_file(SAVE_FILE)

    # If no data is loaded, fetch from the API
    if not recent_merged_prs:
        recent_merged_prs = fetch_merged_pull_requests()
        save_to_file(recent_merged_prs, SAVE_FILE)

#testing code ends

    #recent_merged_prs = fetch_merged_pull_requests() #uncomment before using for production
    print(f"Latest Merged Pull Requests (winget-pkgs):\n")
    i = 1
    print(f"Found {len(recent_merged_prs)} merged PRs in the last 24 hours:")
    for pr in recent_merged_prs:
        title = pr.get("title")
        if title.startswith("Automatic deletion of ") or title.startswith("Remove version "):
            print(title)
            continue
        if title.startswith("Automatic update of "):
            print(title)
            continue
        if title.startswith("New version") or title.startswith("Update"):
            match = re.search(r":\s([\w.-]+)\sversion", title)
            if match:
                app_id = match.group(1).strip()
                print(app_id)
            else:
                app_id = title[len("New version "):].split()[0]
                print(f"Package name not found : {app_id}")
            #app_id = title[len("New version "):].split()[0]

            if app_id in apps:
                print(f"PR Title: {title}")
                print(f"App Name: {app_id} is in apps.txt")
                manifest_url, latest_version = get_latest_version_url(app_id)
                if manifest_url:
                    downloaded_file = download_manifest(manifest_url, app_id, latest_version) 
                    if downloaded_file:
                        updated_downloaded_file = str(downloaded_file).replace("\\", "/")
                        blob_name = "/".join(updated_downloaded_file.split("/", 1)[1:])
                        print(f"Blob_name : {blob_name}")
                        upload_to_azure(downloaded_file, blob_name, latest_version, app_id)
                        print()
            else:
                print(f"App Name: {app_id} not found in apps.txt,  Skipping...... ")


if __name__ == "__main__":

    main()
