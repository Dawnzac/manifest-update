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

# Specify the entity to delete
partition_key = "AppPartition"
row_key = "1"

try:
    # Delete the entity
    table_client.delete_entity(partition_key=partition_key, row_key=row_key)
    print(f"Entity with PartitionKey='{partition_key}' and RowKey='{row_key}' deleted successfully!")
except Exception as e:
    print(f"Error deleting entity: {e}")
