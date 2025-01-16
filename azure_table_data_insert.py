from azure.data.tables import TableServiceClient
from azure.core.credentials import AzureNamedKeyCredential
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Retrieve variables from environment
STORAGE_ACCOUNT_NAME = os.getenv("STORAGE_ACCOUNT_NAME")
STORAGE_ACCOUNT_KEY = os.getenv("STORAGE_ACCOUNT_KEY")
TABLE_NAME = os.getenv("AZURE_TABLE_NAME")

# Validate that variables are loaded
if not STORAGE_ACCOUNT_NAME or not STORAGE_ACCOUNT_KEY or not TABLE_NAME:
    raise ValueError("Missing environment variables. Check your .env file.")

# Create a credential object
credential = AzureNamedKeyCredential(STORAGE_ACCOUNT_NAME, STORAGE_ACCOUNT_KEY)

# Connect to the Table Service
service_client = TableServiceClient(
    endpoint=f"https://{STORAGE_ACCOUNT_NAME}.table.core.windows.net",
    credential=credential
)

# Get a reference to the table
table_client = service_client.get_table_client(TABLE_NAME)

# Insert an entity with the desired fields
entity = {
    "PartitionKey": "Apps",  # Logical grouping
    "RowKey": "2",  # Unique identifier for the entity
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
