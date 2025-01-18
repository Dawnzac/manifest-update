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

file_path = "apps.txt"  # Path to your file
try:
    with open(file_path, "r") as file:
        app_names = [line.strip() for line in file if line.strip()]
except Exception as e:
    raise ValueError(f"Error reading app names from file: {e}")


try:
    for app_name in app_names:
            partition_key = "Apps" 
            row_key = app_name     

            try:
                existing_entity = table_client.get_entity(partition_key=partition_key, row_key=row_key)
                print(f"Entity with RowKey '{row_key}' already exists. Skipping insertion.")
                continue
            except Exception:
                pass

            # Construct the new entity
            entity = {
                "PartitionKey": partition_key,
                "RowKey": row_key,
                "AppID": app_name
            }

            # Insert the entity
            table_client.create_entity(entity=entity)
            print(f"Entity with RowKey '{row_key}' and AppID '{app_name}' inserted successfully.")
except Exception as e:
    print(f"Error inserting entities: {e}")