import os
import base64
from datetime import datetime, timedelta, date
from html import escape

import requests

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_ACTOR")
TOKEN = os.environ.get("GH_TOKEN") or ""
THEME = (os.environ.get("THEME") or "dark").lower()
MOCK = os.environ.get("MOCK_DATA") == "1"  # set to preview design without hitting the API

if not MOCK and not USERNAME:
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


def graphql(query: str, variables=None):
    response = requests.post(
        "https://api.github.com/graphql",
        headers=headers,
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    print("GraphQL:", response.status_code)
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def calculate_current_streak(days):
    if not days:
        return 0
    day_map = {datetime.strptime(d["date"], "%Y-%m-%d").date(): d["contributionCount"] for d in days}
    current = date.today()
    if day_map.get(current, 0) == 0:
        current -= timedelta(days=1)
    streak = 0
    while day_map.get(current, 0) > 0:
        streak += 1
        current -= timedelta(days=1)
    return streak


def calculate_longest_streak(days):
    if not days:
        return 0
    longest = 0
    current = 0
    previous = None
    for d in sorted(days, key=lambda x: x["date"]):
        day = datetime.strptime(d["date"], "%Y-%m-%d").date()
        if d["contributionCount"] > 0:
            if previous and day == previous + timedelta(days=1):
                current += 1
            else:
                current = 1
            longest = max(longest, current)
            previous = day
        else:
            previous = None
            current = 0
    return longest


# ---------------------------------------------------------------------------
# Data collection (real API) or mock data (design preview)
# ---------------------------------------------------------------------------

LANGUAGE_COLORS = {
    "Python": "#3572A5", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#563d7c", "Java": "#b07219", "C++": "#f34b7d",
    "C": "#555555", "Go": "#00ADD8", "Rust": "#dea584", "Shell": "#89e051",
    "Ruby": "#701516", "PHP": "#4F5D95", "Jupyter Notebook": "#DA5B0B",
    "C#": "#178600", "Vue": "#41b883", "Dart": "#00B4AB",
}
DEFAULT_LANG_COLORS = ["#60a5fa", "#34d399", "#f472b6", "#fbbf24", "#a78bfa"]


def lang_color(name, idx):
    return LANGUAGE_COLORS.get(name, DEFAULT_LANG_COLORS[idx % len(DEFAULT_LANG_COLORS)])


if MOCK:
    USERNAME = USERNAME or "s-rohitks"
    avatar_data_uri = ""
    followers = 42
    public_repos = 15
    private_repos = 4
    stars = 3
    forks = 0
    public_gists = 1
    total_contributions = 812
    commit_count = 640
    pr_count = 58
    issue_count = 34
    review_count = 12
    commit_streak = 6
    longest_streak = 21
    languages_totals = {"Python": 82000, "JavaScript": 41000, "HTML": 18000, "CSS": 9000, "Shell": 4000}
    today = date.today()
    days = []
    import random
    random.seed(7)
    for i in range(140):
        d = today - timedelta(days=139 - i)
        days.append({"date": d.strftime("%Y-%m-%d"), "contributionCount": max(0, int(random.random() * 6 - 1.2))})
else:
    # /users/{username} only ever returns public data, even with a token.
    # To see private repo counts we must call /user (the authenticated-as-yourself
    # endpoint), which only works because GH_TOKEN belongs to USERNAME and has
    # the `repo` scope (classic PAT) or "Repository: Metadata (Read)" +
    # "Repository: Read" for private repos (fine-grained PAT).
    if TOKEN:
        user = fetch_json("https://api.github.com/user")
        repos = fetch_json("https://api.github.com/user/repos?per_page=100&affiliation=owner")
    else:
        user = fetch_json(f"https://api.github.com/users/{USERNAME}")
        repos = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")

    if not isinstance(user, dict):
        raise SystemExit(f"Expected user object from GitHub API, got {type(user).__name__}")
    if not isinstance(repos, list):
        raise SystemExit(f"Expected repository list from GitHub API, got {type(repos).__name__}")

    query = """
    query($login: String!) {
      user(login: $login) {
        followers { totalCount }
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount } }
          }
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
        }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes {
            name
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name } }
            }
          }
        }
      }
    }
    """
    result = graphql(query, {"login": USERNAME})
    profile = result["user"]
    collection = profile["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    total_contributions = calendar["totalContributions"]
    commit_count = collection["totalCommitContributions"]
    issue_count = collection["totalIssueContributions"]
    pr_count = collection["totalPullRequestContributions"]
    review_count = collection["totalPullRequestReviewContributions"]

    days = []
    for week in calendar["weeks"]:
        days.extend(week["contributionDays"])
    commit_streak = calculate_current_streak(days)
    longest_streak = calculate_longest_streak(days)

    # NOTE: if total_contributions looks lower than expected, it's almost always because
    # private-repo contributions are excluded. Fix: generate the token with the
    # `read:user` scope AND make sure the token owner's profile setting
    # "Include private contributions" is enabled -> https://github.com/settings/profile
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in repos)
    forks = sum(int(repo.get("forks_count", 0)) for repo in repos)
    public_gists = int(user.get("public_gists", 0))
    public_repos = int(user.get("public_repos", 0))
    # total_private_repos only appears when authenticated as the token owner
    # with the `repo` scope; otherwise it's simply absent, so this is a safe
    # default rather than a sign of an error.
    private_repos = int(user.get("total_private_repos", 0))

    languages_totals = {}
    for node in profile["repositories"]["nodes"]:
        for edge in node["languages"]["edges"]:
            name = edge["node"]["name"]
            languages_totals[name] = languages_totals.get(name, 0) + edge["size"]

    avatar_url = user.get("avatar_url", "")
    avatar_data_uri = ""
    if avatar_url:
        avatar_response = requests.get(avatar_url, timeout=30)
        avatar_response.raise_for_status()
        avatar_b64 = base64.b64encode(avatar_response.content).decode("utf-8")
        content_type = avatar_response.headers.get("Content-Type", "image/png")
        avatar_data_uri = f"data:{content_type};base64,{avatar_b64}"

print(f"Repositories   : {public_repos}")
print(f"Stars          : {stars}")
print(f"Contributions  : {total_contributions}")
print(f"Current Streak : {commit_streak}")
print(f"Longest Streak : {longest_streak}")
print(f"Commits        : {commit_count}")
print(f"PRs            : {pr_count}")
print(f"Issues         : {issue_count}")
print(f"Reviews        : {review_count}")

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
if THEME == "light":
    bg_start, bg_end = "#f6f8fa", "#eaeef2"
    card_bg, tile_bg = "#ffffff", "#f6f8fa"
    text_main, text_subtle, stroke = "#1f2328", "#59636e", "#d0d7de"
    accent_start, accent_end = "#0969da", "#1a7f37"
else:
    bg_start, bg_end = "#0d1117", "#0d1117"
    card_bg, tile_bg = "#0d1117", "#161b22"
    text_main, text_subtle, stroke = "#e6edf3", "#8b949e", "#30363d"
    accent_start, accent_end = "#58a6ff", "#3fb950"

W, H = 820, 520

# ---------------------------------------------------------------------------
# Small inline icon set (18x18 viewbox, stroke-based, currentColor)
# ---------------------------------------------------------------------------
ICONS = {
    "repo": '<path d="M3 2.5A1.5 1.5 0 0 1 4.5 1h7A1.5 1.5 0 0 1 13 2.5v12.086a.5.5 0 0 1-.79.407L9 12.5l-3.21 2.493A.5.5 0 0 1 5 14.586V2.5Z" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "star": '<path d="M9 1.5l2.12 4.3 4.75.69-3.44 3.35.81 4.73L9 12.35l-4.24 2.22.81-4.73L2.13 6.49l4.75-.69L9 1.5z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "fork": '<circle cx="4.5" cy="4" r="1.6" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="13.5" cy="4" r="1.6" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="9" cy="14" r="1.6" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M4.5 5.6V8c0 1.4 1.2 2 2.2 2.4M13.5 5.6V8c0 1.4-1.2 2-2.2 2.4M9 10.4V12.4" fill="none" stroke="currentColor" stroke-width="1.2"/>',
    "people": '<circle cx="6.2" cy="5.2" r="2.4" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M1.8 14c.4-2.6 2.2-4.2 4.4-4.2s4 1.6 4.4 4.2" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="12.2" cy="6" r="2" fill="none" stroke="currentColor" stroke-width="1.1" opacity="0.7"/><path d="M10.6 9.3c1.7.2 3 1.6 3.4 3.9" fill="none" stroke="currentColor" stroke-width="1.1" opacity="0.7"/>',
    "commit": '<circle cx="9" cy="9" r="2.4" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M1.5 9h4.1M12.4 9h4.1" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "pr": '<circle cx="5" cy="4" r="1.7" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="5" cy="14" r="1.7" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="13" cy="6.5" r="1.7" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M5 5.7V12.3M5 7c3 0 4-1 6-1" fill="none" stroke="currentColor" stroke-width="1.2"/>',
    "issue": '<circle cx="9" cy="9" r="6.3" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M9 5.6v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="9" cy="12.1" r="0.75" fill="currentColor"/>',
    "review": '<path d="M3 9.5l3.6 3.6L15 4.6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "flame": '<path d="M9 1.8c.4 2 2 2.7 2 4.9 0 1-.5 1.7-1.1 2.1.9-.2 1.9-1 1.9-2.5 1.6 1.6 2.4 3.3 2.4 5 0 3-2.3 5.2-5.2 5.2S3.8 14.3 3.8 11.3c0-2.6 1.4-4.2 2.7-5.7-.1.9.2 1.7.9 2.1-.3-2.8 1-4.4 1.6-5.9z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>',
    "trophy": '<path d="M6 3h6v4a3 3 0 0 1-6 0V3z" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M6 4H4a2 2 0 0 0 2 3M12 4h2a2 2 0 0 1-2 3" fill="none" stroke="currentColor" stroke-width="1.1"/><path d="M9 10v2M6.5 15h5M7.2 12.5h3.6l.4 2.5H6.8z" fill="none" stroke="currentColor" stroke-width="1.1"/>',
    "gist": '<path d="M5.5 4L2 9l3.5 5M12.5 4L16 9l-3.5 5M10 3l-2 12" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>',
    "lock": '<rect x="4" y="8" width="10" height="7.5" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6 8V5.6a3 3 0 0 1 6 0V8" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="9" cy="11.5" r="0.9" fill="currentColor"/>',
}


def icon(name, x, y, size, color):
    body = ICONS[name]
    scale = size / 18
    return f'<g transform="translate({x - size/2},{y - size/2}) scale({scale:.4f})" color="{color}">{body}</g>'


def esc(s):
    return escape(str(s))


# ---------------------------------------------------------------------------
# Build tiles (icon + label + value)
# ---------------------------------------------------------------------------
def tile(x, y, w, h, name, label, value):
    return f'''
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{tile_bg}" stroke="none"/>
  {icon(name, x + 22, y + h/2, 18, accent_start)}
  <text x="{x + 40}" y="{y + h/2 - 6}" font-family="Segoe UI, Arial, sans-serif" font-size="12" fill="{text_subtle}">{esc(label)}</text>
  <text x="{x + 40}" y="{y + h/2 + 16}" font-family="Segoe UI, Arial, sans-serif" font-size="21" font-weight="700" fill="{text_main}">{esc(value)}</text>
'''


tiles_data = [
    ("star", "Stars", stars),
    ("repo", "Public Repos", public_repos),
    ("lock", "Private Repos", private_repos),
    ("commit", "Commits", commit_count),
    ("pr", "Pull Requests", pr_count),
    ("issue", "Issues", issue_count),
    ("review", "Reviews", review_count),
    ("gist", "Gists", public_gists),
]

grid_x0, grid_y0 = 32, 190
cols, rows = 4, 2
gap = 14
tile_w = (W - 64 - gap * (cols - 1)) / cols
tile_h = 70
tiles_svg = ""
for i, (ic, label, value) in enumerate(tiles_data):
    col, row = i % cols, i // cols
    x = grid_x0 + col * (tile_w + gap)
    y = grid_y0 + row * (tile_h + gap)
    tiles_svg += tile(x, y, tile_w, tile_h, ic, label, value)

# ---------------------------------------------------------------------------
# Language bar (top 5 by size)
# ---------------------------------------------------------------------------
top_langs = sorted(languages_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
total_lang_size = sum(v for _, v in top_langs) or 1

lang_bar_x, lang_bar_y, lang_bar_w, lang_bar_h = 32, 414, W - 64, 16
segments_svg = ""
cursor = lang_bar_x
legend_svg = ""
legend_x, legend_y = lang_bar_x, lang_bar_y + 44
col_width = (W - 64) / 3
for i, (name, size) in enumerate(top_langs):
    pct = size / total_lang_size
    seg_w = pct * lang_bar_w
    color = lang_color(name, i)
    rx = "7" if i == 0 else "0"
    segments_svg += f'<rect x="{cursor:.1f}" y="{lang_bar_y}" width="{max(seg_w,2):.1f}" height="{lang_bar_h}" fill="{color}"/>'
    cursor += seg_w
    lx = legend_x + (i % 3) * col_width
    ly = legend_y + (i // 3) * 26
    legend_svg += f'''
  <circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{color}"/>
  <text x="{lx+16}" y="{ly}" font-family="Segoe UI, Arial, sans-serif" font-size="12.5" fill="{text_main}">{esc(name)}</text>
  <text x="{lx+16}" y="{ly+15}" font-family="Segoe UI, Arial, sans-serif" font-size="11" fill="{text_subtle}">{pct*100:.1f}%</text>
'''
# clip the whole bar to rounded corners
lang_bar_svg = f'''
  <clipPath id="langClip"><rect x="{lang_bar_x}" y="{lang_bar_y}" width="{lang_bar_w}" height="{lang_bar_h}" rx="7"/></clipPath>
  <g clip-path="url(#langClip)">{segments_svg}</g>
  <text x="{lang_bar_x}" y="{lang_bar_y - 10}" font-family="Segoe UI, Arial, sans-serif" font-size="13" font-weight="600" fill="{text_main}">Languages</text>
'''

# ---------------------------------------------------------------------------
# Mini contribution heatmap (last ~18 weeks)
# ---------------------------------------------------------------------------
day_map = {datetime.strptime(d["date"], "%Y-%m-%d").date(): d["contributionCount"] for d in days}
today = date.today()
weeks_back = 18
start = today - timedelta(days=today.weekday())  # this week's Monday
start -= timedelta(weeks=weeks_back - 1)
max_count = max([v for v in day_map.values()] + [1])

heat_x0, heat_y0 = W - 46 - weeks_back * (11 + 2), 48
cell = 11
gap = 2
heat_svg = ""
for w in range(weeks_back):
    for d_i in range(7):
        day = start + timedelta(weeks=w, days=d_i)
        if day > today:
            continue
        count = day_map.get(day, 0)
        if THEME == "dark":
            colors = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
        else:
            colors = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]

        if count == 0:
            fill = colors[0]
        elif count <= 2:
            fill = colors[1]
        elif count <= 5:
            fill = colors[2]
        elif count <= 9:
            fill = colors[3]
        else:
            fill = colors[4]

        x = heat_x0 + w * (cell + gap)
        y = heat_y0 + d_i * (cell + gap)
        heat_svg += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3.5" fill="{fill}" stroke="none"/>'

# ---------------------------------------------------------------------------
# Assemble final SVG
# ---------------------------------------------------------------------------
avatar_block = ""
if avatar_data_uri:
    avatar_block = f'''
  <clipPath id="avatarClip"><circle cx="72" cy="86" r="40"/></clipPath>
  <image href="{avatar_data_uri}" x="32" y="46" width="80" height="80" preserveAspectRatio="xMidYMid slice" clip-path="url(#avatarClip)"/>
  <circle cx="72" cy="86" r="41" fill="none" stroke="url(#accent)" stroke-width="3"/>
'''
    name_x = 130
else:
    name_x = 32

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub profile statistics for {esc(USERNAME)}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{bg_start}"/>
      <stop offset="100%" stop-color="{bg_end}"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{accent_start}"/>
      <stop offset="100%" stop-color="{accent_end}"/>
    </linearGradient>
    {avatar_block}
  </defs>

  <rect width="{W}" height="{H}" rx="18" fill="url(#bg)"/>
  <rect x="10" y="10" width="{W-20}" height="{H-20}" rx="16" fill="{card_bg}" stroke="{stroke}" stroke-width="1"/>
  <rect x="30" y="28" width="140" height="5" rx="2.5" fill="url(#accent)"/>

  <text x="{name_x}" y="70" font-family="Segoe UI, Arial, sans-serif" font-size="24" font-weight="700" fill="{text_main}">{esc(USERNAME)}</text>
  <text x="{name_x}" y="96" font-family="Segoe UI, Arial, sans-serif" font-size="13.5" fill="{text_subtle}">github.com/{esc(USERNAME)}</text>

  {icon("flame", name_x + 12, 122, 16, "#f97316")}
  <text x="{name_x + 26}" y="127" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_main}"><tspan font-weight="700">{commit_streak}</tspan> day streak</text>

  {icon("trophy", name_x + 145, 122, 16, "#facc15")}
  <text x="{name_x + 160}" y="127" font-family="Segoe UI, Arial, sans-serif" font-size="13" fill="{text_main}"><tspan font-weight="700">{longest_streak}</tspan> day best</text>

  <rect
      x="{heat_x0-12}"
      y="{heat_y0-12}"
      width="{weeks_back*(cell+gap)+24}"
      height="118"
      rx="12"
      fill="{tile_bg}"
      opacity="0.55"
      stroke="{stroke}"/>

  <!-- Month labels -->
  <text x="{heat_x0}" y="{heat_y0-16}" font-family="Segoe UI, Arial, sans-serif" font-size="10.5" fill="{text_subtle}">Mar</text>
  <text x="{heat_x0+52}" y="{heat_y0-16}" font-family="Segoe UI, Arial, sans-serif" font-size="10.5" fill="{text_subtle}">Apr</text>
  <text x="{heat_x0+104}" y="{heat_y0-16}" font-family="Segoe UI, Arial, sans-serif" font-size="10.5" fill="{text_subtle}">May</text>
  <text x="{heat_x0+156}" y="{heat_y0-16}" font-family="Segoe UI, Arial, sans-serif" font-size="10.5" fill="{text_subtle}">Jun</text>

  <!-- Weekday labels -->
  <text x="{heat_x0-18}" y="{heat_y0+11}" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="{text_subtle}">M</text>
  <text x="{heat_x0-18}" y="{heat_y0+37}" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="{text_subtle}">W</text>
  <text x="{heat_x0-18}" y="{heat_y0+63}" font-family="Segoe UI, Arial, sans-serif" font-size="10" fill="{text_subtle}">F</text>

  {heat_svg}

  <line x1="30" y1="152" x2="{W-30}" y2="152" stroke="none"/>

  <text x="{grid_x0}" y="178" font-family="Segoe UI, Arial, sans-serif" font-size="12" font-weight="600" fill="{text_subtle}">OVERVIEW</text>
  {tiles_svg}

  <text x="{grid_x0}" y="{grid_y0 + rows*(tile_h+gap) + 26}" font-family="Segoe UI, Arial, sans-serif" font-size="20" font-weight="700" fill="{text_main}">{total_contributions:,}</text>
  <text x="{grid_x0 + 100}" y="{grid_y0 + rows*(tile_h+gap) + 26}" font-family="Segoe UI, Arial, sans-serif" font-size="12.5" fill="{text_subtle}">total contributions in the last year</text>

  {lang_bar_svg}
  {legend_svg}
</svg>'''

os.makedirs("assets", exist_ok=True)
out_path = f"assets/preview-github-stats-{THEME}.svg" if MOCK else f"assets/github-stats-{THEME}.svg"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(svg)
print(f"Generated {out_path}")
