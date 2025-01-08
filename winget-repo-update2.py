import requests

def get_latest_pull_requests(repo_owner, repo_name):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls?state=closed"
    response = requests.get(url)

    if response.status_code == 200:
        pull_requests = response.json()
        for pr in pull_requests:
            title = pr.get("title", "")
            
            # Skip PRs starting with "Automatic deletion of "
            if title.startswith("Automatic deletion of "):
                continue
            
            if title.startswith("Automatic deletion of "):
                continue
            
            print(f"PR Title: {title}")
            print(f"Merged At: {pr.get('merged_at')}")
            print(f"URL: {pr.get('html_url')}")
            print()
    else:
        print(f"Failed to fetch pull requests. Status code: {response.status_code}")

# Replace with the repository owner and name
get_latest_pull_requests("microsoft", "winget-pkgs")
