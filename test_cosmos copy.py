import os
import requests
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GitHub and download settings
GITHUB_PULL_API_URL = "https://api.github.com/repos/microsoft/winget-pkgs/pulls"
HEADERS = {"Accept": "application/vnd.github+json"}
WINGET_REPO = "https://api.github.com/repos/microsoft/winget-pkgs/contents/manifests"
WINGET_REPO_RAW_URL = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests"
DOWNLOAD_FOLDER = "manifests"
SAVE_FILE = "recent_merged_prs.json"

# Azure Blob and Service Bus settings
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
QUEUE_NAME = os.getenv("QUEUE_NAME", "patchjob")  # Default to "patchjob" if not set

# Cosmos DB settings (for fetching app IDs)
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER")

#########################
# Cosmos DB Integration #
#########################

from azure.cosmos import CosmosClient, exceptions

def load_apps_from_cosmos():
    """
    Load app names from Azure Cosmos DB using the SQL API.
    Each document is expected to have an 'AppID' field.
    """
    if not (COSMOS_ENDPOINT and COSMOS_KEY and COSMOS_DATABASE and COSMOS_CONTAINER):
        print("Cosmos DB environment variables are not set!")
        return set()

    try:
        client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
        database = client.get_database_client(COSMOS_DATABASE)
        container = database.get_container_client(COSMOS_CONTAINER)
        
        query = "SELECT c.AppID FROM c"
        apps = set()
        for item in container.query_items(query=query, enable_cross_partition_query=True):
            app_id = item.get("AppID")
            if app_id:
                apps.add(app_id.strip())
        print(f"Loaded {len(apps)} apps from Cosmos DB.")
        return apps
    except exceptions.CosmosHttpResponseError as e:
        print(f"Error querying Cosmos DB: {e}")
        return set()

#########################
# GitHub and Manifest    #
#########################

from packaging.version import Version

def get_latest_version_url(app_id):
    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    api_url = f"{WINGET_REPO}/{app_path}"
    manifest_url = f"{WINGET_REPO_RAW_URL}/{app_path}"
    
    print(f"Fetching manifest data from: {api_url}")
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        versions = [
            {"name": item["name"], "sha": item["sha"]}
            for item in data
            if item["type"] == "dir" and any(char.isdigit() for char in item["name"])
        ]
        if not versions:
            print(f"No versions found for {app_id}")
            return None
        latest_version_info = max(versions, key=lambda v: Version(v["name"]))
        latest_version = latest_version_info["name"]
        latest_sha = latest_version_info["sha"]
        latest_url = f"{manifest_url}/{latest_version}/{app_id}.installer.yaml"
        print(f"Latest manifest URL for {app_id}: {latest_url}")
        print(f"SHA for latest version: {latest_sha}")
        return latest_url, latest_version
    else:
        print(f"Failed to fetch data from GitHub API. Status code: {response.status_code}")
        return None

def download_manifest(manifest_url, app_id, latest_version):
    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    app_download_folder = Path(DOWNLOAD_FOLDER) / app_path / latest_version
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

def send_service_bus_message(app_name, app_version, blob_url):
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
    service_bus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
    message_content = {
        "ApplicationName": app_name,
        "ApplicationVersion": app_version,
        "BlobUrl": blob_url,
    }
    # Adding a custom property "status"
    message = ServiceBusMessage(
        json.dumps(message_content),
        application_properties={"status": "Updated"}
    )
    
    try:
        with service_bus_client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            sender.send_messages(message)
        print(f"Message sent to Service Bus: {message_content} with status 'Updated'")
    except Exception as e:
        print(f"Error sending message to Service Bus: {e}")

def upload_to_azure(file_path, blob_name, latest_version, app_id):
    from azure.storage.blob import BlobServiceClient
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
        send_service_bus_message(app_id, latest_version, blob_name)
    except Exception as e:
        print(f"Error uploading {file_path}: {e}")

#########################
# Merged PRs Functions   #
#########################

def save_to_file(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Data saved to {filename}")

def load_from_file(filename):
    try:
        with open(filename, "r") as f:
            data = json.load(f)
        print(f"Data loaded from {filename}")
        return data
    except FileNotFoundError:
        print(f"{filename} not found. Returning an empty list.")
        return []

def fetch_merged_pull_requests():
    last_24_hours = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    print(f"Fetching PRs merged since: {last_24_hours}")

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
                if merged_at_dt > last_24_hours:
                    recent_merged_prs.append(pr)
                    all_prs_outdated = False

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

#########################
# Main Function          #
#########################

def main():
    # Load apps from Cosmos DB instead of a text file
    apps = load_apps_from_cosmos()  # This returns a set of app IDs from Cosmos DB

    if not apps:
        print("Error: No apps found in Cosmos DB!")
        return

    Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

    # For testing: Load recent merged PRs from file; in production, you might fetch them fresh.
    recent_merged_prs = load_from_file(SAVE_FILE)
    if not recent_merged_prs:
        recent_merged_prs = fetch_merged_pull_requests()
        save_to_file(recent_merged_prs, SAVE_FILE)

    print(f"Found {len(recent_merged_prs)} merged PRs in the last 24 hours:")
    for pr in recent_merged_prs:
        title = pr.get("title")
        # Skip unwanted PRs
        if title.startswith("Automatic deletion of ") or title.startswith("Remove version "):
            print(title)
            continue
        if title.startswith("Automatic update of "):
            print(title)
            continue
        if title.startswith("New version") or title.startswith("Update"):
            # Extract app_id from the title. For example: "New version: Headlamp.Headlamp version 0.27.0"
            match = re.search(r":\s([\w.-]+)\sversion", title)
            if match:
                app_id = match.group(1).strip()
                print(f"Extracted AppID: {app_id}")
            else:
                app_id = title[len("New version "):].split()[0]
                print(f"Fallback AppID extraction: {app_id}")

            if app_id in apps:
                print(f"PR Title: {title}")
                print(f"App Name: {app_id} is found in Cosmos DB")
                result = get_latest_version_url(app_id)
                if result:
                    manifest_url, latest_version = result
                    downloaded_file = download_manifest(manifest_url, app_id, latest_version)
                    if downloaded_file:
                        updated_downloaded_file = str(downloaded_file).replace("\\", "/")
                        blob_name = "/".join(updated_downloaded_file.split("/", 1)[1:])
                        print(f"Blob_name: {blob_name}")
                        upload_to_azure(downloaded_file, blob_name, latest_version, app_id)
                        print()
            else:
                print(f"App Name: {app_id} not found in Cosmos DB, Skipping......")

if __name__ == "__main__":
    main()

