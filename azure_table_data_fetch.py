import os
from dotenv import load_dotenv
from azure.data.tables import TableServiceClient
from azure.core.credentials import AzureNamedKeyCredential

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
#entities = table_client.list_entities()


def get_blob_hash(table_client, app_id):
    try:
        entity = table_client.get_entity(partition_key="Apps", row_key=app_id)
        
        hash_value = entity.get("hash")
        if hash_value:
            print(f"Hash value for AppID {app_id}: {hash_value}")
            return hash_value
        else:
            print(f"No hash value found for AppID {app_id}")
            return None
    except Exception as e:
        print(f"Error fetching hash from Azure Table for AppID {app_id}: {e}")
        return None
    

def fetch_data():
    try:
        print(f"Reading data from table '{TABLE_NAME}':")
        entities = table_client.list_entities()
        for entity in entities:
            print(entity)
    except Exception as e:
        print(f"Error reading table: {e}")

def main():
    #fetch_data()
    hash = get_blob_hash(table_client,app_id="DigitalOcean.Doctl")
    print(hash)

if __name__ == "__main__":
    main()