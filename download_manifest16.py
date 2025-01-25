import requests
import json
from pathlib import Path
import os
import hashlib
from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from packaging.version import Version
from azure.data.tables import TableServiceClient, UpdateMode
from dotenv import load_dotenv
load_dotenv()

GITHUB_PULL_API_URL = "https://api.github.com/repos/microsoft/winget-pkgs/pulls"
HEADERS = {"Accept": "application/vnd.github+json"}

WINGET_REPO = "https://api.github.com/repos/microsoft/winget-pkgs/contents/manifests"
WINGET_REPO_RAW_URL = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests"
DOWNLOAD_FOLDER = "manifests"

STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
#QUEUE_NAME = "winget-update"
QUEUE_NAME = "patchjob"

TABLE_NAME = "wingetapptest"
PARTITION_KEY = "Apps"


#for testing purpose only remove for production

SAVE_FILE = "api_response.json"

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

#Testing code ends


def load_apps_from_table():
    try:
        table_service_client = TableServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
        table_client = table_service_client.get_table_client(TABLE_NAME)

        apps = set()
        for entity in table_client.list_entities():
            app_id = entity.get("AppID")
            if app_id:
                # Ensure all required fields exist
                updated = False
                if not entity.get("version"):
                    entity["version"] = ""
                    updated = True
                if not entity.get("Blobpath"):
                    entity["Blobpath"] = ""
                    updated = True
                if not entity.get("githubpath"):
                    entity["githubpath"] = ""
                    updated = True
                if not entity.get("hash"):
                    entity["hash"] = ""
                    updated = False
                if not entity.get("gitsha"):
                    entity["gitsha"] = ""
                    updated = True

                if updated:
                    table_client.update_entity(mode=UpdateMode.MERGE, entity=entity)
                    print(f"Updated missing fields for AppID: {app_id}")

                apps.add(app_id.strip())

        print(f"\033[33mLoaded {len(apps)} apps from Azure Table Storage.\n \n \033[0m")
        return apps, table_client
    except Exception as e:
        print(f"\033[31mError loading apps from Azure Table Storage: {e}\033[0m")
        return set(), None

def update_entity(table_client, app_id, version=None, blob_path=None, github_path=None, hash_value=None, git_sha=None):
    try:
        entity = table_client.get_entity(partition_key=PARTITION_KEY, row_key=app_id)

        # Update the fields if provided
        if version:
            entity["version"] = version
        if blob_path:
            entity["Blobpath"] = blob_path
        if github_path:
            entity["githubpath"] = github_path
        if hash_value:
            entity["hash"] = hash_value
        if git_sha:
            entity["gitsha"] = git_sha

        table_client.update_entity(mode=UpdateMode.MERGE, entity=entity)
        print(f"Updated entity for AppID: {app_id}")
    except Exception as e:
        print(f"Error updating entity for AppID: {app_id}: {e}")


def get_latest_version_url(app_id):

    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    api_url = f"{WINGET_REPO}/{app_path}"
    manifest_url = f"{WINGET_REPO_RAW_URL}/{app_path}"
    
    print(f"Fetching manifest data from: {api_url}")
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        versions = [{"name": item["name"], "sha": item["sha"]} for item in data if item['type'] == 'dir' and any(char.isdigit() for char in item['name'])]
        if not versions:
            print(f"No versions found for {app_id}")
            return None
        latest_version_info = max(versions, key=lambda v: Version(v["name"]))
        latest_version = latest_version_info["name"]
        latest_sha = latest_version_info["sha"]
        latest_url = f"{manifest_url}/{latest_version}/{app_id}.installer.yaml"
        print(f"\033[33mLatest manifest URL for {app_id}: {latest_url}\033[0m")
        return latest_url, latest_version, latest_sha
    else:
        print(f"\033[31mFailed to fetch data from GitHub API. Status code: {response.status_code}\033[0m")
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
        print(f"\033[32mDownloaded {file_name} to {app_download_folder}\033[0m")
        return file_path
    else:
        print(f"\033[31mFailed to download {manifest_url}. HTTP status code: {response.status_code}\033[0m")
        return None

#Azure Stuff - checking if file already exist with file Hash

def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_blob_hash(table_client, app_id):
    try:
        entity = table_client.get_entity(partition_key="Apps", row_key=app_id)
        
        hash_value = entity.get("gitsha")
        if hash_value:
            return hash_value
        else:
            print(f"\033[35mNo Git Commit hash value found for AppID {app_id}\033[0m")
            return None
    except Exception as e:
        print(f"\033[31mError fetching hash from Azure Table for AppID {app_id}: {e}\033[0m")
        return None
        
#Azure service Bus

def send_service_bus_message(app_name,latest_version ,blob_url, manifest_url, status):
    service_bus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
    message_content = {
        "ApplicationName": app_name,
        "ApplicationVersion": latest_version,
        "BlobUrl": blob_url,
        "GithubUrl": manifest_url,
    }
    message = ServiceBusMessage(json.dumps(message_content),
        application_properties={"status": status})
    
    try:
        with service_bus_client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            sender.send_messages(message)
        print(f"\033[34mMessage sent to Service Bus: {message_content} with status: {status}\033[0m")
    except Exception as e:
        print(f"\033[31mError sending message to Service Bus: {e}\033[0m")


def upload_to_azure(file_path, blob_name, latest_version, app_id, table_client, manifest_url, latest_sha):
    blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)

    try:
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        print(f"\033[36mUploaded {file_path} to Azure Blob Storage as {blob_name}\033[0m")
        update_entity(table_client, app_id, version=latest_version, blob_path=blob_name, github_path=manifest_url, hash_value=None, git_sha=latest_sha)
        status="Update"
        send_service_bus_message(app_id, latest_version, blob_name, manifest_url, status)
    except Exception as e:
        print(f"\033[31mError uploading {file_path}: {e}\033[0m")




def main():


    apps, table_client = load_apps_from_table()

    #for testing purpuse only
    #api_response_save = load_from_file(SAVE_FILE)



#testing code ends

    if not apps:
        print("\033[31mError: No apps found in Azure Table Storage!\033[0m")
        return

    Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)


    for app_id in apps:
        manifest_url, latest_version, latest_sha = get_latest_version_url(app_id)
        if manifest_url:

            local_file_hash = latest_sha
            print(f"Latest git commit hash for {app_id}: {local_file_hash}")

            existing_blob_hash = get_blob_hash(table_client, app_id)
            #existing_blob_hash = get_blob_hash2(blob_client)
            if existing_blob_hash:
                print(f"Existing blob hash for {app_id}: {existing_blob_hash}")
                if local_file_hash == existing_blob_hash:
                    #update_entity(table_client, app_id, version=latest_version, blob_path=blob_name, github_path=manifest_url, hash_value=None, git_sha=latest_sha)
                    print(f"\033[33mNo changes detected for {app_id}. Skipping upload.\033[0m")
                    print("\n\n")
                    continue

            print("\033[32mNew Commit detected !! \033[0m\n")
            downloaded_file = download_manifest(manifest_url, app_id, latest_version) 
            if downloaded_file:
                updated_downloaded_file = str(downloaded_file).replace("\\", "/")
                blob_name = "/".join(updated_downloaded_file.split("/", 1)[1:])
                print(f"Blob_name : {blob_name}")
                upload_to_azure(downloaded_file, blob_name, latest_version, app_id, table_client, manifest_url, latest_sha) #and hope it's a new version :/ (for now)
                print("\n\n")


if __name__ == "__main__":

    main()
