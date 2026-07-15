import os
from datetime import datetime, timedelta
from html import escape

import requests

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_ACTOR")
TOKEN = os.environ.get("GH_TOKEN") or ""
THEME = (os.environ.get("THEME") or "auto").lower()

if not USERNAME:
    raise SystemExit("USERNAME environment variable is required")

headers = {"Accept": "application/vnd.github+json"}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"


def fetch_json(url: str):
    response = requests.get(url, headers=headers, timeout=30)
    print(f"GET {url} -> {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise SystemExit(f"GitHub API returned a non-JSON response: {response.text[:200]}") from exc

    if response.status_code != 200:
        message = payload.get("message", "Unknown error") if isinstance(payload, dict) else str(payload)
        raise SystemExit(f"GitHub API request failed: {message}")

    return payload


# Fetch user information
user = fetch_json(f"https://api.github.com/users/{USERNAME}")
if not isinstance(user, dict):
    raise SystemExit(f"Expected user object from GitHub API, got {type(user).__name__}")

# Fetch repositories
repos = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
if not isinstance(repos, list):
    raise SystemExit(f"Expected repository list from GitHub API, got {type(repos).__name__}")

# Fetch public events to estimate streak and contributions
public_events = fetch_json(f"https://api.github.com/users/{USERNAME}/events/public?per_page=100")
if not isinstance(public_events, list):
    raise SystemExit(f"Expected public events list from GitHub API, got {type(public_events).__name__}")

# Calculate totals
stars = sum(int(repo.get("stargazers_count", 0)) for repo in repos)
forks = sum(int(repo.get("forks_count", 0)) for repo in repos)
public_gists = int(user.get("public_gists", 0))
public_repos = int(user.get("public_repos", 0))
avatar_url = user.get("avatar_url", "")

# Estimate contributions and streak from public push events
push_events = [event for event in public_events if event.get("type") == "PushEvent"]
total_contributions = sum(len(event.get("payload", {}).get("commits", [])) for event in push_events)

# Compute consecutive streak of push days
push_days = []
for event in push_events:
    created_at = event.get("created_at")
    if not created_at:
        continue
    day = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    push_days.append(day)

push_days = sorted(set(push_days), reverse=True)
commit_streak = 0
if push_days:
    last_day = push_days[0]
    commit_streak = 1
    for day in push_days[1:]:
        if day == last_day - timedelta(days=1):
            commit_streak += 1
            last_day = day
        else:
            break

# Theme selection
if THEME == "light":
    bg_start, bg_end, card_bg, text_main, text_subtle, stroke = "#f8fafc", "#e2e8f0", "#ffffff", "#0f172a", "#475569", "#cbd5e1"
    accent_start, accent_end, badge_fill = "#2563eb", "#059669", "#f8fafc"
elif THEME == "dark":
    bg_start, bg_end, card_bg, text_main, text_subtle, stroke = "#0f172a", "#111827", "#0b1220", "#ffffff", "#94a3b8", "#1f2937"
    accent_start, accent_end, badge_fill = "#60a5fa", "#34d399", "#111827"
else:
    bg_start, bg_end, card_bg, text_main, text_subtle, stroke = "#0f172a", "#111827", "#0b1220", "#ffffff", "#94a3b8", "#1f2937"
    accent_start, accent_end, badge_fill = "#60a5fa", "#34d399", "#111827"

# Create SVG
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="700" height="360" role="img" aria-label="GitHub profile statistics">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{bg_start}" />
      <stop offset="100%" stop-color="{bg_end}" />
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent_start}" />
      <stop offset="100%" stop-color="{accent_end}" />
    </linearGradient>
    <clipPath id="avatarClip">
      <circle cx="615" cy="82" r="48" />
    </clipPath>
  </defs>

  <rect width="700" height="360" rx="18" fill="url(#bg)"/>
  <rect x="14" y="14" width="672" height="332" rx="16" fill="{card_bg}" stroke="{stroke}"/>
  <rect x="24" y="24" width="200" height="6" rx="3" fill="url(#accent)"/>

  <text x="28" y="74" font-family="Segoe UI, Arial, sans-serif" font-size="28" font-weight="700" fill="{text_main}">
    GitHub Stats
  </text>

  <text x="28" y="102" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_subtle}">
    @{escape(USERNAME)}
  </text>

  <rect x="28" y="116" width="116" height="34" rx="9" fill="{badge_fill}" stroke="{stroke}"/>
  <text x="44" y="138" font-family="Segoe UI, Arial, sans-serif" font-size="12" font-weight="700" fill="{text_main}">
    {THEME.upper()}
  </text>

  <image href="{escape(avatar_url)}" x="567" y="34" width="96" height="96" preserveAspectRatio="xMidYMid slice" clip-path="url(#avatarClip)" image-rendering="optimizeQuality"/>
  <circle cx="615" cy="82" r="50" fill="none" stroke="url(#accent)" stroke-width="5"/>
  <circle cx="615" cy="82" r="43" fill="none" stroke="{stroke}" stroke-width="1.5" opacity="0.65"/>

  <rect x="28" y="166" width="150" height="74" rx="12" fill="{badge_fill}" stroke="{stroke}"/>
  <text x="44" y="195" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_subtle}">● Repos</text>
  <text x="44" y="223" font-family="Segoe UI, Arial, sans-serif" font-size="26" font-weight="700" fill="{text_main}">{public_repos}</text>

  <rect x="194" y="166" width="150" height="74" rx="12" fill="{badge_fill}" stroke="{stroke}"/>
  <text x="210" y="195" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_subtle}">★ Stars</text>
  <text x="210" y="223" font-family="Segoe UI, Arial, sans-serif" font-size="26" font-weight="700" fill="{text_main}">{stars}</text>

  <rect x="360" y="166" width="150" height="74" rx="12" fill="{badge_fill}" stroke="{stroke}"/>
  <text x="376" y="195" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_subtle}">⎇ Forks</text>
  <text x="376" y="223" font-family="Segoe UI, Arial, sans-serif" font-size="26" font-weight="700" fill="{text_main}">{forks}</text>

  <rect x="28" y="252" width="150" height="74" rx="12" fill="{badge_fill}" stroke="{stroke}"/>
  <text x="44" y="281" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_subtle}">⌁ Gists</text>
  <text x="44" y="309" font-family="Segoe UI, Arial, sans-serif" font-size="24" font-weight="700" fill="{text_main}">{public_gists}</text>

  <rect x="194" y="252" width="150" height="74" rx="12" fill="{badge_fill}" stroke="{stroke}"/>
  <text x="210" y="281" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_subtle}">○ Contrib</text>
  <text x="210" y="309" font-family="Segoe UI, Arial, sans-serif" font-size="24" font-weight="700" fill="{text_main}">{total_contributions}</text>

  <rect x="360" y="252" width="150" height="74" rx="12" fill="{badge_fill}" stroke="{stroke}"/>
  <text x="376" y="281" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_subtle}">↺ Streak</text>
  <text x="376" y="309" font-family="Segoe UI, Arial, sans-serif" font-size="24" font-weight="700" fill="{text_main}">{commit_streak}</text>

  <text x="620" y="170" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="{text_subtle}">Streak</text>
  <text x="620" y="198" font-family="Segoe UI, Arial, sans-serif" font-size="32" font-weight="700" fill="{text_main}">{commit_streak}</text>
  <text x="620" y="220" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="{text_subtle}">days</text>
</svg>"""

os.makedirs("assets", exist_ok=True)

with open("assets/github-stats.svg", "w", encoding="utf-8") as file:
    file.write(svg)

print("Generated assets/github-stats.svg")