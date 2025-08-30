from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session
from flask_cors import CORS
import requests
import json
import time
import os
import threading
from datetime import datetime, timedelta
import uuid
import random
import hashlib
from threading import Lock

app = Flask(__name__)
CORS(app)

# Configure session
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'stone-rulex-integrated-secret-key-2024')
app.config['SESSION_PERMANENT'] = False

# Admin credentials
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'onfire_stone')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'stoneOO7')

# Global storage with thread safety
user_sessions = {}
users_db = {}
data_lock = Lock()

# Files for persistence
USERS_FILE = 'users.json'
SESSIONS_FILE = 'sessions.json'

def load_users():
    """Load users from JSON file"""
    global users_db
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                users_db = json.load(f)
        except:
            users_db = {}
    return users_db

def save_users():
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users_db, f, indent=2)

def hash_password(password):
    """Hash password with salt"""
    salt = "stone_rulex_salt_2024"
    return hashlib.sha256((password + salt).encode()).hexdigest()

def get_session_id():
    """Get or create session ID for current user"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def init_user_session(username):
    """Initialize user session data if not exists"""
    with data_lock:
        if username not in user_sessions:
            user_sessions[username] = {
                'message_threads': {},
                'task_logs': {},
                'stop_flags': {},
                'tokens': [],
                'created_at': datetime.now(),
                'last_activity': datetime.now()
            }
        else:
            user_sessions[username]['last_activity'] = datetime.now()

def get_user_data(username, data_type):
    """Get user-specific data"""
    init_user_session(username)
    return user_sessions[username][data_type]

def add_log(username, task_id, message):
    """Add log entry for specific user and task"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    task_logs = get_user_data(username, 'task_logs')
    if task_id not in task_logs:
        task_logs[task_id] = []
    task_logs[task_id].append(log_entry)
    # Keep only the last 1000 logs per task
    if len(task_logs[task_id]) > 1000:
        del task_logs[task_id][0:len(task_logs[task_id])-1000]

def check_token_validity(token):
    """Check if a Facebook token is valid and return user info with enhanced error handling"""
    try:
        # Add random delay to avoid rate limiting
        time.sleep(random.uniform(0.5, 2.0))
        url = f"https://graph.facebook.com/v17.0/me?access_token={token}"
        headers = {
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            ])
        }
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            user_data = response.json()
            user_id = user_data.get('id')
            user_name = user_data.get('name', 'Unknown')
            
            # Get profile picture with error handling
            try:
                picture_url = f"https://graph.facebook.com/v17.0/{user_id}/picture?access_token={token}&redirect=false"
                pic_response = requests.get(picture_url, headers=headers, timeout=15)
                picture_data = pic_response.json() if pic_response.status_code == 200 else {}
                picture = picture_data.get('data', {}).get('url', '')
            except:
                picture = ''
                
            return {
                'valid': True,
                'id': user_id,
                'name': user_name,
                'picture': picture,
                'message': 'Token is valid'
            }
        else:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
            return {
                'valid': False,
                'message': f'Invalid token: {error_message}'
            }
    except requests.exceptions.Timeout:
        return {'valid': False, 'message': 'Request timeout - token may be rate limited'}
    except requests.exceptions.RequestException as e:
        return {'valid': False, 'message': f'Network error: {str(e)}'}
    except Exception as e:
        return {'valid': False, 'message': f'Unexpected error: {str(e)}'}

def get_token_name(token):
    """Get token owner name for identification"""
    try:
        result = check_token_validity(token)
        if result['valid']:
            return result['name']
        return 'Invalid Token'
    except:
        return 'Unknown'

