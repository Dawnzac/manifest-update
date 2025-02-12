from azure.cosmos import CosmosClient, exceptions
import os
from dotenv import load_dotenv

load_dotenv()

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER")

def load_apps_from_cosmos():
    if not (COSMOS_ENDPOINT and COSMOS_KEY and COSMOS_DATABASE and COSMOS_CONTAINER):
        print("Error: One or more Cosmos DB environment variables are not set!")
        return set()

    try:
        # Create the Cosmos client
        client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
        database = client.get_database_client(COSMOS_DATABASE)
        container = database.get_container_client(COSMOS_CONTAINER)
        
        # Query to select the appId from each document
        query = "SELECT c.appId FROM c"
        apps = set()
        for item in container.query_items(query=query, enable_cross_partition_query=True):
            app_id = item.get("appId")
            if app_id:
                apps.add(app_id.strip())
        
        print(f"Loaded {len(apps)} apps from Cosmos DB.")
        return apps
    except exceptions.CosmosResourceNotFoundError as e:
        print(f"Error querying Cosmos DB: Resource not found. Please check your database and container names.\n{e}")
        return set()
    except Exception as e:
        print(f"Error querying Cosmos DB: {e}")
        return set()

# For testing purposes:
if __name__ == "__main__":
    apps = load_apps_from_cosmos()
    if apps:
        print("Apps loaded from Cosmos DB:")
        for app in apps:
            print(f" - {app}")
    else:
        print("No apps found in Cosmos DB!")
