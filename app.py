from flask import Flask, render_template_string, request, jsonify, session
import requests
import json
import time
import threading
from datetime import datetime
import random

app = Flask(__name__)
app.secret_key = 'facebook-messenger-secret-key-12345'

# Global variables
message_queue = []
is_sending = False
current_status = "Ready"

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ur">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Messenger App</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card { border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); border: none; background: rgba(255, 255, 255, 0.95); }
        .btn-primary { background: linear-gradient(45deg, #667eea, #764ba2); border: none; }
        .status-indicator { width: 15px; height: 15px; border-radius: 50%; display: inline-block; margin-right: 10px; }
        .status-active { background-color: #28a745; animation: pulse 2s infinite; }
        .status-inactive { background-color: #dc3545; }
        @keyframes pulse { 0% { transform: scale(0.95); opacity: 0.7; } 50% { transform: scale(1.1); opacity: 1; } 100% { transform: scale(0.95); opacity: 0.7; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header bg-primary text-white text-center">
                        <h4 class="mb-0">📨 Facebook Messenger</h4>
                        <small>Updated Version</small>
                    </div>
                    <div class="card-body">
                        <!-- Cookies Upload -->
                        <div class="mb-3">
                            <h6>🔐 Step 1: Upload Cookies</h6>
                            <input type="file" id="cookiesFile" class="form-control" accept=".json">
                            <button onclick="uploadCookies()" class="btn btn-primary mt-2">Upload Cookies</button>
                            <div id="cookiesStatus" class="mt-2"></div>
                        </div>

                        <!-- Message Settings -->
                        <div class="mb-3">
                            <h6>✉️ Step 2: Message Settings</h6>
                            <input type="text" id="recipientUid" class="form-control mb-2" placeholder="Facebook User UID">
                            <textarea id="messageText" class="form-control mb-2" rows="3" placeholder="Message text"></textarea>
                            <input type="text" id="prefix" class="form-control mb-2" placeholder="Prefix (optional)">
                            <input type="number" id="speed" class="form-control" value="15" min="10">
                            <small class="text-muted">Minimum 10 seconds delay recommended</small>
                        </div>

                        <!-- Controls -->
                        <div class="mb-3 text-center">
                            <button onclick="startMessaging()" class="btn btn-success btn-lg">🚀 Start</button>
                            <button onclick="stopMessaging()" class="btn btn-danger btn-lg">🛑 Stop</button>
                        </div>

                        <!-- Status -->
                        <div class="mb-3">
                            <h6>📊 Status</h6>
                            <div id="status" class="alert alert-info">
                                <span class="status-indicator status-inactive"></span>
                                <span id="statusText">Ready</span>
                            </div>
                        </div>

                        <!-- Logs -->
                        <div>
                            <h6>📝 Logs</h6>
                            <div id="logs" class="border rounded p-2 bg-light" style="height: 200px; overflow-y: auto;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function addLog(message, type = 'info') {
            const logs = document.getElementById('logs');
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            logEntry.innerHTML = `<small>[${timestamp}] ${message}</small>`;
            if (type === 'error') logEntry.classList.add('text-danger');
            if (type === 'success') logEntry.classList.add('text-success');
            logs.appendChild(logEntry);
            logs.scrollTop = logs.scrollHeight;
        }

        async function uploadCookies() {
            const fileInput = document.getElementById('cookiesFile');
            if (!fileInput.files[0]) {
                addLog('Please select cookies file', 'error'); return;
            }
            const formData = new FormData();
            formData.append('cookies_file', fileInput.files[0]);
            try {
                const response = await fetch('/upload_cookies', { method: 'POST', body: formData });
                const result = await response.json();
                if (result.success) {
                    addLog('Cookies uploaded successfully', 'success');
                } else {
                    addLog('Upload failed: ' + result.error, 'error');
                }
            } catch (error) {
                addLog('Upload error: ' + error, 'error');
            }
        }

        async function startMessaging() {
            const uid = document.getElementById('recipientUid').value;
            const message = document.getElementById('messageText').value;
            const prefix = document.getElementById('prefix').value;
            const speed = document.getElementById('speed').value;

            if (!uid || !message) {
                addLog('Please fill UID and Message', 'error'); return;
            }

            try {
                const response = await fetch('/start_messaging', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({uid: uid, message: message, prefix: prefix, speed: parseInt(speed)})
                });
                const result = await response.json();
                if (result.success) {
                    addLog('Messaging started', 'success');
                } else {
                    addLog('Start failed: ' + result.error, 'error');
                }
            } catch (error) {
                addLog('Start error: ' + error, 'error');
            }
        }

        async function stopMessaging() {
            try {
                await fetch('/stop_messaging', {method: 'POST'});
                addLog('Messaging stopped', 'warning');
            } catch (error) {
                addLog('Stop error: ' + error, 'error');
            }
        }

        async function updateStatus() {
            try {
                const response = await fetch('/status');
                const status = await response.json();
                const indicator = document.querySelector('.status-indicator');
                const statusText = document.getElementById('statusText');
                if (status.is_sending) {
                    indicator.className = 'status-indicator status-active';
                    statusText.textContent = status.status;
                } else {
                    indicator.className = 'status-indicator status-inactive';
                    statusText.textContent = 'Ready';
                }
            } catch (error) {
                console.error('Status error:', error);
            }
        }
        setInterval(updateStatus, 2000);
    </script>
</body>
</html>
'''

class FacebookMessenger:
    def __init__(self, cookies_data):
        self.cookies = cookies_data
        self.session = requests.Session()
        self.setup_session()
    
    def setup_session(self):
        """Setup session with cookies"""
        try:
            for cookie in self.cookies:
                self.session.cookies.set(
                    cookie['name'], 
                    cookie['value'],
                    domain=cookie.get('domain', '.facebook.com'),
                    path=cookie.get('path', '/')
                )
        except Exception as e:
            print(f"Cookie setup error: {e}")
    
    def get_message_form_data(self, recipient_uid, message_text):
        """Get current Facebook message form data"""
        try:
            # First, get the conversation page to extract form data
            url = f"https://www.facebook.com/messages/t/{recipient_uid}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = self.session.get(url, headers=headers, timeout=30)
            print(f"Page fetch status: {response.status_code}")
            
            if response.status_code == 200:
                return self.extract_send_params(response.text, recipient_uid, message_text)
            else:
                print(f"Failed to fetch page: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error getting form data: {e}")
            return None
    
    def extract_send_params(self, html_content, recipient_uid, message_text):
        """Extract sending parameters from HTML"""
        try:
            # This is a simplified version - in real scenario, you'd parse the HTML
            # to get fb_dtsg, jazoest, and other required parameters
            
            import re
            
            # Extract fb_dtsg token
            fb_dtsg_match = re.search(r'name="fb_dtsg" value="([^"]+)"', html_content)
            fb_dtsg = fb_dtsg_match.group(1) if fb_dtsg_match else "NA"
            
            # Extract jazoest token
            jazoest_match = re.search(r'name="jazoest" value="([^"]+)"', html_content)
            jazoest = jazoest_match.group(1) if jazoest_match else "NA"
            
            # For now, return a basic payload
            # In production, you'd need to extract all required parameters
            payload = {
                'fb_dtsg': fb_dtsg,
                'jazoest': jazoest,
                'body': message_text,
                'send': 'Send',
                'tids': f"cid.c.{recipient_uid}",
                'wwwupp': 'C3',
                'platform': 'wwww',
                'sound': 'false',
                'ids[{recipient_uid}]': recipient_uid,
            }
            
            return payload
            
        except Exception as e:
            print(f"Error extracting params: {e}")
            return None
    
    def send_message_simplified(self, recipient_uid, message_text):
        """Simplified message sending approach"""
        try:
            # Use mobile API endpoint which might be simpler
            url = "https://m.facebook.com/messages/send/"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://m.facebook.com',
                'Referer': f'https://m.facebook.com/messages/t/{recipient_uid}',
                'X-Requested-With': 'XMLHttpRequest',
            }
            
            # Basic payload
            payload = {
                'body': message_text,
                'ids[{}]'.format(recipient_uid): recipient_uid,
                'send': 'Send',
                't': int(time.time() * 1000),
            }
            
            response = self.session.post(url, headers=headers, data=payload, timeout=30)
            
            result = {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response_text': response.text[:200] if response.text else '',
                'timestamp': datetime.now().strftime("%H:%M:%S")
            }
            
            print(f"Send result: {result}")
            return result
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().strftime("%H:%M:%S")
            }
            print(f"Send error: {e}")
            return error_result

    def send_message_advanced(self, recipient_uid, message_text):
        """Advanced message sending using GraphQL"""
        try:
            # GraphQL endpoint for messages
            url = "https://www.facebook.com/api/graphql/"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.facebook.com',
                'Referer': f'https://www.facebook.com/messages/t/{recipient_uid}',
                'X-Requested-With': 'XMLHttpRequest',
            }
            
            # This would need actual GraphQL query from Facebook
            # For now, using a basic approach
            payload = {
                'av': recipient_uid,
                'message_batch[0][action_type]': 'ma-type:user-generated-message',
                'message_batch[0][author]': 'fbid:{}'.format(self.get_user_id()),
                'message_batch[0][ephemeral_ttl_mode]': '0',
                'message_batch[0][is_unread]': 'false',
                'message_batch[0][message]': message_text,
                'message_batch[0][offline_threading_id]': self.generate_threading_id(),
                'message_batch[0][source]': 'source:chat:web',
                'message_batch[0][specific_to_list][0]': 'fbid:{}'.format(recipient_uid),
                'message_batch[0][thread_fbid]': recipient_uid,
                'message_batch[0][timestamp]': str(int(time.time() * 1000)),
            }
            
            response = self.session.post(url, headers=headers, data=payload, timeout=30)
            
            result = {
                'success': 'error' not in response.text.lower() and response.status_code == 200,
                'status_code': response.status_code,
                'timestamp': datetime.now().strftime("%H:%M:%S")
            }
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_user_id(self):
        """Extract user ID from cookies"""
        for cookie in self.cookies:
            if cookie['name'] == 'c_user':
                return cookie['value']
        return None

    def generate_threading_id(self):
        """Generate offline threading ID"""
        return str(random.randint(10**17, 10**18 - 1))

    def send_message(self, recipient_uid, message_text):
        """Main message sending method - tries multiple approaches"""
        print(f"Attempting to send message to {recipient_uid}")
        
        # Try simplified approach first
        result = self.send_message_simplified(recipient_uid, message_text)
        
        if not result['success']:
            print("Simplified approach failed, trying advanced...")
            # Try advanced approach
            result = self.send_message_advanced(recipient_uid, message_text)
        
        return result

# Flask Routes
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/upload_cookies', methods=['POST'])
def upload_cookies():
    try:
        cookies_file = request.files['cookies_file']
        cookies_data = json.load(cookies_file)
        session['cookies'] = cookies_data
        return jsonify({'success': True, 'message': 'Cookies uploaded'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/start_messaging', methods=['POST'])
def start_messaging():
    global is_sending, message_queue
    try:
        data = request.json
        recipient_uid = data.get('uid')
        message = data.get('message')
        prefix = data.get('prefix', '')
        speed = int(data.get('speed', 15))
        
        if not recipient_uid or not message:
            return jsonify({'success': False, 'error': 'UID and Message required'})
        
        if 'cookies' not in session:
            return jsonify({'success': False, 'error': 'Upload cookies first'})
        
        message_queue = [f"{prefix} {message}".strip() if prefix else message]
        is_sending = True
        
        thread = threading.Thread(
            target=send_messages_worker,
            args=(session['cookies'], recipient_uid, message_queue, speed)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Started'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stop_messaging', methods=['POST'])
def stop_messaging():
    global is_sending
    is_sending = False
    return jsonify({'success': True, 'message': 'Stopped'})

@app.route('/status')
def get_status():
    global current_status, is_sending
    return jsonify({
        'is_sending': is_sending,
        'status': current_status,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

def send_messages_worker(cookies_data, recipient_uid, messages, delay):
    global is_sending, current_status
    messenger = FacebookMessenger(cookies_data)
    
    for i, message in enumerate(messages):
        if not is_sending:
            break
            
        current_status = f"Sending {i+1}/{len(messages)}"
        print(f"Worker: Sending message {i+1}")
        
        result = messenger.send_message(recipient_uid, message)
        print(f"Worker: Send result: {result}")
        
        if i < len(messages) - 1:
            for remaining in range(delay, 0, -1):
                if not is_sending:
                    break
                current_status = f"Wait {remaining}s"
                time.sleep(1)
    
    is_sending = False
    current_status = "Completed"

if __name__ == '__main__':
    print("🚀 Starting Updated Facebook Messenger...")
    print("📍 http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
