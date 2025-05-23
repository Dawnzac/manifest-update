import requests
import json
from pathlib import Path
import os
from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from packaging.version import Version
from azure.cosmos import CosmosClient, exceptions
from dotenv import load_dotenv
load_dotenv()


API_URL = f"https://formulae.brew.sh/api"
DOWNLOAD_FOLDER = "homebrew"
APPS_FILE = "apps.txt"

STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
#QUEUE_NAME = "winget-update"
QUEUE_NAME = "hb-update"


COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER")



def load_apps_from_file(file_path):
    with open(file_path, "r") as file:
        return {line.strip() for line in file if line.strip()}


# def load_apps_from_cosmos():
#     if not (COSMOS_ENDPOINT and COSMOS_KEY and COSMOS_DATABASE and COSMOS_CONTAINER):
#         print("Error: One or more Cosmos DB environment variables are not set!")
#         return set()

#     try:
#         client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
#         database = client.get_database_client(COSMOS_DATABASE)
#         container = database.get_container_client(COSMOS_CONTAINER)
        
#         query = "SELECT * FROM c"
#         apps = set()
#         for item in container.query_items(query=query, enable_cross_partition_query=True):
#             app_id = item.get("appId")
#             doc_id = item.get("id")
            
#             if not doc_id:
#                 print(f"⚠️ Skipping document with missing 'id' for AppID: {app_id}")
#                 continue  
            
#             updated = False
            
#             for field in ["version", "Blobpath", "githubpath", "gitsha"]:
#                 if field not in item:
#                     item[field] = ""  
#                     updated = True

#             if updated:
#                 try:
#                     container.replace_item(item=doc_id, body=item)
#                     print(f"✅ Updated missing fields for AppID: {app_id}")
#                 except exceptions.CosmosHttpResponseError as e:
#                     print(f"❌ Error replacing document {doc_id}: {e}")


#             if app_id:
#                 #print(f"Debug : ", app_id)
#                 apps.add(app_id.strip())
        
#         print(f"Loaded {len(apps)} apps from Cosmos DB.")
#         return apps, client
#     except exceptions.CosmosResourceNotFoundError as e:
#         print(f"Error querying Cosmos DB: Resource not found. Please check your database and container names.\n{e}")
#         return set(), None
#     except Exception as e:
#         print(f"Error querying Cosmos DB: {e}")
#         return set(), None

# def update_entity(cosmos_client, app_id, version=None, blob_path=None, github_path=None, git_sha=None, database_name=COSMOS_DATABASE, container_name=COSMOS_CONTAINER):
#     try:
#         container = cosmos_client.get_database_client(database_name).get_container_client(container_name)

#         query = "SELECT * FROM c WHERE c.appId = @app_id"
#         parameters = [{"name": "@app_id", "value": app_id}]
        
#         #print(f"🔍 Querying for AppID: {app_id}")
#         results = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        
#         #Debugging:
#         #print(f"Query results: {results}")
        
#         if not results:
#             print(f"\033[31mError: No entity found for AppID: {app_id}\033[0m")
#             return

#         entity = results[0]
        
#         if version:
#             entity["version"] = version
#         if blob_path:
#             entity["Blobpath"] = blob_path
#         if github_path:
#             entity["githubpath"] = github_path
#         if git_sha:
#             entity["gitsha"] = git_sha

#         container.replace_item(item=entity, body=entity)

#         print(f"\033[32m✅ Updated entity for AppID: {app_id}\033[0m")

#     except exceptions.CosmosHttpResponseError as e:
#         print(f"\033[31m❌ Error updating entity for AppID {app_id}: {e}\033[0m")


# def get_latest_version_url(app_id):

#     app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
#     api_url = f"{WINGET_REPO}/{app_path}"
#     manifest_url = f"{WINGET_REPO_RAW_URL}/{app_path}"
    
#     print(f"Fetching manifest data from: {api_url}")
#     response = requests.get(api_url)
#     if response.status_code == 200:
#         data = response.json()
#         versions = [{"name": item["name"], "sha": item["sha"]} for item in data if item['type'] == 'dir' and any(char.isdigit() for char in item['name'])]
#         if not versions:
#             print(f"No versions found for {app_id}")
#             return None
#         latest_version_info = max(versions, key=lambda v: Version(v["name"]))
#         latest_version = latest_version_info["name"]
#         latest_sha = latest_version_info["sha"]
#         latest_url = f"{manifest_url}/{latest_version}/{app_id}.installer.yaml"
#         print(f"\033[33mLatest manifest URL for {app_id}: {latest_url}\033[0m")
#         return latest_url, latest_version, latest_sha
#     else:
#         print(f"\033[31mFailed to fetch data from GitHub API. Status code: {response.status_code}\033[0m")
#         return None

def get_sha256(response_json):

    try:
        sha256 = response_json.get("ruby_source_checksum", {}).get("sha256")

        if sha256:
            print(f"\033[32mSHA256 Checksum: {sha256}\033[0m")
            return sha256
        else:
            print("\033[31mSHA256 checksum not found in the manifest.\033[0m")
            return None

    except (KeyError, TypeError) as e:
        print(f"\033[31mError reading SHA256 checksum: {e}\033[0m")
        return None

