import os
import json
import requests
import feedparser
from bs4 import BeautifulSoup

# =====================
# Config
# =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
STATE_FILE = "state.json"
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

BLOG_SOURCES = [
    {
        "name": "Helm",
        "url": "https://helm.sh/blog",
        "rss": "https://helm.sh/rss.xml",
        "icon": "⚓",
        "parser": "helm_parser",
    }
]


# =====================
# Utilities
# =====================
def log(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")


def normalize_url(url: str) -> str:
    return url.rstrip("/")


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
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


# =====================
# State
# =====================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# =====================
# Parsers
# =====================
def helm_parser(soup, base_url):
    posts = []
    for article in soup.find_all("article"):
        h2 = article.find("h2")
        if not h2:
            continue
        a = h2.find("a")
        if not a:
            continue

        link = a["href"]
        if link.startswith("/"):
            link = base_url + link

        excerpt = ""
        p = article.find("p")
        if p:
            excerpt = p.get_text(strip=True)[:200]

        posts.append(
            {
                "title": a.get_text(strip=True),
                "link": normalize_url(link),
                "excerpt": excerpt,
            }
        )
    return posts


def fetch_html_posts(source):
    r = requests.get(source["url"], timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "html.parser")
    base_url = "/".join(source["url"].split("/")[:3])
    return globals()[source["parser"]](soup, base_url)


def fetch_rss_posts(source):
    feed = feedparser.parse(source["rss"])
    posts = []
    for e in feed.entries:
        posts.append(
            {
                "title": e.title,
                "link": normalize_url(e.link),
                "excerpt": e.summary[:200] if "summary" in e else "",
            }
        )
    return posts


def fetch_posts(source):
    try:
        log("Trying HTML parser")
        return fetch_html_posts(source)
    except Exception as e:
        log(f"HTML failed ({e}), falling back to RSS")
        return fetch_rss_posts(source)


# =====================
# Formatting
# =====================
def format_post(post, source):
    return (
        f"{source['icon']} <b>{post['title']}</b>\n\n"
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
    log(f"Loaded state: {state}")

    updated_state = {}
    outgoing = []

    for source in BLOG_SOURCES:
        name = source["name"]
        last_seen = normalize_url(state.get(name, "")) if state.get(name) else None

        posts = fetch_posts(source)
        log(f"Fetched {len(posts)} posts")

        new_posts = []

        for post in posts:  # newest → oldest
            if last_seen and post["link"] == last_seen:
                log("Reached last-seen post, stopping")
                break
            new_posts.append(post)

        if new_posts:
            updated_state[name] = posts[0]["link"]

        outgoing.extend(reversed(new_posts))
        print(f"{name}: {len(new_posts)} new post(s)")

    for post in outgoing:
        send_telegram_message(format_post(post, source))
        print(f"Sent: {post['title']}")

    if updated_state:
        save_state(updated_state)
        print(f"State updated: {updated_state}")


if __name__ == "__main__":
    main()
