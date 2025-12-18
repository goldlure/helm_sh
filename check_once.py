import os
import json
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# =====================
# Configuration
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
STATE_FILE = "state.json"

BLOG_SOURCES = [
    {
        "name": "Helm",
        "url": "https://helm.sh/blog",
        "icon": "⚓",
        "parser": "helm_parser",
    },
]

# =====================
# Telegram
# =====================
def send_telegram_message(text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


# =====================
# State handling
# =====================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load state: {e}")
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save state: {e}")
        return False


# =====================
# Parsers
# =====================
def helm_parser(soup, base_url):
    posts = []
    articles = soup.find_all("article")

    for article in articles:
        h2 = article.find("h2")
        if not h2:
            continue

        a = h2.find("a")
        if not a:
            continue

        link = a.get("href")
        if link.startswith("/"):
            link = base_url + link

        date_elem = article.find("time")
        date = date_elem.get_text(strip=True) if date_elem else "Unknown"

        excerpt_elem = article.find("p")
        excerpt = excerpt_elem.get_text(strip=True)[:200] if excerpt_elem else ""

        posts.append(
            {
                "title": a.get_text(strip=True),
                "link": link,
                "date": date,
                "excerpt": excerpt,
            }
        )

    return posts


def fetch_blog_posts(source):
    try:
        r = requests.get(source["url"], timeout=10)
        r.raise_for_status()

        soup = BeautifulSoup(r.content, "html.parser")
        parser = globals().get(source.get("parser"), None)
        base_url = "/".join(source["url"].split("/")[:3])

        posts = parser(soup, base_url)
        for p in posts:
            p["source"] = source["name"]
            p["icon"] = source.get("icon", "📰")

        return posts

    except Exception as e:
        print(f"Fetch error ({source['name']}): {e}")
        return []


# =====================
# Formatting
# =====================
def format_post_message(post):
    return (
        f"{post['icon']} <b>{post['title']}</b>\n\n"
        f"📅 {post['date']}\n"
        f"🔖 {post['source']}\n\n"
        f"{post['excerpt']}...\n\n"
        f"🔗 <a href='{post['link']}'>Read more</a>"
    )


# =====================
# Main
# =====================
def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN and CHAT_ID must be set")

    state = load_state()
    print(f"Loaded state: {state}")

    new_state = {}
    all_new_posts = []

    for source in BLOG_SOURCES:
        name = source["name"]
        last_seen_url = state.get(name)

        posts = fetch_blog_posts(source)
        if not posts:
            continue

        new_posts = []

        for post in posts:
            if post["link"] == last_seen_url:
                break
            new_posts.append(post)

        if posts:
            new_state[name] = posts[0]["link"]

        all_new_posts.extend(reversed(new_posts))

        print(f"{name}: {len(new_posts)} new post(s)")

    for post in all_new_posts:
        if send_telegram_message(format_post_message(post)):
            print(f"Sent: {post['title']}")

    if new_state:
        save_state(new_state)
        print(f"State updated: {new_state}")


if __name__ == "__main__":
    main()