def download_manifest(app_id):
    api_url = f"{API_URL}/cask/{app_id}.json"
    app_download_folder_formula = Path(DOWNLOAD_FOLDER) / "formula"
    app_download_folder_cask = Path(DOWNLOAD_FOLDER) / "cask"

    app_download_folder_formula.mkdir(parents=True, exist_ok=True)
    app_download_folder_cask.mkdir(parents=True, exist_ok=True)

    file_name = api_url.split('/')[-1]

    try:
        print(f"Downloading {app_id}...")  
        response = requests.get(f"{API_URL}/cask/{app_id}.json", timeout=10) 
        response.raise_for_status() 

        get_sha256(response.json())

        file_path = app_download_folder_cask / file_name
        formatted_json = json.dumps(response.json(), indent=4, ensure_ascii=False)
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(formatted_json)
        
        print(f"\033[32mDownloaded {file_name} to {app_download_folder_cask}\033[0m")
        return file_path

    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            print(f"\033[33m{app_id} not found in cask. Trying formula...\033[0m")
            try:
                file_path = app_download_folder_formula / file_name
                response = requests.get(f"{API_URL}/formula/{app_id}.json", timeout=10)
                response.raise_for_status() 
                formatted_json = json.dumps(response.json(), indent=4, ensure_ascii=False)

                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(formatted_json)

                print(f"\033[32mDownloaded {file_name} to {app_download_folder_formula}\033[0m")
                return file_path

            except requests.exceptions.RequestException as e:
                print(f"\033[31mFailed to download {app_id} from formula. Error: {e}\033[0m")
                return None

        print(f"\033[31mHTTP Error: {e}\033[0m") 
        return None

    except requests.exceptions.RequestException as e:
        print(f"\033[31mFailed to download {api_url}. Error: {e}\033[0m")
        return None

# #Azure Stuff - checking if file already exist with file Hash


# def get_blob_hash(cosmos_client, app_id, database_name=COSMOS_DATABASE, container_name=COSMOS_CONTAINER):
#     try:
#         container = cosmos_client.get_database_client(database_name).get_container_client(container_name)
        
#         query = f"SELECT c.gitsha FROM c WHERE c.appId = '{app_id}'"
        
#         results = list(container.query_items(query=query, enable_cross_partition_query=True))
        
#         if results:
#             hash_value = results[0].get("gitsha")
#             if hash_value:
#                 return hash_value
#             else:
#                 print(f"\033[35mNo Git Commit hash value found for AppID {app_id}\033[0m")
#                 return None
#         else:
#             print(f"\033[35mNo record found for AppID {app_id}\033[0m")
#             return None
#     except exceptions.CosmosHttpResponseError as e:
#         print(f"\033[31mError fetching hash from Cosmos DB for AppID {app_id}: {e}\033[0m")
#         return None
        
# #Azure service Bus

# def send_service_bus_message(app_name,latest_version ,blob_url, manifest_url, status):
#     service_bus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
#     message_content = {
#         "ApplicationName": app_name,
#         "ApplicationVersion": latest_version,
#         "BlobUrl": blob_url,
#         "GithubUrl": manifest_url,
#     }
#     message = ServiceBusMessage(json.dumps(message_content),
#         application_properties={"status": status})
    
#     try:
#         with service_bus_client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
#             sender.send_messages(message)
#         print(f"\033[34mMessage sent to Service Bus: {message_content} with status: {status}\033[0m")
#     except Exception as e:
#         print(f"\033[31mError sending message to Service Bus: {e}\033[0m")


# def upload_to_azure(file_path, blob_name, latest_version, app_id, CosmosClient, manifest_url, latest_sha):
#     blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
#     blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)

#     try:
#         blob_client.upload_blob(data, overwrite=True)
#         print(f"\033[36mUploaded {file_path} to Azure Blob Storage as {blob_name}\033[0m")
#         update_entity(CosmosClient, app_id, version=latest_version, blob_path=blob_name, github_path=manifest_url, git_sha=latest_sha)
#         status="Update"
#         send_service_bus_message(app_id, latest_version, blob_name, manifest_url, status)
#     except Exception as e:
#         print(f"\033[31mError uploading {file_path}: {e}\033[0m")




def main():


#     #apps, CosmosClient = load_apps_from_cosmos()

#     #List of apps to fetch
    if not Path(APPS_FILE).exists():
        print(f"Error: {APPS_FILE} not found!")
        return

    apps = load_apps_from_file(APPS_FILE)
    
    if not apps:
        print("Error: No apps found in the apps.txt file!")
        return

#     if not apps:
#         print("\033[31mError: No apps found in Azure Cosmos DB !\033[0m")
#         return

    Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)


    for app_id in apps:
        download_manifest(app_id)

#         manifest_url, latest_version, latest_sha = get_latest_version_url(app_id)
#         if manifest_url:

#             local_file_hash = latest_sha
#             print(f"Latest git commit hash for {app_id}: {local_file_hash}")

#             existing_blob_hash = get_blob_hash(CosmosClient, app_id)
#             #existing_blob_hash = get_blob_hash2(blob_client)
#             if existing_blob_hash:
#                 print(f"Existing blob hash for {app_id}: {existing_blob_hash}")
#                 if local_file_hash == existing_blob_hash:
#                     #update_entity(CosmosClient, app_id, version=latest_version, blob_path=blob_name, github_path=manifest_url, hash_value=None, git_sha=latest_sha)
#                     print(f"\033[33mNo changes detected for {app_id}. Skipping upload.\033[0m")
#                     print("\n\n")
#                     continue

#             print("\033[32mNew Commit detected !! \033[0m\n")
#             downloaded_file = download_manifest(manifest_url, app_id, latest_version) 
#             if downloaded_file:
#                 updated_downloaded_file = str(downloaded_file).replace("\\", "/")
#                 blob_name = "/".join(updated_downloaded_file.split("/", 1)[1:])
#                 print(f"Blob_name : {blob_name}")
#                 upload_to_azure(downloaded_file, blob_name, latest_version, app_id, CosmosClient, manifest_url, latest_sha) #and hope it's a new version :/ (for now)
#                 print("\n\n")


if __name__ == "__main__":

    main()
