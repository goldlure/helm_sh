import os
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Blog sources configuration
BLOG_SOURCES = [
    {
        'name': 'Helm',
        'url': 'https://helm.sh/blog',
        'icon': '⚓',
        'parser': 'helm_parser'
    },
]

def parse_date_from_message(text):
    """Extract and parse date from Telegram message format: 📅 November 17, 2025"""
    match = re.search(r'📅\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})', text)
    if match:
        try:
            date_str = match.group(1)
            date_obj = datetime.strptime(date_str, '%B %d, %Y')
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None

def get_recent_bot_messages(limit=1):
    """Fetch recent messages from the bot in the chat"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        response = requests.get(url, params={'limit': limit}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('ok'):
            print("Failed to fetch updates from Telegram")
            return []
        
        messages = []
        for update in data.get('result', []):
            message = update.get('message', {})
            # Only get messages sent by the bot to our chat
            if (message.get('chat', {}).get('id') == int(CHAT_ID) and 
                message.get('from', {}).get('is_bot')):
                messages.append(message.get('text', ''))
        
        return messages
    except Exception as e:
        print(f"Error fetching bot messages: {e}")
        return []

def extract_source_and_date_from_message(message):
    """Extract blog source name and date from a Telegram message"""
    # Extract source: 🔖 Helm
    source_match = re.search(r'🔖\s+([^\n]+)', message)
    source = source_match.group(1).strip() if source_match else None
    
    # Extract date
    date = parse_date_from_message(message)
    
    return source, date

def get_last_seen_dates():
    """Get the last seen dates by fetching recent bot messages from Telegram"""
    print("Fetching last seen dates from Telegram history...")
    
    messages = get_recent_bot_messages(limit=1)
    
    if not messages:
        print("No messages found. Will send all posts.")
        return {}
    
    print(f"Found {len(messages)} bot message(s)")
    
    # Extract the most recent date for each source
    last_dates = {}
    
    for message in messages:
        source, date = extract_source_and_date_from_message(message)
        if source and date:
            # Keep the most recent date for each source
            if source not in last_dates or date > last_dates[source]:
                last_dates[source] = date
    
    print(f"Extracted dates for {len(last_dates)} sources:")
    for source, date in last_dates.items():
        print(f"  - {source}: {date}")
    
    return last_dates

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

def parse_blog_date(date_str):
    """Parse blog date string to YYYY-MM-DD format"""
    if not date_str or date_str == 'Unknown date' or date_str == 'Recent':
        return None
    
    # Try common date formats
    formats = [
        '%B %d, %Y',      # November 17, 2025
        '%b %d, %Y',      # Nov 17, 2025
        '%Y-%m-%d',       # 2025-11-17
        '%d %B %Y',       # 17 November 2025
        '%d %b %Y',       # 17 Nov 2025
    ]
    
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str.strip(), fmt)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return None

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
    
    # Get last seen dates from Telegram
    last_seen_dates = get_last_seen_dates()
    
    all_new_posts = []
    
    for source in BLOG_SOURCES:
        source_name = source['name']
        last_seen_date = last_seen_dates.get(source_name)
        posts = fetch_blog_posts(source)
        
        if not posts:
            continue
        
        new_posts = []
        
        for post in posts:
            post_date = parse_blog_date(post['date'])
            
            if not post_date:
                # If we can't parse the date, skip it to be safe
                print(f"Warning: Could not parse date '{post['date']}' for post: {post['title']}")
                continue
            
            # Check if this is a new post
            if not last_seen_date or post_date > last_seen_date:
                new_posts.append(post)
        
        all_new_posts.extend(new_posts)
        
        if new_posts:
            print(f"Found {len(new_posts)} new post(s) from {source_name}")
    
    # Send new posts (oldest first)
    for post in reversed(all_new_posts):
        message = format_post_message(post)
        if send_telegram_message(message):
            print(f"Sent: {post['title']}")
    
    print(f"Check complete. {len(all_new_posts)} new post(s)")

if __name__ == '__main__':
    main()
