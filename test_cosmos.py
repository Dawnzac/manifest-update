import os
import requests
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time
from dotenv import load_dotenv

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
    Each document is expected to have an 'appId' field.
    """
    if not (COSMOS_ENDPOINT and COSMOS_KEY and COSMOS_DATABASE and COSMOS_CONTAINER):
        print("Cosmos DB environment variables are not set!")
        return set()

    try:
        client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
        database = client.get_database_client(COSMOS_DATABASE)
        container = database.get_container_client(COSMOS_CONTAINER)
        
        query = "SELECT c.appId FROM c"
        apps = set()
        for item in container.query_items(query=query, enable_cross_partition_query=True):
            app_id = item.get("appId")
            if app_id:
                apps.add(app_id.strip())
        print(f"Loaded {len(apps)} apps from Cosmos DB.")
        return apps
    except exceptions.CosmosHttpResponseError as e:
        print(f"Error querying Cosmos DB: {e}")
        return set()


def main():

    apps = load_apps_from_cosmos()  

    if not apps:
        print("Error: No apps found in Cosmos DB!")
        return
    for a in apps:
        print(a)
        print("\n\n")

if __name__ == "__main__":
    main()

