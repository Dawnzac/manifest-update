import requests
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time

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

    apps = load_apps_from_file(APPS_FILE)
    recent_merged_prs = []
    params = {
        "state": "closed",
        "per_page": 100,
        "page": 1
    }
    start_time = time.time()
    while True:
        response = requests.get(GITHUB_PULL_API_URL, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"Failed to fetch PRs: {response.status_code} - {response.text}")
            break

        prs = response.json()
        all_prs_outdated = True

        # Filter PRs merged within the last 24 hours
        for pr in prs:
            merged_at = pr.get("merged_at")
            print(merged_at)
            if merged_at:
                merged_at_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                if merged_at_dt > last_24_hours and merged_at is not None:
                    recent_merged_prs.append(pr)
                    all_prs_outdated = False
                else:
                    continue
        if all_prs_outdated:
            print("All remaining PRs are older than 24 hours. Stopping pagination.")
            break

        # Check if there are more pages
        if "next" in response.links:
            params["page"] += 1
        else:
            break

    end_time = time.time()
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

    execution_time = end_time - start_time
    print(f"Time taken for Fetch: {execution_time:.4f} seconds")


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