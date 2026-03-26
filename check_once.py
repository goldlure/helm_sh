import os
import json
import requests
import feedparser
import html
import time
from bs4 import BeautifulSoup

# =====================
# Config
# =====================
MAX_NEW_POSTS = 5 
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
STATE_FILE = "state.json"
SOURCES_FILE = "sources.json"
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
 
# =====================
# Utilities
# =====================
def log(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")


def normalize_url(url: str) -> str:
    return url.rstrip("/")


def load_sources():
    with open(SOURCES_FILE, "r") as f:
        return json.load(f)


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
        raw_summary = e.summary if "summary" in e else ""
        excerpt = BeautifulSoup(raw_summary, "html.parser").get_text(strip=True)[:200]
        posts.append(
            {
                "title": e.title,
                "link": normalize_url(e.link),
                "excerpt": excerpt,
            }
        )
    return posts


def fetch_posts(source):
    if "parser" not in source:
        log(f"Using RSS for {source['name']}")
        return fetch_rss_posts(source)
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
    title = html.escape(post['title'])
    excerpt = html.escape(post['excerpt'])
    return (
        f"{source['icon']} <b>{title}</b>\n\n"
        f"{excerpt}...\n\n"
        f"🔗 <a href='{post['link']}'>Read more</a>"
    )


# =====================
# Main
# =====================
def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN and CHAT_ID must be set")

    sources = load_sources()
    state = load_state()
    log(f"Loaded state: {state}")

    updated_state = {}
    outgoing = []  # list of (post, source) tuples

    for source in sources:
        name = source["name"]
        last_seen = normalize_url(state.get(name, "")) if state.get(name) else None

        posts = fetch_posts(source)
        log(f"[{name}] Fetched {len(posts)} posts")

        new_posts = []

        for post in posts:  # newest → oldest
            if last_seen and post["link"] == last_seen:
                log("Reached last-seen post, stopping")
                break
            new_posts.append(post)
        new_posts = new_posts[:MAX_NEW_POSTS]
        
        if new_posts:
            updated_state[name] = posts[0]["link"]

        outgoing.extend((post, source) for post in reversed(new_posts))
        print(f"{name}: {len(new_posts)} new post(s)")

    for post, source in outgoing:
        send_telegram_message(format_post(post, source))
        print(f"Sent: {post['title']}")
        time.sleep(1)

    if updated_state:
        merged_state = {**state, **updated_state}
        save_state(merged_state)
        print(f"State updated: {merged_state}")


if __name__ == "__main__":
    main()
