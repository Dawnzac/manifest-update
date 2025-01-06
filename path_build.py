import requests
from pathlib import Path

WINGET_REPO = "https://api.github.com/repos/microsoft/winget-pkgs/contents/manifests"
WINGET_REPO_RAW_URL = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests"
#DOWNLOAD_FOLDER = "manifests"

def get_latest_version_url(app_id):

    app_path = f"{app_id[0].lower()}/{app_id.replace('.', '/')}"
    api_url = f"{WINGET_REPO}/{app_path}"
    manifest_url = f"{WINGET_REPO_RAW_URL}/{app_path}"

    print(f"Fetching manifest data from: {api_url}\n")
    response = requests.get(api_url)
    if response.status_code == 200:
        data = response.json()
        versions = [item['name'] for item in data if item['type'] == 'dir' and any(char.isdigit() for char in item['name'])]
        if not versions:
            print(f"No versions found for {app_id}")
            return None
        latest_version = versions[-1]
        latest_url = f"{manifest_url}/{latest_version}/{app_id}.installer.yaml"
        print(f"Latest manifest URL for {app_id}: {latest_url}\n")
        return latest_url
    else:
        print(f"Failed to fetch data from GitHub API. Status code: {response.status_code}")
        return None
    

def main():
    # List of apps to fetch
    apps = ["Google.Chrome","Google.AndroidStudio","Google.EarthPro"]

    # Ensure download folder exists
    #Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

    for app_id in apps:
        manifest_url = get_latest_version_url(app_id)
        #print(manifest_url)

if __name__ == "__main__":
    main()