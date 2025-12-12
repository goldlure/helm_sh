import os
import time
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
BLOG_URL = 'https://helm.sh/blog'
CHECK_INTERVAL = 3600  # Check every hour (in seconds)
STATE_FILE = 'bot_state.json'

def load_state():
    """Load the last seen blog posts from file"""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'seen_posts': []}

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

def fetch_blog_posts():
    """Fetch the latest blog posts from Helm blog"""
    try:
        response = requests.get(BLOG_URL, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        posts = []
        
        # Find all blog post articles
        articles = soup.find_all('article')
        
        for article in articles[:5]:  # Get latest 5 posts
            title_elem = article.find('h2')
            link_elem = title_elem.find('a') if title_elem else None
            
            if link_elem:
                title = link_elem.get_text(strip=True)
                link = link_elem.get('href', '')
                
                # Make sure link is absolute
                if link.startswith('/'):
                    link = f"https://helm.sh{link}"
                
                # Try to get date and author
                date_elem = article.find('time')
                date = date_elem.get_text(strip=True) if date_elem else 'Unknown date'
                
                # Get excerpt if available
                excerpt_elem = article.find('p')
                excerpt = excerpt_elem.get_text(strip=True)[:200] if excerpt_elem else ''
                
                posts.append({
                    'title': title,
                    'link': link,
                    'date': date,
                    'excerpt': excerpt
                })
        
        return posts
    
    except Exception as e:
        print(f"Error fetching blog posts: {e}")
        return []

def format_post_message(post):
    """Format a blog post as a Telegram message"""
    message = f"📝 <b>{post['title']}</b>\n\n"
    message += f"📅 {post['date']}\n\n"
    
    if post['excerpt']:
        message += f"{post['excerpt']}...\n\n"
    
    message += f"🔗 <a href='{post['link']}'>Read more</a>"
    
    return message

def check_for_new_posts():
    """Check for new blog posts and send notifications"""
    state = load_state()
    seen_posts = set(state.get('seen_posts', []))
    
    posts = fetch_blog_posts()
    
    if not posts:
        print("No posts fetched")
        return
    
    new_posts = []
    for post in posts:
        if post['link'] not in seen_posts:
            new_posts.append(post)
            seen_posts.add(post['link'])
    
    # Send notifications for new posts (in reverse order, oldest first)
    for post in reversed(new_posts):
        message = format_post_message(post)
        if send_telegram_message(message):
            print(f"Sent notification for: {post['title']}")
            time.sleep(1)  # Small delay between messages
        else:
            print(f"Failed to send notification for: {post['title']}")
    
    # Save updated state
    state['seen_posts'] = list(seen_posts)
    state['last_check'] = datetime.now().isoformat()
    save_state(state)
    
    if new_posts:
        print(f"Found and sent {len(new_posts)} new post(s)")
    else:
        print("No new posts")

def main():
    """Main bot loop"""
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN and CHAT_ID environment variables must be set!")
        return
    
    # Send startup message
    send_telegram_message("🚀 Helm Blog Bot started! I'll notify you of new posts.")
    
    print("Bot started. Checking for new posts...")
    
    while True:
        try:
            check_for_new_posts()
            print(f"Sleeping for {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\nBot stopped by user")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == '__main__':
    main()