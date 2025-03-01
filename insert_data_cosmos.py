from azure.cosmos import CosmosClient, exceptions
import os
from dotenv import load_dotenv

load_dotenv()

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER")

client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
container = client.get_database_client(COSMOS_DATABASE).get_container_client(COSMOS_CONTAINER)

def get_next_id():
    query = "SELECT MAX(c.id) FROM c"
    results = list(container.query_items(query=query, enable_cross_partition_query=True))

    if not results or results[0]['$1'] is None:
        return 1
    return int(results[0]['$1']) + 1

try:

    next_id = get_next_id()
    print(f"Next ID: {next_id}")


    with open('apps.txt', 'r') as file:
        for line in file:
            appId = line.strip()
            item = {
                "id": str(next_id),
                "packageIdentifier": appId,
                "appId": appId
            }

            container.create_item(body=item)

            next_id += 1

    print("✅ Bulk data inserted successfully!")

except exceptions.CosmosHttpResponseError as e:
    print(f"❌ Error inserting data: {e}")
