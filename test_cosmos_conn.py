from azure.cosmos import CosmosClient

import os


from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("COSMOS_ENDPOINT")
PRIMARY_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("COSMOS_DATABASE")
CONTAINER_NAME = os.getenv("COSMOS_CONTAINER")

print(f"Endpoint: {ENDPOINT}")
print(f"Primary Key: {PRIMARY_KEY[:5]}... (masked)")
print(f"Database: {DATABASE_NAME}")
print(f"Container: {CONTAINER_NAME}")


client = CosmosClient(ENDPOINT, PRIMARY_KEY)

# List all databases
databases = [db['id'] for db in client.list_databases()]
print("Databases:", databases)

# Verify if the database exists
if DATABASE_NAME in databases:
    database = client.get_database_client(DATABASE_NAME)
    containers = [c['id'] for c in database.list_containers()]
    print("Containers:", containers)

    if CONTAINER_NAME not in containers:
        print(f"⚠ Error: Container '{CONTAINER_NAME}' not found in database '{DATABASE_NAME}'")
else:
    print(f"⚠ Error: Database '{DATABASE_NAME}' does not exist.")
