import requests
import json
from pathlib import Path
import os
import hashlib
from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from packaging.version import Version
from azure.data.tables import TableServiceClient, UpdateMode
import sys
import logging
from dotenv import load_dotenv
load_dotenv()


DOWNLOAD_FOLDER = "homebrew"

STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
SERVICE_BUS_CONNECTION_STRING = os.getenv("SERVICE_BUS_CONNECTION_STRING")
#QUEUE_NAME = "winget-update"
QUEUE_NAME = "patchjob"
TABLE_NAME = "wingetapptest"
PARTITION_KEY = "Apps"




logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




CASK_BASE_URL = "https://raw.githubusercontent.com/Homebrew/homebrew-cask/HEAD/Casks"

def get_app_names_from_table() -> list:
    """
    Connect to the Azure Table and retrieve a list of app names.
    Assumes that each entity has at least an 'AppName' property.
    """
    if not STORAGE_CONNECTION_STRING:
        logger.error("STORAGE_CONNECTION_STRING is not set.")
        sys.exit(1)

    table_service = TableServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    table_client = table_service.get_table_client(TABLE_NAME)
    
    app_names = []
    logger.info("Retrieving app names from Azure Table: %s", TABLE_NAME)
    try:
        entities = table_client.list_entities()
        for entity in entities:
            # Assuming the column name is 'AppName'
            if "AppName" in entity:
                app_names.append(entity["AppName"])
            else:
                logger.warning("Entity %s does not have an 'AppName' property.", entity)
    except Exception as e:
        logger.error("Error retrieving entities from table: %s", e)
        sys.exit(1)

    logger.info("Found %d app(s) in the table.", len(app_names))
    return app_names

def download_cask_file(app_name: str) -> str:
    """
    Downloads the cask file from GitHub for the given app name.
    Returns the file content (as text) if successful.
    """
    url = f"{CASK_BASE_URL}/{app_name}.rb"
    logger.info("Downloading cask file for '%s' from %s", app_name, url)
    try:
        response = requests.get(url)
        response.raise_for_status()
        logger.info("Successfully downloaded cask for '%s'.", app_name)
        return response.text
    except requests.RequestException as e:
        logger.error("Failed to download cask for '%s': %s", app_name, e)
        return None

def upload_to_blob(app_name: str, content: str) -> bool:
    """
    Uploads the provided content as a blob (named <app_name>.rb) to the specified container.
    Returns True if the upload is successful.
    """
    if not STORAGE_CONNECTION_STRING:
        logger.error("STORAGE_CONNECTION_STRING is not set.")
        return False

    blob_service_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)

    # Create container if it does not exist
    try:
        container_client.create_container()
        logger.info("Created blob container '%s'.", CONTAINER_NAME)
    except Exception:
        pass

    blob_name = f"{app_name}.rb"
    blob_client = container_client.get_blob_client(blob=blob_name)
    try:
        logger.info("Uploading blob '%s' to container '%s'.", blob_name, CONTAINER_NAME)
        blob_client.upload_blob(content, overwrite=True)
        logger.info("Uploaded '%s' successfully.", blob_name)
        return True
    except Exception as e:
        logger.error("Failed to upload blob '%s': %s", blob_name, e)
        return False

def send_service_bus_message(app_name: str, status: str):

    if not SERVICE_BUS_CONNECTION_STRING:
        logger.error("SERVICE_BUS_CONNECTION_STRING is not set.")
        return

    message_text = f"App '{app_name}': {status}"
    logger.info("Sending service bus message: %s", message_text)
    try:
        with ServiceBusClient.from_connection_string(conn_str=SERVICE_BUS_CONNECTION_STRING) as sb_client:
            sender = sb_client.get_queue_sender(queue_name=QUEUE_NAME)
            with sender:
                message = ServiceBusMessage(message_text)
                sender.send_messages(message)
        logger.info("Service bus message sent for '%s'.", app_name)
    except Exception as e:
        logger.error("Failed to send service bus message for '%s': %s", app_name, e)

def process_app(app_name: str):
    cask_content = download_cask_file(app_name)
    if cask_content is None:
        #send_service_bus_message(app_name, "Download failed")
        return

    if upload_to_blob(app_name, cask_content):
        send_service_bus_message(app_name, "Upload successful")
    else:
        send_service_bus_message(app_name, "Upload failed")

def main():
    app_names = get_app_names_from_table()
    if not app_names:
        logger.error("No app names found; exiting.")
        return

    for app in app_names:
        process_app(app)

if __name__ == "__main__":
    main()
