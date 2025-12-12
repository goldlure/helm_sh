import os
import json
import requests
from bs4 import BeautifulSoup

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
STATE_FILE = 'bot_state.json'

# Blog sources configuration
BLOG_SOURCES = [
    {
        'name': 'Helm',
        'url': 'https://helm.sh/blog',
        'icon': '⚓',
        'parser': 'helm_parser'
    },
]

def load_state():
    """Load the last seen blog posts from file"""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'seen_posts': {}}

def save_state(state):
    """Save the current state to file"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def send_telegram_message(text, parse_mode='HTML'):
    """Send a message via Telegram Bot API"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def helm_parser(soup, base_url):
    """Parser for Helm blog"""
    posts = []
    articles = soup.find_all('article')
    
    for article in articles[:5]:
        title_elem = article.find('h2')
        link_elem = title_elem.find('a') if title_elem else None
        
        if link_elem:
            title = link_elem.get_text(strip=True)
            link = link_elem.get('href', '')
            
            if link.startswith('/'):
                link = f"{base_url.rstrip('/')}{link}"
            
            date_elem = article.find('time')
            date = date_elem.get_text(strip=True) if date_elem else 'Unknown date'
            
            excerpt_elem = article.find('p')
            excerpt = excerpt_elem.get_text(strip=True)[:200] if excerpt_elem else ''
            
            posts.append({
                'title': title,
                'link': link,
                'date': date,
                'excerpt': excerpt
            })
    
    return posts

def generic_parser(soup, base_url):
    """Generic parser for blogs"""
    posts = []
    articles = (soup.find_all('article') or 
                soup.find_all('div', class_='post') or
                soup.find_all('div', class_='blog-post'))
    
    for article in articles[:5]:
        title_elem = (article.find('h1') or article.find('h2') or 
                     article.find('h3') or article.find('a', class_='title'))
        
        if title_elem:
            link_elem = title_elem.find('a') if title_elem.name != 'a' else title_elem
            
            if link_elem:
                title = link_elem.get_text(strip=True)
                link = link_elem.get('href', '')
                
                if link.startswith('/'):
                    link = f"{base_url.rstrip('/')}{link}"
                
                date_elem = article.find('time') or article.find(class_='date')
                date = date_elem.get_text(strip=True) if date_elem else 'Recent'
                
                excerpt_elem = article.find('p')
                excerpt = excerpt_elem.get_text(strip=True)[:200] if excerpt_elem else ''
                
                posts.append({
                    'title': title,
                    'link': link,
                    'date': date,
                    'excerpt': excerpt
                })
    
    return posts

def fetch_blog_posts(source):
    """Fetch the latest blog posts from a source"""
    try:
        response = requests.get(source['url'], timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        parser_name = source.get('parser', 'generic_parser')
        parser_func = globals().get(parser_name, generic_parser)
        base_url = '/'.join(source['url'].split('/')[:3])
        
        posts = parser_func(soup, base_url)
        
        for post in posts:
            post['source'] = source['name']
            post['source_icon'] = source.get('icon', '📰')
        
        return posts
    
    except Exception as e:
        print(f"Error fetching {source['name']}: {e}")
        return []

def format_post_message(post):
    """Format a blog post as a Telegram message"""
    icon = post.get('source_icon', '📰')
    source = post.get('source', 'Blog')
    
    message = f"{icon} <b>{post['title']}</b>\n\n"
    message += f"📅 {post['date']}\n"
    message += f"🔖 {source}\n\n"
    
    if post.get('excerpt'):
        message += f"{post['excerpt']}...\n\n"
    
    message += f"🔗 <a href='{post['link']}'>Read more</a>"
    
    return message

def main():
    """Check once and exit"""
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN and CHAT_ID must be set!")
        return
    
    state = load_state()
    
    if not isinstance(state.get('seen_posts'), dict):
        state['seen_posts'] = {}
    
    all_new_posts = []
    
    for source in BLOG_SOURCES:
        source_name = source['name']
        seen_posts = set(state['seen_posts'].get(source_name, []))
        posts = fetch_blog_posts(source)
        
        if not posts:
            continue
        
        new_posts = []
        for post in posts:
            if post['link'] not in seen_posts:
                new_posts.append(post)
                seen_posts.add(post['link'])
        
        state['seen_posts'][source_name] = list(seen_posts)
        all_new_posts.extend(new_posts)
        
        if new_posts:
            print(f"Found {len(new_posts)} new post(s) from {source_name}")
    
    for post in reversed(all_new_posts):
        message = format_post_message(post)
        if send_telegram_message(message):
            print(f"Sent: {post['title']}")
    
    save_state(state)
    print(f"Check complete. {len(all_new_posts)} new post(s)")

if __name__ == '__main__':
    main()
