import os
from azure.storage.blob import BlobServiceClient

def upload_files_to_azure(storage_connection_string, container_name, source_folder):
    blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    for root, _, files in os.walk(source_folder):
        for file in files:
            file_path = os.path.join(root, file)
            blob_path = os.path.relpath(file_path, source_folder)

            print(f"Uploading {file_path} to {blob_path} in container {container_name}")
            with open(file_path, "rb") as data:
                container_client.upload_blob(name=blob_path, data=data, overwrite=True)

if __name__ == "__main__":
    STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")
    SOURCE_FOLDER = "./manifests"

    upload_files_to_azure(STORAGE_CONNECTION_STRING, CONTAINER_NAME, SOURCE_FOLDER)
