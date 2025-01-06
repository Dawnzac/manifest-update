import requests
import yaml
from pathlib import Path

WINGET_REPO = "https://api.github.com/repos/microsoft/winget-pkgs/contents/manifests"
WINGET_REPO_RAW_URL = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests"
DOWNLOAD_FOLDER = "manifests"

def get_latest_version_url(app_id):
    """
    Fetch the latest version manifest URL using GitHub API.
    """
    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    api_url = f"{WINGET_REPO}/{app_path}"
    manifest_url = f"{WINGET_REPO_RAW_URL}/{app_path}"
    
    print(f"Fetching manifest data from: {api_url}")
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        versions = [item['name'] for item in data if item['type'] == 'dir' and any(char.isdigit() for char in item['name'])]
        if not versions:
            print(f"No versions found for {app_id}")
            return None
        latest_version = versions[-1]
        latest_url = f"{manifest_url}/{latest_version}/{app_id}.installer.yaml"
        print(f"Latest manifest URL for {app_id}: {latest_url}")
        return latest_url
    else:
        print(f"Failed to fetch data from GitHub API. Status code: {response.status_code}")
        return None

def download_manifest(manifest_url, app_id):
    """
    Download the manifest file for the latest version of the app.
    """
    app_download_folder = Path(DOWNLOAD_FOLDER) / app_id
    app_download_folder.mkdir(parents=True, exist_ok=True)
    
    file_name = manifest_url.split('/')[-1]
    file_path = app_download_folder / file_name
    
    print(f"Downloading {manifest_url} to {file_path}...")
    response = requests.get(manifest_url)
    if response.status_code == 200:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(response.text)
        print(f"Downloaded {file_name} to {app_download_folder}")
        return file_path
    else:
        print(f"Failed to download {manifest_url}. HTTP status code: {response.status_code}")
        return None

def read_yaml_file(file_path):
    """
    Reads and parses the YAML file to ensure it is valid.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
            print(f"YAML file content for {file_path}:\n{data}")
            return data
    except Exception as e:
        print(f"Error reading YAML file {file_path}: {e}")
        return None

def main():
    # List of apps to fetch
    apps = ["Google.Chrome", "Microsoft.Edge"]

    # Ensure download folder exists
    Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

    for app_id in apps:
        manifest_url = get_latest_version_url(app_id)
        if manifest_url:
            downloaded_file = download_manifest(manifest_url, app_id)
            #if downloaded_file:
                # Verify and read the downloaded YAML file
                #read_yaml_file(downloaded_file)

if __name__ == "__main__":
    main()
