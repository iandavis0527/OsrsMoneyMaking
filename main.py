import argparse
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "OSRS_MoneyMaker_BatchFilter - Contact: user@example.com"}

SKILL_NAMES = [
    "Overall",
    "Attack",
    "Defence",
    "Strength",
    "Hitpoints",
    "Ranged",
    "Prayer",
    "Magic",
    "Cooking",
    "Woodcutting",
    "Fletching",
    "Fishing",
    "Firemaking",
    "Crafting",
    "Smithing",
    "Mining",
    "Herblore",
    "Agility",
    "Thieving",
    "Slayer",
    "Farming",
    "Runecraft",
    "Hunter",
    "Construction",
]


def fetch_player_stats(username: str) -> dict:
    """Fetch skills and levels from OSRS Hiscores CSV API."""
    url = f"https://services.runescape.com/m=hiscore_oldschool/index_lite.ws?player={urllib.parse.quote(username)}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(
            f"Error fetching stats for player '{username}'. (HTTP {response.status_code})"
        )
        return {}

    lines = response.text.strip().split("\n")
    stats = {}

    for idx, skill in enumerate(SKILL_NAMES):
        if idx < len(lines):
            parts = lines[idx].split(",")
            if len(parts) >= 2:
                stats[skill.lower()] = int(parts[1])

    return stats


def print_player_stats(username: str, stats: dict):
    """Print the fetched player stats in a multi-column table format."""
    print(f"\n=== STATS DUMP: {username.upper()} ===")
    print("-" * 60)

    # Exclude Overall for grid view to keep individual skills clean
    skills_only = [s for s in SKILL_NAMES if s != "Overall"]

    # Print 3 skills per row
    cols = 3
    for i in range(0, len(skills_only), cols):
        row_skills = skills_only[i : i + cols]
        row_str = ""
        for skill in row_skills:
            level = stats.get(skill.lower(), 1)
            row_str += f"{skill:<13}: {level:<3} | "
        print(row_str.rstrip(" |"))

    print("-" * 60)
    print(f"Overall Level : {stats.get('overall', 'N/A')}")
    print("=" * 60)


def fetch_wiki_money_methods(page_name: str) -> list:
    """Fetch money making methods from a given wiki page (P2P or F2P)."""
    wiki_api_url = "https://oldschool.runescape.wiki/api.php"
    params = {
        "action": "parse",
        "page": page_name,
        "prop": "text",
        "format": "json",
    }

    response = requests.get(wiki_api_url, params=params, headers=HEADERS)
    if response.status_code != 200:
        print(f"Failed to reach OSRS Wiki API for page: {page_name}")
        return []

    html_content = response.json().get("parse", {}).get("text", {}).get("*", "")
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", {"class": "wikitable"})

    methods = []
    if not table:
        return methods

    for row in table.find_all("tr")[1:]:
        cols = row.find_all(["td", "th"])
        if len(cols) >= 2:
            name = cols[0].get_text(strip=True)
            profit_str = cols[1].get_text(strip=True)

            link = cols[0].find("a")
            page_title = ""
            if link and link.has_attr("href"):
                page_title = urllib.parse.unquote(link["href"].replace("/w/", ""))

            if page_title:
                methods.append(
                    {"name": name, "profit": profit_str, "page_title": page_title}
                )

    return methods


def fetch_batch_requirements(page_titles: list) -> dict:
    """Fetch raw wikitext for multiple pages in a single API call (max 50 titles per batch)."""
    if not page_titles:
        return {}

    wiki_api_url = "https://oldschool.runescape.wiki/api.php"
    titles_str = "|".join(page_titles)

    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": titles_str,
        "format": "json",
    }

    response = requests.get(wiki_api_url, params=params, headers=HEADERS)
    if response.status_code != 200:
        return {}

    data = response.json()
    pages = data.get("query", {}).get("pages", {})

    requirements_by_title = {}

    for page_info in pages.values():
        title = page_info.get("title", "")
        revisions = page_info.get("revisions", [])

        if not revisions:
            continue

        wikitext = revisions[0].get("slots", {}).get("main", {}).get("*", "")

        required_skills = {}
        for skill in SKILL_NAMES:
            pattern = re.compile(rf"{skill}\s*[:|=]?\s*(\d{{1,2}})", re.IGNORECASE)
            match = pattern.search(wikitext)
            if match:
                required_skills[skill.lower()] = int(match.group(1))

        requirements_by_title[title] = required_skills

    return requirements_by_title


def chunk_list(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def filter_all_methods(methods: list, player_stats: dict) -> list:
    """Batch process methods and filter based on skill stats."""
    all_titles = list({m["page_title"] for m in methods})

    BATCH_SIZE = 50
    all_requirements = {}

    for chunk in chunk_list(all_titles, BATCH_SIZE):
        batch_reqs = fetch_batch_requirements(chunk)
        all_requirements.update(batch_reqs)

    results = []
    for method in methods:
        title = method["page_title"].replace("_", " ")
        req_skills = all_requirements.get(title, {})

        can_do = True
        missing_reasons = []

        for skill, req_level in req_skills.items():
            player_level = player_stats.get(skill, 1)
            if player_level < req_level:
                can_do = False
                missing_reasons.append(
                    f"{skill.capitalize()} {player_level}/{req_level}"
                )

        method["status"] = (
            "Unlocked" if can_do else f"Locked: Missing {', '.join(missing_reasons)}"
        )
        results.append(method)

    return results


def print_table(title: str, methods: list, limit: int | None = None):
    """Utility function to display methods formatted as a clean table."""
    display_methods = methods[:limit] if limit else methods
    print(f"\n=== {title} ({len(methods)} total) ===")
    print(f"{'METHOD':<45} | {'PROFIT':<15} | {'STATUS'}")
    print("-" * 78)
    for m in display_methods:
        print(f"{m['name'][:44]:<45} | {m['profit']:<15} | {m['status']}")


def main(username: str):
    print(f"\n1. Fetching stats for '{username}'...")
    stats = fetch_player_stats(username)
    if not stats:
        return

    # Print formatted dump of player stats
    print_player_stats(username, stats)

    print("\n2. Fetching P2P & F2P Money Making Guides...")
    p2p_methods = fetch_wiki_money_methods("Money_making_guide")
    f2p_methods = fetch_wiki_money_methods("Money_making_guide/Free-to-play")
    print(
        f"   -> Found {len(p2p_methods)} P2P methods and {len(f2p_methods)} F2P methods."
    )

    print("\n3. Evaluating skill requirements...")
    p2p_results = filter_all_methods(p2p_methods, stats)
    f2p_results = filter_all_methods(f2p_methods, stats)

    # Free-to-play Table Output
    f2p_unlocked = [m for m in f2p_results if m["status"] == "Unlocked"]
    print_table("FREE-TO-PLAY (F2P) UNLOCKED METHODS", f2p_unlocked)

    # Members Table Output
    p2p_unlocked = [m for m in p2p_results if m["status"] == "Unlocked"]
    print_table("PAY-TO-PLAY (P2P) UNLOCKED METHODS (TOP 20)", p2p_unlocked)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to find available OSRS money making methods based on stats"
    )
    parser.add_argument("username", help="Your OSRS username")
    args = parser.parse_args()

    main(args.username)
