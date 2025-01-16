import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone

GITHUB_PULL_API_URL = "https://api.github.com/repos/microsoft/winget-pkgs/pulls"
HEADERS = {"Accept": "application/vnd.github+json"}
APPS_FILE = "apps.txt"

def load_apps_from_file(file_path):
    """Load app names from a text file."""
    with open(file_path, "r") as file:
        return {line.strip() for line in file if line.strip()}

def fetch_merged_pull_requests():
    last_24_hours = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    print(f"last 24 Hours: {last_24_hours}")
    dt = datetime.fromisoformat(last_24_hours)
    since_time = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Formatted PRs merged since: {since_time}")

    apps = load_apps_from_file(APPS_FILE)
    recent_merged_prs = []
    params = {
        "state": "closed",  # Only closed pull requests
        "per_page": 100,
        #"sort": "updated",
        #"direction": "desc",
        #"since": since_time ,
        "page": 1
    }
    
    while True:
        response = requests.get(GITHUB_PULL_API_URL, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"Failed to fetch PRs: {response.status_code} - {response.text}")
            break

        prs = response.json()

        # Filter PRs merged within the last 24 hours
        for pr in prs:
            merged_at = pr.get("merged_at")
            print(merged_at)
            recent_merged_prs.append(pr)

        # Check if there are more pages
        if 'next' in response.links:
            params['page'] += 1  # Move to the next page
        else:
            break
            
    print(f"Latest Merged Pull Requests (winget-pkgs):\n")
    i = 1
    print(f"Found {len(recent_merged_prs)} merged PRs in the last 24 hours:")
    for pr in recent_merged_prs:
        title = pr.get("title")
        if title.startswith("Automatic deletion of ") or title.startswith("Automatic update of "):
            print(f"PR Title: {title}")
            continue
        if title.startswith("New version") or title.startswith("Update"):
            app_id = title[len("New version "):].split()[0]
            if app_id in apps:
                print(f"PR Title: {title}")
                print(f"App Name: {app_id} is in apps.txt")
                print(f"Merged At: {pr.get('merged_at')}")
                print()
            else:
                print(f"App Name: {app_id} not found in apps.txt,  Skipping...... ")
                print(f"Merged At: {pr.get('merged_at')}")
        print( f"{i} -\n")
        i = i +1


def main():

    # List of apps to fetch
    if not Path(APPS_FILE).exists():
        print(f"Error: {APPS_FILE} not found!")
        return

    apps = load_apps_from_file(APPS_FILE)
    
    if not apps:
        print("Error: No apps found in the apps.txt file!")
        return

    fetch_merged_pull_requests()

if __name__ == "__main__":

    main()