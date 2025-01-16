from azure.data.tables import TableServiceClient
from azure.core.credentials import AzureNamedKeyCredential
from dotenv import load_dotenv
import os

load_dotenv()

STORAGE_ACCOUNT_NAME = os.getenv("STORAGE_ACCOUNT_NAME")
STORAGE_ACCOUNT_KEY = os.getenv("STORAGE_ACCOUNT_KEY")
TABLE_NAME = os.getenv("AZURE_TABLE_NAME")

if not STORAGE_ACCOUNT_NAME or not STORAGE_ACCOUNT_KEY or not TABLE_NAME:
    raise ValueError("Missing environment variables. Check your .env file.")


credential = AzureNamedKeyCredential(STORAGE_ACCOUNT_NAME, STORAGE_ACCOUNT_KEY)


service_client = TableServiceClient(
    endpoint=f"https://{STORAGE_ACCOUNT_NAME}.table.core.windows.net",
    credential=credential
)

table_client = service_client.get_table_client(TABLE_NAME)

entity = {
    "PartitionKey": "Apps",
    "RowKey": "2",  
    "AppID": "Google.Chrome",
    "version": "",
    "Blobpath": "",
    "githubpath": "",
    "hash": ""
}

try:
    table_client.create_entity(entity=entity)
    print("Entity inserted successfully!")
except Exception as e:
    print(f"Error inserting entity: {e}")
