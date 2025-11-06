from flask import Flask, render_template_string, request, jsonify, session
import requests
import json
import time
import threading
from datetime import datetime
import random
import re

app = Flask(__name__)
app.secret_key = 'facebook-messenger-secret-key-12345'

# Global variables
message_queue = []
is_sending = False
current_status = "Ready"
send_logs = []

# HTML Template with better logging
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
        .log-entry { padding: 5px; margin: 2px 0; border-radius: 3px; font-family: monospace; font-size: 12px; }
        .log-success { background: #d4edda; color: #155724; }
        .log-error { background: #f8d7da; color: #721c24; }
        .log-info { background: #d1ecf1; color: #0c5460; }
        .log-warning { background: #fff3cd; color: #856404; }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <div class="card">
                    <div class="card-header bg-primary text-white text-center">
                        <h4 class="mb-0">📨 Facebook Messenger</h4>
                        <small>Debug Mode - Private Conversations</small>
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
                            <div class="row">
                                <div class="col-md-6">
                                    <input type="text" id="recipientUid" class="form-control mb-2" placeholder="User UID (1000xxxxxxxxx)">
                                </div>
                                <div class="col-md-6">
                                    <input type="number" id="speed" class="form-control mb-2" value="20" min="15">
                                </div>
                            </div>
                            <input type="text" id="prefix" class="form-control mb-2" placeholder="Prefix (optional)">
                            <textarea id="messageText" class="form-control mb-2" rows="3" placeholder="Type your message here..."></textarea>
                            <small class="text-muted">Use personal user ID, not group ID. Minimum 15 seconds delay.</small>
                        </div>

                        <!-- Controls -->
                        <div class="mb-3 text-center">
                            <button onclick="startMessaging()" class="btn btn-success btn-lg">🚀 Start Messaging</button>
                            <button onclick="stopMessaging()" class="btn btn-danger btn-lg">🛑 Stop</button>
                            <button onclick="clearLogs()" class="btn btn-warning btn-lg">🗑️ Clear Logs</button>
                        </div>

                        <!-- Status -->
                        <div class="mb-3">
                            <h6>📊 Real-time Status</h6>
                            <div id="status" class="alert alert-info">
                                <span class="status-indicator status-inactive"></span>
                                <span id="statusText">Ready to start</span>
                                <br>
                                <small id="statusDetail" class="text-muted">Waiting for action...</small>
                            </div>
                        </div>

                        <!-- Debug Logs -->
                        <div class="mb-3">
                            <h6>🐛 Debug Logs</h6>
                            <div id="debugLogs" class="border rounded p-2 bg-light" style="height: 300px; overflow-y: auto; font-size: 12px;"></div>
                        </div>

                        <!-- Send Logs -->
                        <div>
                            <h6>📨 Send Attempt Logs</h6>
                            <div id="sendLogs" class="border rounded p-2 bg-white" style="height: 200px; overflow-y: auto;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function addDebugLog(message, type = 'info') {
            const logs = document.getElementById('debugLogs');
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry log-${type}`;
            logEntry.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
            logs.appendChild(logEntry);
            logs.scrollTop = logs.scrollHeight;
        }

        function addSendLog(message, success = true) {
            const logs = document.getElementById('sendLogs');
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            logEntry.className = success ? 'log-entry log-success' : 'log-entry log-error';
            logEntry.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
            logs.appendChild(logEntry);
            logs.scrollTop = logs.scrollHeight;
        }

        async function uploadCookies() {
            const fileInput = document.getElementById('cookiesFile');
            if (!fileInput.files[0]) {
                addDebugLog('Please select cookies file', 'error'); return;
            }
            
            addDebugLog('Starting cookies upload...', 'info');
            const formData = new FormData();
            formData.append('cookies_file', fileInput.files[0]);
            
            try {
                const response = await fetch('/upload_cookies', { method: 'POST', body: formData });
                const result = await response.json();
                if (result.success) {
                    addDebugLog('Cookies uploaded successfully!', 'success');
                    addDebugLog(`Found ${result.cookie_count} cookies`, 'info');
                    addDebugLog(`User ID: ${result.user_id}`, 'info');
                } else {
                    addDebugLog('Upload failed: ' + result.error, 'error');
                }
            } catch (error) {
                addDebugLog('Upload error: ' + error, 'error');
            }
        }

        async function startMessaging() {
            const uid = document.getElementById('recipientUid').value;
            const message = document.getElementById('messageText').value;
            const prefix = document.getElementById('prefix').value;
            const speed = document.getElementById('speed').value;

            if (!uid || !message) {
                addDebugLog('Please fill UID and Message fields', 'error'); return;
            }

            if (speed < 15) {
                addDebugLog('Delay should be at least 15 seconds for safety', 'warning');
            }

            addDebugLog(`Starting messaging to UID: ${uid}`, 'info');
            addDebugLog(`Message: ${message}`, 'info');
            addDebugLog(`Delay: ${speed} seconds`, 'info');

            try {
                const response = await fetch('/start_messaging', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        uid: uid, 
                        message: message, 
                        prefix: prefix, 
                        speed: parseInt(speed)
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    addDebugLog('Messaging process started successfully!', 'success');
                    updateStatus();
                } else {
                    addDebugLog('Start failed: ' + result.error, 'error');
                }
            } catch (error) {
                addDebugLog('Start error: ' + error, 'error');
            }
        }

        async function stopMessaging() {
            try {
                await fetch('/stop_messaging', {method: 'POST'});
                addDebugLog('Messaging stopped by user', 'warning');
            } catch (error) {
                addDebugLog('Stop error: ' + error, 'error');
            }
        }

        function clearLogs() {
            document.getElementById('debugLogs').innerHTML = '';
            document.getElementById('sendLogs').innerHTML = '';
            addDebugLog('Logs cleared', 'info');
        }

        async function updateStatus() {
            try {
                const response = await fetch('/status');
                const status = await response.json();
                
                const indicator = document.querySelector('.status-indicator');
                const statusText = document.getElementById('statusText');
                const statusDetail = document.getElementById('statusDetail');
                
                if (status.is_sending) {
                    indicator.className = 'status-indicator status-active';
                    statusText.textContent = status.status;
                    statusDetail.textContent = `Queue: ${status.queue_length} | Last: ${status.last_activity}`;
                } else {
                    indicator.className = 'status-indicator status-inactive';
                    statusText.textContent = 'Ready to start';
                    statusDetail.textContent = 'Waiting for action...';
                }

                // Update send logs
                if (status.send_logs) {
                    status.send_logs.forEach(log => {
                        if (!window.displayedLogs) window.displayedLogs = new Set();
                        const logKey = `${log.timestamp}-${log.message}`;
                        if (!window.displayedLogs.has(logKey)) {
                            addSendLog(`${log.message} - ${log.status}`, log.success);
                            window.displayedLogs.add(logKey);
                        }
                    });
                }
                
            } catch (error) {
                console.error('Status update error:', error);
            }
        }

        // Auto-update every 3 seconds
        setInterval(updateStatus, 3000);
        
        // Initial call
        updateStatus();

        addDebugLog('Application loaded. Upload cookies to begin.', 'info');
    </script>
</body>
</html>
'''

class FacebookMessenger:
    def __init__(self, cookies_data):
        self.cookies = cookies_data
        self.session = requests.Session()
        self.setup_session()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
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
            print("✅ Session setup completed")
        except Exception as e:
            print(f"❌ Cookie setup error: {e}")
    
    def get_user_id(self):
        """Get user ID from cookies"""
        for cookie in self.cookies:
            if cookie['name'] == 'c_user':
                return cookie['value']
        return None

    def get_fb_dtsg(self):
        """Extract fb_dtsg token from Facebook"""
        try:
            url = "https://www.facebook.com"
            response = self.session.get(url, timeout=10)
            match = re.search(r'"token":"([^"]+)"', response.text)
            if match:
                return match.group(1)
        except:
            pass
        return "NA"

    def send_message_direct(self, recipient_uid, message_text):
        """Direct message sending method for private conversations"""
        try:
            # Get the messaging page first to extract tokens
            msg_url = f"https://www.facebook.com/messages/t/{recipient_uid}"
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.facebook.com/',
                'DNT': '1'
            }
            
            # Get the page to extract tokens
            response = self.session.get(msg_url, headers=headers, timeout=30)
            print(f"📄 Page fetch status: {response.status_code}")
            
            if response.status_code != 200:
                return {'success': False, 'error': f'Page fetch failed: {response.status_code}'}
            
            # Extract fb_dtsg from the page
            fb_dtsg = self.extract_fb_dtsg(response.text)
            print(f"🔑 FB_DTSG: {fb_dtsg[:20]}..." if fb_dtsg else "❌ No FB_DTSG found")
            
            # Try to send using the send endpoint
            send_url = "https://www.facebook.com/messages/send/"
            send_headers = {
                'User-Agent': self.user_agent,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.facebook.com',
                'Referer': msg_url,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            payload = {
                'ids[{}]'.format(recipient_uid): recipient_uid,
                'body': message_text,
                'waterfall_source': 'message',
                't': int(time.time() * 1000),
                'fb_dtsg': fb_dtsg if fb_dtsg else 'NA'
            }
            
            print(f"📤 Sending message to {recipient_uid}")
            send_response = self.session.post(send_url, headers=send_headers, data=payload, timeout=30)
            
            result = {
                'success': send_response.status_code == 200,
                'status_code': send_response.status_code,
                'response_preview': send_response.text[:100] if send_response.text else 'No response',
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'method': 'direct'
            }
            
            print(f"📨 Send result: {result}")
            return result
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'method': 'direct'
            }
            print(f"❌ Send error: {e}")
            return error_result

    def extract_fb_dtsg(self, html_content):
        """Extract fb_dtsg token from HTML"""
        try:
            # Multiple patterns to find fb_dtsg
            patterns = [
                r'name="fb_dtsg" value="([^"]+)"',
                r'"token":"([^"]+)"',
                r'fb_dtsg["\']\s*:\s*["\']([^"\']+)',
                r'DTSGInitData".*?token["\']\s*:\s*["\']([^"\']+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html_content, re.DOTALL)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            print(f"❌ FB_DTSG extraction error: {e}")
            return None

    def send_message(self, recipient_uid, message_text):
        """Main message sending method"""
        print(f"🎯 Attempting to send to private conversation: {recipient_uid}")
        
        # Try direct method first
        result = self.send_message_direct(recipient_uid, message_text)
        
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
        
        # Validate cookies
        user_id = None
        for cookie in cookies_data:
            if cookie.get('name') == 'c_user':
                user_id = cookie.get('value')
                break
        
        session['cookies'] = cookies_data
        session['user_id'] = user_id
        
        return jsonify({
            'success': True, 
            'message': 'Cookies uploaded successfully',
            'cookie_count': len(cookies_data),
            'user_id': user_id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/start_messaging', methods=['POST'])
def start_messaging():
    global is_sending, message_queue, send_logs
    
    try:
        data = request.json
        recipient_uid = data.get('uid')
        message = data.get('message')
        prefix = data.get('prefix', '')
        speed = int(data.get('speed', 20))
        
        if not recipient_uid or not message:
            return jsonify({'success': False, 'error': 'UID and Message required'})
        
        if 'cookies' not in session:
            return jsonify({'success': False, 'error': 'Please upload cookies first'})
        
        # Prepare message
        final_message = f"{prefix} {message}".strip() if prefix else message
        message_queue = [final_message]
        is_sending = True
        send_logs = []  # Reset logs
        
        # Start background thread
        thread = threading.Thread(
            target=send_messages_worker,
            args=(session['cookies'], recipient_uid, message_queue, speed)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True, 
            'message': 'Messaging started',
            'queue_length': len(message_queue)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stop_messaging', methods=['POST'])
def stop_messaging():
    global is_sending
    is_sending = False
    return jsonify({'success': True, 'message': 'Messaging stopped'})

@app.route('/status')
def get_status():
    global current_status, is_sending, message_queue, send_logs
    return jsonify({
        'is_sending': is_sending,
        'status': current_status,
        'queue_length': len(message_queue),
        'last_activity': datetime.now().strftime("%H:%M:%S"),
        'send_logs': send_logs[-10:]  # Last 10 logs
    })

def send_messages_worker(cookies_data, recipient_uid, messages, delay):
    """Background worker for sending messages"""
    global is_sending, current_status, send_logs
    
    messenger = FacebookMessenger(cookies_data)
    sent_count = 0
    
    for i, message in enumerate(messages):
        if not is_sending:
            current_status = "Stopped by user"
            break
            
        current_status = f"Sending message {i+1}/{len(messages)}"
        print(f"🔄 Worker: Sending message {i+1}")
        
        # Send message
        result = messenger.send_message(recipient_uid, message)
        
        # Log the result
        log_entry = {
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'message': f"Message {i+1} to {recipient_uid}",
            'status': f"Status: {result['status_code']}",
            'success': result['success'],
            'method': result.get('method', 'unknown')
        }
        send_logs.append(log_entry)
        
        if result['success']:
            sent_count += 1
            print(f"✅ Successfully sent message {i+1}")
        else:
            print(f"❌ Failed to send message {i+1}: {result.get('error', 'Unknown error')}")
        
        # Wait before next message
        if i < len(messages) - 1:
            for remaining in range(delay, 0, -1):
                if not is_sending:
                    break
                current_status = f"Waiting {remaining}s... ({i+1}/{len(messages)})"
                time.sleep(1)
    
    is_sending = False
    current_status = f"Completed - {sent_count}/{len(messages)} sent"
    print(f"🎉 Messaging completed: {sent_count}/{len(messages)}")

if __name__ == '__main__':
    print("🚀 Starting Debug Facebook Messenger...")
    print("📍 http://localhost:5000")
    print("🐛 Debug mode enabled - Check browser console for detailed logs")
    app.run(debug=True, host='0.0.0.0', port=5000)
