import os
import json
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

def send_state_message(last_seen_dates):
    """Send a hidden state message to store the last seen dates"""
    # Use a special format that we can parse later
    # Using zero-width characters to make it less visible
    state_json = json.dumps(last_seen_dates)
    message = f"🤖 <code>STATE:{state_json}</code>"
    
    return send_telegram_message(message)

def get_last_state_from_messages():
    """Fetch recent messages and extract the last state"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    try:
        # Get updates without offset to see all unacknowledged messages
        response = requests.get(url, params={'limit': 100}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('ok'):
            print("Failed to fetch updates from Telegram")
            return {}
        
        print(f"DEBUG: Received {len(data.get('result', []))} updates from Telegram")
        
        # Look for state messages (search in reverse to find most recent)
        for update in reversed(data.get('result', [])):
            message = update.get('message', {})
            text = message.get('text', '')
            
            # Look for our state message format
            if 'STATE:' in text:
                try:
                    # Extract JSON from the message
                    match = re.search(r'STATE:(\{.*\})', text)
                    if match:
                        state_data = json.loads(match.group(1))
                        print(f"DEBUG: Found state message: {state_data}")
                        return state_data
                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"DEBUG: Failed to parse state message: {e}")
                    continue
        
        print("DEBUG: No state message found in updates")
        return {}
        
    except Exception as e:
        print(f"Error fetching updates: {e}")
        return {}

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
    
    # Get last seen dates from previous state message
    print("Fetching state from Telegram messages...")
    last_seen_dates = get_last_state_from_messages()
    
    if last_seen_dates:
        print(f"Loaded state: {last_seen_dates}")
    else:
        print("No previous state found. Will send all posts.")
    
    all_new_posts = []
    updated_dates = {}
    
    for source in BLOG_SOURCES:
        source_name = source['name']
        last_seen_date = last_seen_dates.get(source_name)
        posts = fetch_blog_posts(source)
        
        if not posts:
            continue
        
        new_posts = []
        latest_date = last_seen_date
        
        for post in posts:
            post_date = parse_blog_date(post['date'])
            
            if not post_date:
                # If we can't parse the date, skip it to be safe
                print(f"Warning: Could not parse date '{post['date']}' for post: {post['title']}")
                continue
            
            # Update latest date seen
            if not latest_date or post_date > latest_date:
                latest_date = post_date
            
            print(f"DEBUG: Post '{post['title']}' has date {post_date}, last_seen={last_seen_date}")
            
            # Check if this is a new post
            if not last_seen_date or post_date > last_seen_date:
                new_posts.append(post)
        
        # Store the latest date for this source
        if latest_date:
            updated_dates[source_name] = latest_date
        
        all_new_posts.extend(new_posts)
        
        if new_posts:
            print(f"Found {len(new_posts)} new post(s) from {source_name}")
    
    # Send new posts (oldest first)
    for post in reversed(all_new_posts):
        message = format_post_message(post)
        if send_telegram_message(message):
            print(f"Sent: {post['title']}")
    
    # Send state message to preserve for next run
    if updated_dates:
        if send_state_message(updated_dates):
            print(f"Saved state: {updated_dates}")
        else:
            print("Failed to save state message")
    
    print(f"Check complete. {len(all_new_posts)} new post(s)")

if __name__ == '__main__':
    main()
