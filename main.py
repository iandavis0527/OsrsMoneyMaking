import argparse
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup

# Set a custom User-Agent as required by OSRS Wiki API policy
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


def fetch_wiki_money_methods() -> list:
    """Fetch all money making methods from the main guide page."""
    wiki_api_url = "https://oldschool.runescape.wiki/api.php"
    params = {
        "action": "parse",
        "page": "Money_making_guide",
        "prop": "text",
        "format": "json",
    }

    response = requests.get(wiki_api_url, params=params, headers=HEADERS)
    if response.status_code != 200:
        print("Failed to reach OSRS Wiki API.")
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
                # Extract clean page title from href (e.g. /w/Money_making_guide/Tanning_cowhides -> Money_making_guide/Tanning_cowhides)
                page_title = urllib.parse.unquote(link["href"].replace("/w/", ""))

            if page_title:
                methods.append(
                    {"name": name, "profit": profit_str, "page_title": page_title}
                )

    return methods


def fetch_batch_requirements(page_titles: list) -> dict:
    """Fetch raw wikitext for multiple pages in a single API call (max 50 titles per batch)."""
    wiki_api_url = "https://oldschool.runescape.wiki/api.php"

    # Pipe-separated titles for batch API request
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

        # Parse required skill levels using regex across common wiki formats
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
    """Batch process all methods and filter based on skill stats."""
    all_titles = [m["page_title"] for m in methods]

    # MediaWiki API allows max 50 titles per request
    BATCH_SIZE = 50
    all_requirements = {}

    print(f"   -> Fetching wikitext requirements in batches of {BATCH_SIZE}...")
    for chunk in chunk_list(all_titles, BATCH_SIZE):
        batch_reqs = fetch_batch_requirements(chunk)
        all_requirements.update(batch_reqs)

    results = []
    for method in methods:
        title = method["page_title"].replace("_", " ")  # MediaWiki normalizes spaces
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

        if can_do:
            method["status"] = "Unlocked"
        else:
            method["status"] = f"Locked: Missing {', '.join(missing_reasons)}"

        results.append(method)

    return results


def main(username: str):
    print(f"\n1. Fetching stats for '{username}'...")
    stats = fetch_player_stats(username)
    if not stats:
        return

    print(f"   -> Total Level: {stats.get('overall', 'N/A')}")

    print("\n2. Fetching list of all money making methods...")
    methods = fetch_wiki_money_methods()
    print(f"   -> Found {len(methods)} total methods.")

    print(
        "\n3. Batch querying MediaWiki API and evaluating requirements for ALL methods..."
    )
    results = filter_all_methods(methods, stats)

    unlocked = [m for m in results if m["status"] == "Unlocked"]
    locked = [m for m in results if m["status"] != "Unlocked"]

    print("\n" + "=" * 75)
    print(
        f"SUMMARY: {len(unlocked)} Unlocked | {len(locked)} Locked out of {len(results)} total methods"
    )
    print("=" * 75)

    print(f"\n--- TOP UNLOCKED METHODS ({len(unlocked)}) ---")
    print(f"{'METHOD':<45} | {'PROFIT':<15} | {'STATUS'}")
    print("-" * 75)
    for m in unlocked[:20]:  # Display top 20 unlocked
        print(f"{m['name'][:44]:<45} | {m['profit']:<15} | {m['status']}")

    if locked:
        print(f"\n--- SAMPLE LOCKED METHODS ({len(locked)}) ---")
        print(f"{'METHOD':<35} | {'PROFIT':<15} | {'REASON'}")
        print("-" * 75)
        for m in locked[:10]:  # Display sample of 10 locked
            print(f"{m['name'][:34]:<35} | {m['profit']:<15} | {m['status']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "Script to find available money making methods for OSRS"
    )
    parser.add_argument("username", help="Your osrs username")
    args = parser.parse_args()

    main(args.username)