def fetch_messenger_groups(token):
    """Fetch messenger groups with enhanced error handling"""
    try:
        # Add random delay
        time.sleep(random.uniform(1.0, 3.0))
        headers = {
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            ])
        }
        
        # First verify token
        check_result = check_token_validity(token)
        if not check_result['valid']:
            return {'success': False, 'message': check_result['message']}
        
        # Fetch conversations
        url = f"https://graph.facebook.com/v17.0/me/conversations?fields=id,name,participants&access_token={token}"
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            groups = []
            for conv in data.get('data', []):
                conv_id = conv.get('id', '').replace('t_', '')
                conv_name = conv.get('name', '')
                if not conv_name:
                    participants = conv.get('participants', {}).get('data', [])
                    participant_names = [p.get('name', 'Unknown') for p in participants[:3]]
                    conv_name = ', '.join(participant_names) if participant_names else 'Group Chat'
                
                groups.append({
                    'uid': conv_id,
                    'name': conv_name
                })
            
            return {'success': True, 'groups': groups}
        else:
            error_data = response.json() if response.content else {}
            error_message = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
            return {'success': False, 'message': error_message}
    except requests.exceptions.Timeout:
        return {'success': False, 'message': 'Request timeout - please try again'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'message': f'Network error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'message': f'Unexpected error: {str(e)}'}

def send_messages(username, task_id, convo_uid, tokens, message_content, speed, haters_name):
    """Enhanced message sending with suspension prevention"""
    messages = [msg.strip() for msg in message_content.split('\n') if msg.strip()]
    num_messages = len(messages)
    max_tokens = len(tokens)
    
    if max_tokens == 0:
        add_log(username, task_id, "No valid tokens available")
        return
        
    stop_flags = get_user_data(username, 'stop_flags')
    add_log(username, task_id, f"Starting task with {num_messages} messages and {max_tokens} tokens")
    add_log(username, task_id, f"Target conversation: {convo_uid}")
    add_log(username, task_id, f"Message speed: {speed} seconds (base delay)")
    
    # Enhanced headers for anti-detection
    headers = {
        'User-Agent': random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site'
    }
    
    # Token usage tracking for intelligent rotation
    token_usage = {token: 0 for token in tokens}
    token_cooldown = {token: 0 for token in tokens}
    
    for i, message in enumerate(messages):
        if task_id in stop_flags and stop_flags[task_id]:
            add_log(username, task_id, "Task stopped by user")
            break
            
        if not message:
            continue
            
        # Intelligent token selection (avoid recently used tokens)
        current_time = time.time()
        available_tokens = [t for t in tokens if current_time >= token_cooldown[t]]
        
        if not available_tokens:
            # If all tokens are in cooldown, wait for the earliest one
            min_cooldown = min(token_cooldown.values())
            wait_time = max(0, min_cooldown - current_time)
            if wait_time > 0:
                add_log(username, task_id, f"All tokens in cooldown. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
            available_tokens = tokens
            
        # Select token with least usage
        token = min(available_tokens, key=lambda t: token_usage[t])
        token_index = tokens.index(token)
        
        # Enhanced message formatting
        full_message = f"{haters_name}: {message}"
        add_log(username, task_id, f"Sending message {i+1}/{num_messages} using token {token_index+1}: {full_message[:50]}...")
        
        try:
            # Enhanced delay calculation with jitter
            base_delay = float(speed)
            jitter = random.uniform(0.3, 1.8)  # Random jitter
            usage_delay = token_usage[token] * 0.1  # Increase delay based on usage
            total_delay = base_delay + jitter + usage_delay
            
            if i > 0:  # Don't delay before first message
                add_log(username, task_id, f"Waiting {total_delay:.1f} seconds (base: {base_delay}, jitter: {jitter:.1f}, usage: {usage_delay:.1f})...")
                time.sleep(total_delay)
                
            # Check stop flag again after delay
            if task_id in stop_flags and stop_flags[task_id]:
                add_log(username, task_id, "Task stopped by user during delay")
                break
                
            # Enhanced retry logic with exponential backoff
            max_retries = 5
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    url = f"https://graph.facebook.com/v17.0/{convo_uid}/messages"
                    payload = {
                        'message': full_message,
                        'access_token': token
                    }
                    
                    # Add random delay before request
                    time.sleep(random.uniform(0.1, 0.5))
                    
                    response = requests.post(url, data=payload, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        add_log(username, task_id, f"✓ Message {i+1} sent successfully (Token {token_index+1})")
                        success = True
                        token_usage[token] += 1
                        # Set cooldown for this token (increases with usage)
                        cooldown_time = current_time + (5 + token_usage[token] * 2)
                        token_cooldown[token] = cooldown_time
                    elif response.status_code == 429:  # Rate limited - longer wait
                        wait_time = (2 ** retry_count) * 30 + random.uniform(10, 30)
                        add_log(username, task_id, f"Rate limited. Waiting {wait_time:.1f} seconds...")
                        time.sleep(wait_time)
                        retry_count += 1
                    elif response.status_code in [400, 403]:  # Token or permission issue
                        error_data = response.json() if response.content else {}
                        error_message = error_data.get('error', {}).get('message', 'Unknown error')
                        add_log(username, task_id, f"✗ Token {token_index+1} error: {error_message}")
                        
                        # Remove problematic token from rotation
                        if 'token' in error_message.lower() or 'permission' in error_message.lower():
                            add_log(username, task_id, f"Removing problematic token {token_index+1} from rotation")
                            if len(tokens) > 1:
                                tokens.remove(token)
                                token_usage.pop(token, None)
                                token_cooldown.pop(token, None)
                                break
                        retry_count += 1
                    else:
                        error_data = response.json() if response.content else {}
                        error_message = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                        add_log(username, task_id, f"✗ Error sending message {i+1}: {error_message}")
                        retry_count += 1
                        
                        if retry_count < max_retries:
                            wait_time = (2 ** retry_count) + random.uniform(1, 5)
                            add_log(username, task_id, f"Retrying in {wait_time:.1f} seconds... (attempt {retry_count + 1}/{max_retries})")
                            time.sleep(wait_time)
                            
                except requests.exceptions.Timeout:
                    add_log(username, task_id, f"Request timeout for message {i+1}")
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = (2 ** retry_count) + random.uniform(2, 8)
                        add_log(username, task_id, f"Retrying in {wait_time:.1f} seconds...")
                        time.sleep(wait_time)
                except requests.exceptions.RequestException as e:
                    add_log(username, task_id, f"Network error: {str(e)}")
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = (2 ** retry_count) + random.uniform(2, 8)
                        add_log(username, task_id, f"Retrying in {wait_time:.1f} seconds...")
                        time.sleep(wait_time)
                        
            if not success:
                add_log(username, task_id, f"Failed to send message {i+1} after {max_retries} attempts")
                # If we have multiple tokens, try switching to a different one
                if len(tokens) > 1:
                    add_log(username, task_id, "Switching to different token for next message")
                    
        except Exception as e:
            add_log(username, task_id, f"Unexpected error sending message {i+1}: {str(e)}")
            
    add_log(username, task_id, f"Task completed. Token usage: {dict(token_usage)}")

def cleanup_inactive_sessions():
    """Clean up inactive sessions (older than 24 hours)"""
    current_time = datetime.now()
    inactive_users = []
    with data_lock:
        for username, session_data in user_sessions.items():
            last_activity = session_data.get('last_activity', session_data.get('created_at'))
            if (current_time - last_activity).total_seconds() > 86400:  # 24 hours
                inactive_users.append(username)
                
        for username in inactive_users:
            # Stop all threads for this user
            message_threads = user_sessions[username]['message_threads']
            stop_flags = user_sessions[username]['stop_flags']
            for task_id in list(message_threads.keys()):
                if task_id in stop_flags:
                    stop_flags[task_id] = True
                thread_info = message_threads[task_id]
                if thread_info['thread'].is_alive():
                    thread_info['thread'].join(timeout=1)
            del user_sessions[username]

# Load users on startup
load_users()

# HTML Templates (keeping the enhanced UI from the first script)
html_content = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STONE RULEX - Enhanced Admin System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); border-radius: 20px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1); max-width: 1200px; margin: 0 auto; overflow: hidden; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; position: relative; }
        .header h1 { font-size: 2.5rem; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3); }
        .header p { font-size: 1.1rem; opacity: 0.9; }
        .user-info { position: absolute; top: 10px; left: 20px; background: rgba(255, 255, 255, 0.2); padding: 8px 12px; border-radius: 15px; font-size: 0.8rem; backdrop-filter: blur(5px); }
        .logout-btn { position: absolute; top: 10px; right: 20px; background: rgba(220, 53, 69, 0.8); color: white; border: none; padding: 8px 15px; border-radius: 15px; cursor: pointer; font-size: 0.8rem; backdrop-filter: blur(5px); }
        .approval-status { margin: 20px; padding: 15px; border-radius: 10px; text-align: center; font-weight: 600; }
        .approved { background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); color: #155724; border: 1px solid #c3e6cb; }
        .pending { background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); color: #856404; border: 1px solid #ffeaa7; }
        .tabs { display: flex; background: #f8f9fa; border-bottom: 1px solid #dee2e6; }
        .tab { flex: 1; padding: 20px; text-align: center; cursor: pointer; background: #f8f9fa; border: none; font-size: 16px; font-weight: 600; color: #495057; transition: all 0.3s ease; position: relative; }
        .tab:hover { background: #e9ecef; color: #007bff; }
        .tab.active { background: white; color: #007bff; }
        .tab.active::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 3px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .tab-content { display: none; padding: 30px; min-height: 500px; }
        .tab-content.active { display: block; }
        .form-group { margin-bottom: 25px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
        input[type="text"], input[type="number"], textarea, input[type="file"] { width: 100%; padding: 15px; border: 2px solid #e9ecef; border-radius: 10px; font-size: 16px; transition: all 0.3s ease; background: #f8f9fa; }
        input[type="text"]:focus, input[type="number"]:focus, textarea:focus { outline: none; border-color: #667eea; background: white; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        textarea { resize: vertical; min-height: 120px; font-family: 'Courier New', monospace; }
        .btn { padding: 15px 30px; border: none; border-radius: 10px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; text-transform: uppercase; letter-spacing: 0.5px; margin: 5px; min-width: 150px; }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3); }
        .btn-success { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .btn-success:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(40, 167, 69, 0.3); }
        .btn-danger { background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); color: white; }
        .btn-danger:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(220, 53, 69, 0.3); }
        .btn-warning { background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%); color: #212529; }
        .btn-warning:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(255, 193, 7, 0.3); }
        .task-item { background: white; border: 1px solid #e9ecef; border-radius: 15px; padding: 25px; margin-bottom: 20px; box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08); transition: all 0.3s ease; }
        .task-item:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15); }
        .task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; }
        .task-id { font-weight: 700; color: #667eea; font-size: 18px; }
        .task-status { padding: 8px 16px; border-radius: 20px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
        .status-running { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .status-stopped { background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); color: white; }
        .task-info { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .task-info-item { background: #f8f9fa; padding: 10px 15px; border-radius: 8px; border-left: 4px solid #667eea; }
        .task-info-label { font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
        .task-info-value { font-weight: 600; color: #495057; }
        .task-buttons { display: flex; gap: 10px; flex-wrap: wrap; }
        .log-container { background: #1e1e1e; color: #00ff00; font-family: 'Courier New', monospace; font-size: 12px; padding: 20px; border-radius: 10px; height: 400px; overflow-y: auto; margin-top: 15px; border: 2px solid #333; display: none; }
        .log-container.show { display: block; }
        .log-entry { margin-bottom: 5px; line-height: 1.4; }
        .result-container { margin-top: 20px; }
        .result-item { background: white; border: 1px solid #e9ecef; border-radius: 10px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05); }
        .result-valid { border-left: 5px solid #28a745; background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); }
        .result-invalid { border-left: 5px solid #dc3545; background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%); }
        .token-info { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 10px; }
        .token-info-item { display: flex; align-items: center; gap: 10px; }
        .profile-pic { width: 50px; height: 50px; border-radius: 50%; border: 3px solid #667eea; }
        .group-item { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 10px; padding: 15px; margin-bottom: 10px; transition: all 0.3s ease; }
        .group-item:hover { background: white; box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1); }
        .group-name { font-weight: 600; color: #667eea; margin-bottom: 5px; }
        .group-uid { font-family: 'Courier New', monospace; color: #6c757d; font-size: 12px; background: #e9ecef; padding: 5px 10px; border-radius: 5px; display: inline-block; }
        .loading { text-align: center; padding: 40px; color: #6c757d; }
        .loading::after { content: ''; display: inline-block; width: 20px; height: 20px; border: 3px solid #f3f3f3; border-top: 3px solid #667eea; border-radius: 50%; animation: spin 1s linear infinite; margin-left: 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .empty-state { text-align: center; padding: 60px 20px; color: #6c757d; }
        .empty-state i { font-size: 4rem; margin-bottom: 20px; opacity: 0.3; }
        @media (max-width: 768px) { .tabs { flex-direction: column; } .task-header { flex-direction: column; align-items: flex-start; gap: 10px; } .task-buttons { width: 100%; } .btn { flex: 1; min-width: auto; } .user-info, .logout-btn { position: static; margin: 5px; display: inline-block; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="user-info"> 👤 {{ session.get('username', 'Unknown') }} </div>
            <button class="logout-btn" onclick="window.location.href='/logout'">Logout</button>
            <h1>STONE RULEX</h1>
        </div>
        
        {% if not session.get('approved') %}
        <div class="approval-status pending">
            <h3>⚠ Pending Admin Approval</h3>
            <p>Your account is waiting for admin approval. You cannot use the tools until approved.</p>
        </div>
        {% else %}
        <div class="approval-status approved">
            <h3>✓ Account Approved</h3>
            <p>You have full access to all tools and features.</p>
        </div>
        {% endif %}
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('bot-tab')">CONVO TOOL</button>
            <button class="tab" onclick="switchTab('token-tab')">TOKEN CHECKER</button>
            <button class="tab" onclick="switchTab('groups-tab')">UID FETCHER</button>
            <button class="tab" onclick="switchTab('logs-tab')">TASK MANAGER</button>
        </div>
        
        <div id="bot-tab" class="tab-content active">
            {% if not session.get('approved') %}
            <div class="empty-state">
                <h3>🔒 Access Restricted</h3>
                <p>Please wait for admin approval to use this tool.</p>
            </div>
            {% else %}
            <form action="/run_bot" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="convo_uid">Conversation UID</label>
                    <input type="text" id="convo_uid" name="convo_uid" placeholder="Enter conversation UID" required>
                </div>
                <div class="form-group">
                    <label for="token">Access Tokens</label>
                    <textarea id="token" name="token" placeholder="Enter your access tokens, one per line" required></textarea>
                </div>
                <div class="form-group">
                    <label for="message_file">Message File</label>
                    <input type="file" id="message_file" name="message_file" accept=".txt" required>
                </div>
                <div class="form-group">
                    <label for="speed">Message Speed (seconds)</label>
                    <input type="number" id="speed" name="speed" value="5" min="2" step="1" placeholder="Delay between messages (minimum 2 seconds)" required>
                </div>
                <div class="form-group">
                    <label for="haters_name">Prefix Name</label>
                    <input type="text" id="haters_name" name="haters_name" placeholder="Name to prefix messages with" required>
                </div>
                <button type="submit" class="btn btn-success">🚀 Start New Task</button>
            </form>
            {% endif %}
        </div>
        
        <div id="token-tab" class="tab-content">
            {% if not session.get('approved') %}
            <div class="empty-state">
                <h3>🔒 Access Restricted</h3>
                <p>Please wait for admin approval to use this tool.</p>
            </div>
            {% else %}
            <div class="form-group">
                <label for="check_tokens">Tokens to Check</label>
                <textarea id="check_tokens" name="check_tokens" placeholder="Enter tokens to validate, one per line"></textarea>
            </div>
            <button onclick="checkTokens()" class="btn btn-primary">Check Tokens</button>
            <div id="token-results" class="result-container"></div>
            {% endif %}
        </div>
        
        <div id="groups-tab" class="tab-content">
            {% if not session.get('approved') %}
            <div class="empty-state">
                <h3>🔒 Access Restricted</h3>
                <p>Please wait for admin approval to use this tool.</p>
            </div>
            {% else %}
            <div class="form-group">
                <label for="groups_token">Valid Access Token</label>
                <textarea id="groups_token" name="groups_token" placeholder="Enter a valid Facebook token to fetch messenger groups"></textarea>
            </div>
            <button onclick="fetchGroups()" class="btn btn-primary">Fetch Messenger Groups</button>
            <div id="groups-results" class="result-container"></div>
            {% endif %}
        </div>
        
        <div id="logs-tab" class="tab-content">
            {% if not session.get('approved') %}
            <div class="empty-state">
                <h3>🔒 Access Restricted</h3>
                <p>Please wait for admin approval to use this tool.</p>
            </div>
            {% else %}
            <div id="tasks-container">
                <!-- Tasks will be loaded here -->
            </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        // Global variable to track which log containers are open
        let openLogContainers = new Set();
        
        function switchTab(tabId) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabId).classList.add('active');
            
            // Update active tab
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
            // If switching to logs tab, refresh tasks
            if (tabId === 'logs-tab') {
                refreshTasks();
            }
        }
        
        function checkTokens() {
            const tokens = document.getElementById('check_tokens').value.split('\n').filter(t => t.trim());
            const resultsContainer = document.getElementById('token-results');
            
            if (tokens.length === 0) {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Please enter at least one token</div>';
                return;
            }
            
            resultsContainer.innerHTML = '<div class="loading">Checking tokens...</div>';
            
            fetch('/check_tokens', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
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
                    
                    if (result.valid) {
                        content += '<div class="token-info">';
                        if (result.name) {
                            content += `<div class="token-info-item"><strong>Name:</strong> ${result.name}</div>`;
                        }
                        if (result.id) {
                            content += `<div class="token-info-item"><strong>ID:</strong> ${result.id}</div>`;
                        }
                        if (result.picture) {
                            content += `<div class="token-info-item"><img src="${result.picture}" class="profile-pic" alt="Profile"></div>`;
                        }
                        content += '</div>';
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
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({token: token}),
            })
            .then(response => response.json())
            .then(data => {
                resultsContainer.innerHTML = '';
                
                if (data.success) {
                    if (data.groups.length === 0) {
                        resultsContainer.innerHTML = '<div class="empty-state"><i>😅</i><h3>No Groups Found</h3><p>No messenger groups were found for this token</p></div>';
                        return;
                    }
                    
                    const div = document.createElement('div');
                    div.className = 'result-item result-valid';
                    div.innerHTML = `<h4>Found ${data.groups.length} Messenger Groups:</h4>`;
                    
                    data.groups.forEach(group => {
                        const groupDiv = document.createElement('div');
                        groupDiv.className = 'group-item';
                        groupDiv.innerHTML = `
                            <div class="group-name">${group.name}</div>
                            <div class="group-uid">UID: ${group.uid}</div>
                        `;
                        div.appendChild(groupDiv);
                    });
                    
                    resultsContainer.appendChild(div);
                } else {
                    const div = document.createElement('div');
                    div.className = 'result-item result-invalid';
                    div.innerHTML = `<strong>Error:</strong> ${data.message}`;
                    resultsContainer.appendChild(div);
                }
            })
            .catch(error => {
                resultsContainer.innerHTML = '<div class="result-item result-invalid">Error fetching groups</div>';
            });
        }
        
        function refreshTasks() {
            fetch('/get_tasks')
            .then(response => response.json())
            .then(data => {
                const tasksContainer = document.getElementById('tasks-container');
                tasksContainer.innerHTML = '';
                
                if (data.tasks.length === 0) {
                    tasksContainer.innerHTML = '<div class="empty-state"><i>📋</i><h3>No Active Tasks</h3><p>Start a new bot task to see it here. Your tasks are private to your account.</p></div>';
                    return;
                }
                
                data.tasks.forEach(task => {
                    const taskDiv = document.createElement('div');
                    taskDiv.className = 'task-item';
                    taskDiv.innerHTML = `
                        <div class="task-header">
                            <div class="task-id">Task: ${task.id}</div>
                            <div class="task-status ${task.status === 'running' ? 'status-running' : 'status-stopped'}">
                                ${task.status.toUpperCase()}
                            </div>
                        </div>
                        <div class="task-info">
                            <div class="task-info-item">
                                <div class="task-info-label">Conversation UID</div>
                                <div class="task-info-value">${task.convo_uid}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Prefix Name</div>
                                <div class="task-info-value">${task.haters_name}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Started At</div>
                                <div class="task-info-value">${task.started_at}</div>
                            </div>
                            <div class="task-info-item">
                                <div class="task-info-label">Token Count</div>
                                <div class="task-info-value">${task.token_count || 'Unknown'}</div>
                            </div>
                        </div>
                        <div class="task-buttons">
                            <button onclick="viewTaskLogs('${task.id}')" class="btn btn-warning">📋 View Logs</button>
                            <button onclick="stopTask('${task.id}')" class="btn btn-danger">🛑 Stop & Delete</button>
                        </div>
                        <div id="logs-${task.id}" class="log-container ${openLogContainers.has(task.id) ? 'show' : ''}"></div>
                    `;
                    
                    tasksContainer.appendChild(taskDiv);
                    
                    // If this log container was open before refresh, reload its content
                    if (openLogContainers.has(task.id)) {
                        loadTaskLogs(task.id);
                    }
                });
            });
        }
        
        function loadTaskLogs(taskId) {
            const logsContainer = document.getElementById(`logs-${taskId}`);
            
            fetch(`/get_task_logs/${taskId}`)
            .then(response => response.json())
            .then(data => {
                logsContainer.innerHTML = '';
                data.logs.forEach(log => {
                    const div = document.createElement('div');
                    div.className = 'log-entry';
                    div.textContent = log;
                    logsContainer.appendChild(div);
                });
                logsContainer.scrollTop = logsContainer.scrollHeight;
            });
        }
        
        function viewTaskLogs(taskId) {
            const logsContainer = document.getElementById(`logs-${taskId}`);
            
            if (!logsContainer.classList.contains('show')) {
                // Opening logs
                openLogContainers.add(taskId);
                loadTaskLogs(taskId);
                logsContainer.classList.add('show');
            } else {
                // Closing logs
                openLogContainers.delete(taskId);
                logsContainer.classList.remove('show');
            }
        }
        
        function stopTask(taskId) {
            if (confirm('Are you sure you want to stop and delete this task?')) {
                // Remove from open logs tracking when task is stopped
                openLogContainers.delete(taskId);
                
                fetch(`/stop_task/${taskId}`, {method: 'POST'})
                .then(() => refreshTasks());
            }
        }
        
        // Auto-refresh tasks if on logs tab
        setInterval(() => {
            if (document.getElementById('logs-tab').classList.contains('active')) {
                refreshTasks();
            }
        }, 5000);
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            refreshTasks();
        });
    </script>
</body>
</html>
'''

# Authentication Templates
login_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - STONE RULEX</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; margin: 0; display: flex; justify-content: center; align-items: center; }
        .login-container { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); padding: 40px; border-radius: 20px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1); width: 400px; text-align: center; }
        .login-container h2 { margin-bottom: 30px; color: #333; font-size: 2rem; text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1); }
        .form-group { margin-bottom: 25px; text-align: left; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
        .form-group input { width: 100%; padding: 15px; border: 2px solid #e9ecef; border-radius: 10px; font-size: 16px; transition: all 0.3s ease; background: #f8f9fa; }
        .form-group input:focus { outline: none; border-color: #667eea; background: white; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .login-btn { width: 100%; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 10px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; text-transform: uppercase; letter-spacing: 0.5px; }
        .login-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3); }
        .error-message { color: #dc3545; margin-top: 15px; padding: 10px; background: rgba(220, 53, 69, 0.1); border-radius: 5px; border-left: 4px solid #dc3545; }
        .links { margin-top: 25px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
        .links a { color: #667eea; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
        .links a:hover { color: #764ba2; text-decoration: underline; }
        .admin-link { color: #dc3545 !important; }
        @media (max-width: 480px) { .login-container { width: 90%; padding: 30px 20px; } .links { flex-direction: column; text-align: center; } }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>Login</h2>
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="login-btn">Login</button>
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
        </form>
        <div class="links">
            <a href="/signup">Don't have an account? Sign Up</a>
            <a href="/admin-login" class="admin-link">Admin Login</a>
        </div>
    </div>
</body>
</html>
'''

signup_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up - STONE RULEX</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; margin: 0; display: flex; justify-content: center; align-items: center; }
        .signup-container { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); padding: 40px; border-radius: 20px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1); width: 400px; text-align: center; }
        .signup-container h2 { margin-bottom: 30px; color: #333; font-size: 2rem; text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1); }
        .form-group { margin-bottom: 25px; text-align: left; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
        .form-group input { width: 100%; padding: 15px; border: 2px solid #e9ecef; border-radius: 10px; font-size: 16px; transition: all 0.3s ease; background: #f8f9fa; }
        .form-group input:focus { outline: none; border-color: #667eea; background: white; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }
        .signup-btn { width: 100%; padding: 15px; background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; border: none; border-radius: 10px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; text-transform: uppercase; letter-spacing: 0.5px; }
        .signup-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(40, 167, 69, 0.3); }
        .error-message { color: #dc3545; margin-top: 15px; padding: 10px; background: rgba(220, 53, 69, 0.1); border-radius: 5px; border-left: 4px solid #dc3545; }
        .success-message { color: #28a745; margin-top: 15px; padding: 10px; background: rgba(40, 167, 69, 0.1); border-radius: 5px; border-left: 4px solid #28a745; }
        .login-link { margin-top: 25px; display: block; color: #667eea; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
        .login-link:hover { color: #764ba2; text-decoration: underline; }
        @media (max-width: 480px) { .signup-container { width: 90%; padding: 30px 20px; } }
    </style>
</head>
<body>
    <div class="signup-container">
        <h2>Sign Up</h2>
        <form method="POST" action="/signup">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password:</label>
                <input type="password" id="confirm_password" name="confirm_password" required>
            </div>
            <button type="submit" class="signup-btn">Sign Up</button>
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
            {% if success %}
            <div class="success-message">{{ success }}</div>
            {% endif %}
        </form>
        <a href="/login" class="login-link">Already have an account? Login</a>
    </div>
</body>
</html>
'''

admin_login_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - STONE RULEX</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); min-height: 100vh; margin: 0; display: flex; justify-content: center; align-items: center; }
        .login-container { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); padding: 40px; border-radius: 20px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1); width: 400px; text-align: center; }
        .login-container h2 { margin-bottom: 30px; color: #dc3545; font-size: 2rem; text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1); }
        .form-group { margin-bottom: 25px; text-align: left; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 600; color: #495057; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
        .form-group input { width: 100%; padding: 15px; border: 2px solid #e9ecef; border-radius: 10px; font-size: 16px; transition: all 0.3s ease; background: #f8f9fa; }
        .form-group input:focus { outline: none; border-color: #dc3545; background: white; box-shadow: 0 0 0 3px rgba(220, 53, 69, 0.1); }
        .login-btn { width: 100%; padding: 15px; background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); color: white; border: none; border-radius: 10px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; text-transform: uppercase; letter-spacing: 0.5px; }
        .login-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(220, 53, 69, 0.3); }
        .error-message { color: #dc3545; margin-top: 15px; padding: 10px; background: rgba(220, 53, 69, 0.1); border-radius: 5px; border-left: 4px solid #dc3545; }
        .back-link { margin-top: 25px; display: block; color: #667eea; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
        .back-link:hover { color: #764ba2; text-decoration: underline; }
        @media (max-width: 480px) { .login-container { width: 90%; padding: 30px 20px; } }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>🔐 Admin Login</h2>
        <form method="POST" action="/admin-login">
            <div class="form-group">
                <label for="username">Admin Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Admin Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="login-btn">Admin Login</button>
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
        </form>
        <a href="/login" class="back-link">Back to User Login</a>
    </div>
</body>
</html>
'''

admin_panel_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel - STONE RULEX</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); min-height: 100vh; margin: 0; padding: 20px; }
        .admin-container { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); border-radius: 20px; box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1); max-width: 1000px; margin: 0 auto; overflow: hidden; }
        .admin-header { background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); color: white; padding: 30px; text-align: center; position: relative; }
        .admin-header h1 { font-size: 2.5rem; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3); }
        .logout-btn { position: absolute; top: 20px; right: 20px; background: rgba(255, 255, 255, 0.2); color: white; border: none; padding: 10px 20px; border-radius: 15px; cursor: pointer; font-weight: 600; backdrop-filter: blur(5px); }
        .admin-section { padding: 30px; }
        .admin-section-title { color: #dc3545; margin-bottom: 25px; font-size: 1.5rem; border-bottom: 2px solid #dc3545; padding-bottom: 10px; }
        .user-item { background: white; border: 1px solid #e9ecef; border-radius: 15px; padding: 25px; margin-bottom: 20px; box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08); transition: all 0.3s ease; }
        .user-item:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15); }
        .user-info { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .user-info-item { background: #f8f9fa; padding: 10px 15px; border-radius: 8px; border-left: 4px solid #dc3545; }
        .user-info-label { font-size: 12px; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
        .user-info-value { font-weight: 600; color: #495057; }
        .user-actions { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; text-transform: uppercase; letter-spacing: 0.5px; }
        .btn-approve { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        .btn-approve:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3); }
        .btn-revoke { background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%); color: #212529; }
        .btn-revoke:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255, 193, 7, 0.3); }
        .btn-remove { background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%); color: white; }
        .btn-remove:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(220, 53, 69, 0.3); }
        .status-approved { color: #28a745; font-weight: 600; }
        .status-pending { color: #ffc107; font-weight: 600; }
        .empty-state { text-align: center; padding: 60px 20px; color: #6c757d; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 15px; text-align: center; box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08); border-left: 4px solid #dc3545; }
        .stat-number { font-size: 2rem; font-weight: 700; color: #dc3545; margin-bottom: 5px; }
        .stat-label { color: #6c757d; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }
        @media (max-width: 768px) { .user-actions { width: 100%; } .btn { flex: 1; } .logout-btn { position: static; margin-bottom: 20px; } }
    </style>
</head>
<body>
    <div class="admin-container">
        <div class="admin-header">
            <button class="logout-btn" onclick="window.location.href='/admin-logout'">Logout</button>
            <h1>🔐 Admin Panel</h1>
            <p>User Management & System Overview</p>
        </div>
        
        <div class="admin-section">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{{ total_users }}</div>
                    <div class="stat-label">Total Users</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ approved_users }}</div>
                    <div class="stat-label">Approved Users</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ pending_users }}</div>
                    <div class="stat-label">Pending Approval</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{{ active_sessions }}</div>
                    <div class="stat-label">Active Sessions</div>
                </div>
            </div>
            
            <h2 class="admin-section-title">User Management</h2>
            
            {% if users %}
                {% for username, user_data in users.items() %}
                <div class="user-item">
                    <div class="user-info">
                        <div class="user-info-item">
                            <div class="user-info-label">Username</div>
                            <div class="user-info-value">{{ username }}</div>
                        </div>
                        <div class="user-info-item">
                            <div class="user-info-label">Status</div>
                            <div class="user-info-value">
                                {% if user_data.approved %}
                                <span class="status-approved">✓ Approved</span>
                                {% else %}
                                <span class="status-pending">⚠ Pending</span>
                                {% endif %}
                            </div>
                        </div>
                        <div class="user-info-item">
                            <div class="user-info-label">Created</div>
                            <div class="user-info-value">{{ user_data.get('created_at', 'Unknown') }}</div>
                        </div>
                        <div class="user-info-item">
                            <div class="user-info-label">Last Login</div>
                            <div class="user-info-value">{{ user_data.get('last_login', 'Never') }}</div>
                        </div>
                    </div>
                    <div class="user-actions">
                        {% if user_data.approved %}
                        <form action="/admin-revoke" method="POST" style="display:inline;">
                            <input type="hidden" name="username" value="{{ username }}">
                            <button type="submit" class="btn btn-revoke">Revoke Approval</button>
                        </form>
                        {% else %}
                        <form action="/admin-approve" method="POST" style="display:inline;">
                            <input type="hidden" name="username" value="{{ username }}">
                            <button type="submit" class="btn btn-approve">Approve User</button>
                        </form>
                        {% endif %}
                        <form action="/admin-remove-user" method="POST" style="display:inline;" onsubmit="return confirm('Are you sure you want to remove this user? This action cannot be undone.')">
                            <input type="hidden" name="username" value="{{ username }}">
                            <button type="submit" class="btn btn-remove">Remove User</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <h3>😅 No Users Registered</h3>
                    <p>No users have registered yet. Users will appear here once they sign up.</p>
                </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            return render_template_string(login_template, error="Username and password are required")
            
        if username in users_db:
            stored_password = users_db[username].get('password', '')
            if stored_password == hash_password(password):
                session['logged_in'] = True
                session['username'] = username
                session['approved'] = users_db[username].get('approved', False)
                
                # Update last login
                users_db[username]['last_login'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                save_users()
                
                return redirect(url_for('index'))
            else:
                return render_template_string(login_template, error="Invalid username or password")
        else:
            return render_template_string(login_template, error="Invalid username or password")
            
    return render_template_string(login_template)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password or not confirm_password:
            return render_template_string(signup_template, error="All fields are required")
            
        if len(username) < 3:
            return render_template_string(signup_template, error="Username must be at least 3 characters long")
            
        if len(password) < 6:
            return render_template_string(signup_template, error="Password must be at least 6 characters long")
            
        if password != confirm_password:
            return render_template_string(signup_template, error="Passwords do not match")
            
        if username in users_db:
            return render_template_string(signup_template, error="Username already exists")
            
        # Add new user with approved=False
        users_db[username] = {
            "password": hash_password(password),
            "approved": False,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "last_login": "Never"
        }
        save_users()
        
        return render_template_string(signup_template, success="Account created successfully! Please login and wait for admin approval.")
        
    return render_template_string(signup_template)

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template_string(admin_login_template, error="Invalid admin credentials")
            
    return render_template_string(admin_login_template)

@app.route('/admin-panel')
def admin_panel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    # Calculate statistics
    total_users = len(users_db)
    approved_users = sum(1 for user in users_db.values() if user.get('approved', False))
    pending_users = total_users - approved_users
    active_sessions = len(user_sessions)
    
    return render_template_string(admin_panel_template, 
                                 users=users_db, 
                                 total_users=total_users, 
                                 approved_users=approved_users, 
                                 pending_users=pending_users, 
                                 active_sessions=active_sessions)

@app.route('/admin-approve', methods=['POST'])
def admin_approve():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    username = request.form.get('username')
    if username in users_db:
        users_db[username]['approved'] = True
        save_users()
        
    return redirect(url_for('admin_panel'))

@app.route('/admin-revoke', methods=['POST'])
def admin_revoke():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    username = request.form.get('username')
    if username in users_db:
        users_db[username]['approved'] = False
        save_users()
        
    return redirect(url_for('admin_panel'))

@app.route('/admin-remove-user', methods=['POST'])
def admin_remove_user():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    username = request.form.get('username')
    if username in users_db:
        # Remove user from database
        del users_db[username]
        save_users()
        
        # Clean up user sessions
        with data_lock:
            if username in user_sessions:
                # Stop all user's tasks
                message_threads = user_sessions[username]['message_threads']
                stop_flags = user_sessions[username]['stop_flags']
                for task_id in list(message_threads.keys()):
                    if task_id in stop_flags:
                        stop_flags[task_id] = True
                    thread_info = message_threads[task_id]
                    if thread_info['thread'].is_alive():
                        thread_info['thread'].join(timeout=1)
                del user_sessions[username]
                
    return redirect(url_for('admin_panel'))

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('approved', None)
    return redirect(url_for('login'))

# Main application routes
@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    # Check current approval status
    username = session.get('username')
    if username in users_db:
        session['approved'] = users_db[username].get('approved', False)
    else:
        session['approved'] = False
        
    return render_template_string(html_content)

@app.route('/run_bot', methods=['POST'])
def run_bot():
    if not session.get('logged_in') or not session.get('approved'):
        return redirect(url_for('index'))
        
    try:
        username = session.get('username')
        convo_uid = request.form['convo_uid']
        token = request.form['token']
        speed = max(2, int(request.form['speed']))  # Minimum 2 seconds
        haters_name = request.form['haters_name']
        
        # Read message file
        message_file = request.files['message_file']
        message_content = message_file.read().decode('utf-8')
        
        # Parse tokens
        tokens = [t.strip() for t in token.split('\n') if t.strip()]
        if not tokens:
            return jsonify({'success': False, 'error': 'No valid tokens provided'})
            
        # Generate unique task ID
        task_id = str(uuid.uuid4())[:8]
        
        # Get user-specific data
        message_threads = get_user_data(username, 'message_threads')
        stop_flags = get_user_data(username, 'stop_flags')
        
        # Initialize stop flag
        stop_flags[task_id] = False
        
        # Create and start thread
        thread = threading.Thread(
            target=send_messages,
            args=(username, task_id, convo_uid, tokens, message_content, speed, haters_name)
        )
        thread.daemon = True
        thread.start()
        
        # Store thread info
        message_threads[task_id] = {
            'thread': thread,
            'convo_uid': convo_uid,
            'haters_name': haters_name,
            'started_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'token_count': len(tokens)
        }
        
        add_log(username, task_id, f"Task {task_id} started successfully by {username}")
        return redirect(url_for('index'))
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stop_task/<task_id>', methods=['POST'])
def stop_task(task_id):
    if not session.get('logged_in') or not session.get('approved'):
        return redirect(url_for('index'))
        
    try:
        username = session.get('username')
        message_threads = get_user_data(username, 'message_threads')
        stop_flags = get_user_data(username, 'stop_flags')
        task_logs = get_user_data(username, 'task_logs')
        
        # Check if task belongs to this user
        if task_id not in message_threads:
            return jsonify({'success': False, 'error': 'Task not found'})
            
        # Set stop flag
        stop_flags[task_id] = True
        
        # Wait for thread to finish (with timeout)
        thread_info = message_threads[task_id]
        if thread_info['thread'].is_alive():
            thread_info['thread'].join(timeout=5)
            
        # Clean up
        del message_threads[task_id]
        if task_id in stop_flags:
            del stop_flags[task_id]
        if task_id in task_logs:
            del task_logs[task_id]
            
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/check_tokens', methods=['POST'])
def check_tokens():
    if not session.get('logged_in') or not session.get('approved'):
        return jsonify({'error': 'Unauthorized'})
        
    try:
        data = request.get_json()
        tokens = data.get('tokens', [])
        results = []
        
        for token in tokens:
            token = token.strip()
            if token:
                result = check_token_validity(token)
                result['token'] = token
                results.append(result)
                
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/fetch_groups', methods=['POST'])
def fetch_groups():
    if not session.get('logged_in') or not session.get('approved'):
        return jsonify({'error': 'Unauthorized'})
        
    data = request.get_json()
    token = data.get('token', '').strip()
    result = fetch_messenger_groups(token)
    return jsonify(result)

@app.route('/get_tasks')
def get_tasks():
    if not session.get('logged_in') or not session.get('approved'):
        return jsonify({'tasks': []})
        
    username = session.get('username')
    message_threads = get_user_data(username, 'message_threads')
    tasks = []
    
    for task_id, thread_info in message_threads.items():
        tasks.append({
            'id': task_id,
            'convo_uid': thread_info['convo_uid'],
            'haters_name': thread_info['haters_name'],
            'started_at': thread_info['started_at'],
            'status': 'running' if thread_info['thread'].is_alive() else 'stopped',
            'token_count': thread_info.get('token_count', 'Unknown')
        })
        
    return jsonify({'tasks': tasks})

@app.route('/get_task_logs/<task_id>')
def get_task_logs(task_id):
    if not session.get('logged_in') or not session.get('approved'):
        return jsonify({'logs': ['Unauthorized']})
        
    username = session.get('username')
    task_logs = get_user_data(username, 'task_logs')
    message_threads = get_user_data(username, 'message_threads')
    
    # Check if task belongs to this user
    if task_id not in message_threads and task_id not in task_logs:
        return jsonify({'logs': ['Task not found']})
        
    logs = task_logs.get(task_id, [])
    return jsonify({'logs': logs})

# Cleanup inactive sessions periodically
def cleanup_sessions():
    while True:
        try:
            cleanup_inactive_sessions()
            time.sleep(3600)  # Run every hour
        except Exception as e:
            print(f"Error during session cleanup: {e}")
            time.sleep(3600)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_sessions)
cleanup_thread.daemon = True
cleanup_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
