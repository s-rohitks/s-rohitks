import os
import requests

USERNAME = os.environ["USERNAME"]
TOKEN = os.environ["GH_TOKEN"]

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Fetch user information
user = requests.get(
    f"https://api.github.com/users/{USERNAME}",
    headers=headers,
).json()

# Fetch repositories
repos = requests.get(
    f"https://api.github.com/users/{USERNAME}/repos?per_page=100",
    headers=headers,
).json()

# Calculate totals
stars = sum(repo["stargazers_count"] for repo in repos)
forks = sum(repo["forks_count"] for repo in repos)

# Create SVG
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="220">
<rect width="100%" height="100%" rx="12" fill="#282a36"/>

<text x="20" y="40" font-size="24" fill="#50fa7b">
GitHub Stats
</text>

<text x="20" y="80" font-size="18" fill="#ffffff">
Repositories: {user['public_repos']}
</text>

<text x="20" y="110" font-size="18" fill="#ffffff">
Followers: {user['followers']}
</text>

<text x="20" y="140" font-size="18" fill="#ffffff">
Following: {user['following']}
</text>

<text x="20" y="170" font-size="18" fill="#ffffff">
Stars: {stars}
</text>

<text x="20" y="200" font-size="18" fill="#ffffff">
Forks: {forks}
</text>
</svg>"""

os.makedirs("assets", exist_ok=True)

with open("assets/github-stats.svg", "w", encoding="utf-8") as file:
    file.write(svg)

print("Generated assets/github-stats.svg")