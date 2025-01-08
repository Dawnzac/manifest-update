import requests
from datetime import datetime

# GitHub API URL for the winget public repository
GITHUB_API_URL = "https://api.github.com/repos/microsoft/winget-pkgs/pulls"
HEADERS = {"Accept": "application/vnd.github+json"}
apps_file = "apps.txt"

def load_apps_from_file(file_path):
    """Load app names from a text file."""
    with open(file_path, "r") as file:
        return {line.strip() for line in file if line.strip()}

def fetch_merged_pull_requests():
    """Fetch the latest merged pull requests from the winget public repository."""
    apps = load_apps_from_file(apps_file)
    params = {
        "state": "closed",  # Only closed pull requests
        "per_page": 10      # Fetch the latest 10 pull requests
    }
    
    response = requests.get(GITHUB_API_URL, headers=HEADERS, params=params)
    
    if response.status_code == 200:
        prs = response.json()
        merged_prs = [
            pr for pr in prs if pr.get("merged_at") is not None
        ]
        
        print(f"Latest Merged Pull Requests (winget-pkgs):\n")
        for pr in merged_prs:
            title = pr.get("title")
            if title.startswith("Automatic deletion of ") or title.startswith("Automatic update of "):
                continue
            #cleaned_title = title.split(":", 1)[-1].strip()
            if title.startswith("New version"):
                # Extract the app name from the title (assuming app name follows "New version ")
                app_name = title[len("New version "):].split()[0]  # Get the first word after "New version"
                if app_name in apps:
                    print(f"PR Title: {title}")
                    print(f"App Name: {app_name} is in apps.txt")
                    print(f"Merged At: {pr.get('merged_at')}")
                    print(f"URL: {pr.get('html_url')}")
                    print()
                else:
                    print(f"App Name: {app_name} not found in apps.txt")
            # Format and display information
            #merged_at_human = datetime.strptime(merged_at, "%Y-%m-%dT%H:%M:%SZ")
            #print(f"Title: {cleaned_title}")
            #print(f"Merged At: {merged_at_human.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            #print(f"URL: {url}")
            print("\n")
    else:
        print(f"Failed to fetch data: {response.status_code}")
        print(response.json())

if __name__ == "__main__":
    fetch_merged_pull_requests()
