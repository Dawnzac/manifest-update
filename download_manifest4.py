import os
import subprocess
from pathlib import Path
import requests
import shutil
import yaml

DOWNLOAD_FOLDER = "latest_manifests"
WINGET_REPO_RAW_URL = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests"

def get_latest_version_path(app_id):
    """
    Use `winget show <app_id> --versions` to get the latest version.
    """
    try:
        # Run the `winget show` command
        result = subprocess.run(
            ["winget", "show", app_id, "--versions"],
            capture_output=True,
            text=True,
            check=True
        )
        versions_output = result.stdout.strip()
        
        # Extract the list of versions
        versions = [
            line.strip() for line in versions_output.splitlines()
            if line.strip() and not line.startswith("Version") and not line.startswith("-")
        ]
        
        if not versions:
            print(f"No versions found for {app_id}.")
            return None
        
        # Use the latest version
        latest_version = versions[-1]
        print(f"Latest version for {app_id}: {latest_version}")
        
        # Construct the raw URL for the manifest file
        app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
        #print(f"App path : {app_path}")
        manifest_file = f"{app_id}.installer.yaml"
        latest_version_url = f"{WINGET_REPO_RAW_URL}/{app_path}/{latest_version}/{manifest_file}"
        return latest_version_url
    except subprocess.CalledProcessError as e:
        print(f"Error running winget command for {app_id}: {e}")
        return None

def download_manifest(manifest_url, app_id):
   
    app_download_folder = Path(DOWNLOAD_FOLDER) / app_id
    app_download_folder.mkdir(parents=True, exist_ok=True)
    
    file_name = manifest_url.split('/')[-1]
    file_path = app_download_folder / file_name
    
    print(f"Downloading {manifest_url} to {file_path}...")
    response = requests.get(manifest_url, stream=True)
    
    # Check response content type
    content_type = response.headers.get('Content-Type', '')
    if 'text' in content_type or 'yaml' in content_type:
        # Save as plain text
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(response.text)
        print(f"Downloaded {file_name} as plain text to {app_download_folder}")
    else:
        # Handle binary data or unexpected content
        print(f"Unexpected content type: {content_type}")
        return None
    
    return file_path

def read_yaml_file(file_path):

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
    apps = ["Microsoft.Edge"]

    # Ensure download folder exists
    Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

    for app_id in apps:
        manifest_url = get_latest_version_path(app_id)
        if manifest_url:
            downloaded_file = download_manifest(manifest_url, app_id)
            #if downloaded_file:
                # Verify and read the downloaded YAML file
                #read_yaml_file(downloaded_file)

if __name__ == "__main__":
    main()
