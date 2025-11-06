from flask import Flask, render_template_string, request, jsonify, session
import requests
import json
import time
import threading
from datetime import datetime
import os
import uuid

app = Flask(__name__)
app.secret_key = 'facebook-messenger-secret-key-12345'

# Global variables for message sending
message_queue = []
is_sending = False
current_status = "Ready"

# HTML Template as string
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ur">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Messenger App</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .card {
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            border: none;
            backdrop-filter: blur(10px);
            background: rgba(255, 255, 255, 0.95);
        }
        .btn-primary {
            background: linear-gradient(45deg, #667eea, #764ba2);
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: 600;
        }
        .btn-success {
            background: linear-gradient(45deg, #28a745, #20c997);
            border: none;
            border-radius: 8px;
            padding: 12px 25px;
            font-weight: 600;
        }
        .btn-danger {
            background: linear-gradient(45deg, #dc3545, #e83e8c);
            border: none;
            border-radius: 8px;
            padding: 12px 25px;
            font-weight: 600;
        }
        .status-indicator {
            width: 15px;
            height: 15px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        .status-active {
            background-color: #28a745;
        }
        .status-inactive {
            background-color: #dc3545;
            animation: none;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.7; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.7; }
        }
        .form-control {
            border-radius: 8px;
            border: 2px solid #e9ecef;
            padding: 12px 15px;
            transition: all 0.3s ease;
        }
        .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        .log-entry {
            padding: 8px 12px;
            margin: 5px 0;
            border-radius: 5px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
        }
        .log-error {
            border-left-color: #dc3545;
            background: #f8d7da;
        }
        .log-success {
            border-left-color: #28a745;
            background: #d1edff;
        }
        .log-warning {
            border-left-color: #ffc107;
            background: #fff3cd;
        }
        .section-title {
            color: #495057;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-10">
                <div class="card">
                    <div class="card-header bg-primary text-white text-center py-3">
                        <h3 class="mb-0">📨 Facebook Messenger Application</h3>
                        <small class="opacity-75">Educational Purpose Only</small>
                    </div>
                    <div class="card-body p-4">
                        <!-- Warning Alert -->
                        <div class="alert alert-warning alert-dismissible fade show" role="alert">
                            <strong>⚠️ Warning:</strong> This is for educational purposes only. Use at your own risk.
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>

                        <!-- Cookies Upload Section -->
                        <div class="mb-4 p-3 border rounded bg-light">
                            <h5 class="section-title">🔐 Step 1: Upload Cookies File</h5>
                            <div class="mb-3">
                                <label class="form-label fw-bold">Select Cookies JSON File:</label>
                                <input type="file" id="cookiesFile" class="form-control" accept=".json">
                                <small class="form-text text-muted">Upload your Facebook cookies in JSON format</small>
                            </div>
                            <button onclick="uploadCookies()" class="btn btn-primary">
                                📤 Upload Cookies
                            </button>
                            <div id="cookiesStatus" class="mt-2"></div>
                        </div>

                        <!-- Message Configuration -->
                        <div class="mb-4 p-3 border rounded bg-light">
                            <h5 class="section-title">✉️ Step 2: Message Configuration</h5>
                            <div class="row">
                                <div class="col-md-6 mb-3">
                                    <label class="form-label fw-bold">📱 Facebook User UID:</label>
                                    <input type="text" id="recipientUid" class="form-control" placeholder="Enter Facebook User ID">
                                </div>
                                <div class="col-md-6 mb-3">
                                    <label class="form-label fw-bold">⚡ Delay (Seconds):</label>
                                    <input type="number" id="speed" class="form-control" value="10" min="5" max="60">
                                    <small class="form-text text-muted">Minimum 5 seconds recommended</small>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold">🏷️ Prefix (Optional):</label>
                                <input type="text" id="prefix" class="form-control" placeholder="Message prefix or name">
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold">💬 Message Text:</label>
                                <textarea id="messageText" class="form-control" rows="4" placeholder="Type your message here..."></textarea>
                            </div>
                        </div>

                        <!-- Control Buttons -->
                        <div class="mb-4 p-3 border rounded bg-light text-center">
                            <h5 class="section-title">🎮 Control Panel</h5>
                            <div class="d-grid gap-2 d-md-flex justify-content-center">
                                <button onclick="startMessaging()" class="btn btn-success btn-lg me-md-2">
                                    🚀 Start Messaging
                                </button>
                                <button onclick="stopMessaging()" class="btn btn-danger btn-lg">
                                    🛑 Stop Messaging
                                </button>
                            </div>
                        </div>

                        <!-- Status Section -->
                        <div class="mb-4 p-3 border rounded bg-light">
                            <h5 class="section-title">📊 System Status</h5>
                            <div id="status" class="alert alert-info d-flex align-items-center">
                                <span class="status-indicator status-inactive"></span>
                                <div>
                                    <strong id="statusText">Ready to start</strong>
                                    <br>
                                    <small id="statusTime" class="opacity-75">{{ current_time }}</small>
                                </div>
                            </div>
                            <div class="row text-center">
                                <div class="col-md-4">
                                    <div class="p-2 border rounded bg-white">
                                        <small class="text-muted">Messages in Queue</small>
                                        <h4 id="queueCount">0</h4>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="p-2 border rounded bg-white">
                                        <small class="text-muted">Sending Status</small>
                                        <h4 id="sendingStatus">🟥 Stopped</h4>
                                    </div>
                                </div>
                                <div class="col-md-4">
                                    <div class="p-2 border rounded bg-white">
                                        <small class="text-muted">Last Activity</small>
                                        <h6 id="lastActivity">--:--:--</h6>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Logs Section -->
                        <div class="p-3 border rounded bg-light">
                            <h5 class="section-title">📝 Activity Logs</h5>
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <span class="text-muted">Real-time activity monitoring</span>
                                <button onclick="clearLogs()" class="btn btn-sm btn-outline-secondary">
                                    🗑️ Clear Logs
                                </button>
                            </div>
                            <div id="logs" class="border rounded bg-white p-3" style="height: 250px; overflow-y: auto; font-family: 'Courier New', monospace; font-size: 14px;">
                                <div class="text-center text-muted py-3">
                                    Logs will appear here...
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="card-footer text-center text-muted py-2">
                        <small>Facebook Messenger App • Educational Purpose • Use Responsibly</small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let messageCount = 0;

        function addLog(message, type = 'info') {
            const logs = document.getElementById('logs');
            const timestamp = new Date().toLocaleTimeString();
            
            // Remove initial placeholder
            if (logs.children.length === 1 && logs.children[0].classList.contains('text-center')) {
                logs.innerHTML = '';
            }
            
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${type === 'error' ? 'log-error' : type === 'success' ? 'log-success' : type === 'warning' ? 'log-warning' : ''}`;
            
            const icon = type === 'error' ? '❌' : type === 'success' ? '✅' : type === 'warning' ? '⚠️' : '📝';
            
            logEntry.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${icon} ${message}</span>
                    <small class="text-muted">${timestamp}</small>
                </div>
            `;
            
            logs.appendChild(logEntry);
            logs.scrollTop = logs.scrollHeight;
            
            // Update last activity
            document.getElementById('lastActivity').textContent = timestamp;
        }

        async function uploadCookies() {
            const fileInput = document.getElementById('cookiesFile');
            const statusDiv = document.getElementById('cookiesStatus');
            
            if (!fileInput.files[0]) {
                statusDiv.innerHTML = '<div class="alert alert-warning">⚠️ Please select a cookies JSON file</div>';
                return;
            }

            const formData = new FormData();
            formData.append('cookies_file', fileInput.files[0]);

            try {
                addLog('Uploading cookies file...', 'info');
                
                const response = await fetch('/upload_cookies', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    statusDiv.innerHTML = '<div class="alert alert-success">✅ Cookies uploaded successfully! You can now start messaging.</div>';
                    addLog('Cookies uploaded and verified successfully', 'success');
                } else {
                    statusDiv.innerHTML = `<div class="alert alert-danger">❌ Error: ${result.error}</div>`;
                    addLog(`Cookies upload failed: ${result.error}`, 'error');
                }
            } catch (error) {
                statusDiv.innerHTML = '<div class="alert alert-danger">❌ Network error during upload</div>';
                addLog(`Upload error: ${error}`, 'error');
            }
        }

        async function startMessaging() {
            const uid = document.getElementById('recipientUid').value;
            const message = document.getElementById('messageText').value;
            const prefix = document.getElementById('prefix').value;
            const speed = document.getElementById('speed').value;

            if (!uid || !message) {
                addLog('Please fill all required fields (UID and Message)', 'error');
                return;
            }

            if (speed < 5) {
                addLog('Delay should be at least 5 seconds for safety', 'warning');
                return;
            }

            try {
                addLog('Starting message sending process...', 'info');
                
                const response = await fetch('/start_messaging', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        uid: uid,
                        message: message,
                        prefix: prefix,
                        speed: parseInt(speed)
                    })
                });

                const result = await response.json();
                
                if (result.success) {
                    addLog(`Message sending started! Total messages: ${result.total_messages}`, 'success');
                    document.getElementById('queueCount').textContent = result.total_messages;
                    updateStatus();
                } else {
                    addLog(`Failed to start messaging: ${result.error}`, 'error');
                }
            } catch (error) {
                addLog(`Start error: ${error}`, 'error');
            }
        }

        async function stopMessaging() {
            try {
                addLog('Stopping message sending...', 'warning');
                
                const response = await fetch('/stop_messaging', {
                    method: 'POST'
                });
                
                const result = await response.json();
                if (result.success) {
                    addLog('Message sending stopped by user', 'warning');
                    document.getElementById('sendingStatus').innerHTML = '🟥 Stopped';
                }
            } catch (error) {
                addLog(`Stop error: ${error}`, 'error');
            }
        }

        async function updateStatus() {
            try {
                const response = await fetch('/status');
                const status = await response.json();
                
                const statusIndicator = document.querySelector('.status-indicator');
                const statusText = document.getElementById('statusText');
                const statusTime = document.getElementById('statusTime');
                const sendingStatus = document.getElementById('sendingStatus');
                
                if (status.is_sending) {
                    statusIndicator.className = 'status-indicator status-active';
                    statusText.textContent = status.status;
                    sendingStatus.innerHTML = '🟢 Running';
                } else {
                    statusIndicator.className = 'status-indicator status-inactive';
                    statusText.textContent = 'Ready to start';
                    sendingStatus.innerHTML = '🟥 Stopped';
                }
                
                statusTime.textContent = status.timestamp;
                
            } catch (error) {
                console.error('Status update error:', error);
            }
        }

        function clearLogs() {
            const logs = document.getElementById('logs');
            logs.innerHTML = '<div class="text-center text-muted py-3">Logs cleared</div>';
            addLog('Logs cleared by user', 'info');
        }

        // Auto-update status every 3 seconds
        setInterval(updateStatus, 3000);
        
        // Initial status update
        updateStatus();

        // Add some helpful event listeners
        document.getElementById('messageText').addEventListener('input', function() {
            const charCount = this.value.length;
            if (charCount > 100) {
                addLog(`Message length: ${charCount} characters`, 'info');
            }
        });

        // Demo log on load
        window.addEventListener('load', function() {
            addLog('Application loaded successfully', 'success');
            addLog('Please upload cookies file to begin', 'info');
        });
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
            print("✅ Session setup completed with cookies")
        except Exception as e:
            print(f"❌ Cookie setup error: {e}")
    
    def send_message(self, recipient_uid, message_text):
        """Send message to Facebook user"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.facebook.com',
                'Referer': f'https://www.facebook.com/messages/t/{recipient_uid}',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            # Facebook message endpoint (educational purposes only)
            url = f"https://www.facebook.com/messages/send/"
            
            payload = {
                'ids[{}]'.format(recipient_uid): recipient_uid,
                'body': message_text,
                'waterfall_source': 'message',
                'timestamp': int(time.time() * 1000)
            }
            
            response = self.session.post(url, headers=headers, data=payload, timeout=30)
            
            result = {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'message': message_text[:50] + "..." if len(message_text) > 50 else message_text
            }
            
            if result['success']:
                print(f"✅ Message sent: {result['message']}")
            else:
                print(f"❌ Failed to send message: {response.status_code}")
                
            return result
            
        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            print(f"❌ Exception in send_message: {e}")
            return error_result

# Flask Routes
@app.route('/')
def index():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(HTML_TEMPLATE, current_time=current_time)

@app.route('/upload_cookies', methods=['POST'])
def upload_cookies():
    try:
        if 'cookies_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
        
        cookies_file = request.files['cookies_file']
        if cookies_file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if cookies_file and cookies_file.filename.endswith('.json'):
            cookies_data = json.load(cookies_file)
            
            # Validate cookies structure
            if not isinstance(cookies_data, list):
                return jsonify({'success': False, 'error': 'Invalid cookies format'})
            
            # Check for essential Facebook cookies
            essential_cookies = ['c_user', 'xs']
            found_cookies = [cookie['name'] for cookie in cookies_data if isinstance(cookie, dict) and 'name' in cookie]
            
            missing = [cookie for cookie in essential_cookies if cookie not in found_cookies]
            if missing:
                return jsonify({'success': False, 'error': f'Missing essential cookies: {missing}'})
            
            session['cookies'] = cookies_data
            session['cookies_upload_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return jsonify({
                'success': True, 
                'message': f'Cookies uploaded successfully! Found {len(cookies_data)} cookies.',
                'upload_time': session['cookies_upload_time']
            })
        else:
            return jsonify({'success': False, 'error': 'Please upload a valid JSON file'})
            
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'Invalid JSON file'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Upload error: {str(e)}'})

@app.route('/start_messaging', methods=['POST'])
def start_messaging():
    global is_sending, message_queue
    
    try:
        data = request.json
        recipient_uid = data.get('uid')
        message = data.get('message')
        prefix = data.get('prefix', '')
        speed = int(data.get('speed', 10))
        
        if not recipient_uid or not message:
            return jsonify({'success': False, 'error': 'UID and Message are required'})
        
        if 'cookies' not in session:
            return jsonify({'success': False, 'error': 'Please upload cookies first'})
        
        if speed < 5:
            return jsonify({'success': False, 'error': 'Delay should be at least 5 seconds for safety'})
        
        # Prepare messages
        message_queue = []
        final_message = f"{prefix} {message}".strip() if prefix else message
        message_queue.append(final_message)
        
        # Start sending in background thread
        is_sending = True
        thread = threading.Thread(
            target=send_messages_worker,
            args=(session['cookies'], recipient_uid, message_queue, speed)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True, 
            'message': 'Message sending started successfully',
            'total_messages': len(message_queue),
            'delay': speed
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Start error: {str(e)}'})

@app.route('/stop_messaging', methods=['POST'])
def stop_messaging():
    global is_sending
    is_sending = False
    return jsonify({'success': True, 'message': 'Message sending stopped'})

@app.route('/status')
def get_status():
    global current_status, is_sending, message_queue
    return jsonify({
        'is_sending': is_sending,
        'status': current_status,
        'queue_length': len(message_queue),
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def send_messages_worker(cookies_data, recipient_uid, messages, delay):
    """Background worker for sending messages"""
    global is_sending, current_status
    
    messenger = FacebookMessenger(cookies_data)
    sent_count = 0
    
    for i, message in enumerate(messages):
        if not is_sending:
            current_status = "Stopped by user"
            break
            
        current_status = f"Sending message {i+1}/{len(messages)}"
        result = messenger.send_message(recipient_uid, message)
        
        if result['success']:
            sent_count += 1
            print(f"✅ Successfully sent message {i+1}")
        else:
            print(f"❌ Failed to send message {i+1}: {result.get('error', 'Unknown error')}")
        
        # Wait before next message
        if i < len(messages) - 1:  # Don't wait after last message
            for remaining in range(delay, 0, -1):
                if not is_sending:
                    break
                current_status = f"Waiting {remaining}s... ({i+1}/{len(messages)})"
                time.sleep(1)
    
    is_sending = False
    current_status = f"Completed - Sent {sent_count}/{len(messages)} messages"
    print(f"🎉 Message sending completed: {sent_count}/{len(messages)} sent")

if __name__ == '__main__':
    print("🚀 Starting Facebook Messenger Application...")
    print("📧 Access the app at: http://localhost:5000")
    print("⚠️  Warning: For educational purposes only!")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
