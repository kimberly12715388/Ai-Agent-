import os

import requests

response = requests.get(
    "https://api.github.com/repos/octocat/Hello-World",
    headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
)
response.raise_for_status()

print("Repository:", response.json()["full_name"])
print("Requests allowed per hour:", response.headers["X-RateLimit-Limit"])