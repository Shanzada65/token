import os
import time
import json
import threading
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'whatsapp_automation_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
driver = None
is_connected = False
is_sending = False
stop_sending = False
message_queue = []

# HTML Template with embedded CSS and JavaScript
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Automation Tool</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .container {
            background: rgba(0, 0, 0, 0.8);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(0, 255, 255, 0.3);
            max-width: 600px;
            width: 100%;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .header h1 {
            color: #00ffff;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
        }

        .status-indicator {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
            margin-top: 10px;
        }

        .status-disconnected {
            background: rgba(255, 0, 0, 0.2);
            color: #ff6b6b;
            border: 1px solid #ff6b6b;
        }

        .status-connected {
            background: rgba(0, 255, 0, 0.2);
            color: #51cf66;
            border: 1px solid #51cf66;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            color: #ffffff;
            margin-bottom: 8px;
            font-weight: 500;
        }

        .form-control {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.1);
            color: #ffffff;
            font-size: 16px;
            transition: all 0.3s ease;
        }

        .form-control:focus {
            outline: none;
            border-color: #00ffff;
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
        }

        .form-control::placeholder {
            color: rgba(255, 255, 255, 0.6);
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .btn-primary {
            background: linear-gradient(45deg, #00ffff, #0080ff);
            color: #000;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0, 255, 255, 0.3);
        }

        .btn-danger {
            background: linear-gradient(45deg, #ff4757, #ff3838);
            color: #fff;
        }

        .btn-danger:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(255, 71, 87, 0.3);
        }

        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .btn-block {
            width: 100%;
            margin-bottom: 15px;
        }

        .row {
            display: flex;
            gap: 15px;
        }

        .col {
            flex: 1;
        }

        .log-container {
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            padding: 15px;
            height: 200px;
            overflow-y: auto;
            margin-top: 20px;
        }

        .log-entry {
            color: #ffffff;
            margin-bottom: 5px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }

        .log-entry.success {
            color: #51cf66;
        }

        .log-entry.error {
            color: #ff6b6b;
        }

        .log-entry.info {
            color: #74c0fc;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 10px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ffff, #0080ff);
            width: 0%;
            transition: width 0.3s ease;
        }

        .file-input-wrapper {
            position: relative;
            display: inline-block;
            width: 100%;
        }

        .file-input {
            position: absolute;
            opacity: 0;
            width: 100%;
            height: 100%;
            cursor: pointer;
        }

        .file-input-label {
            display: block;
            padding: 12px 16px;
            border: 2px dashed rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.05);
            color: rgba(255, 255, 255, 0.8);
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .file-input-label:hover {
            border-color: #00ffff;
            background: rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 768px) {
            .container {
                margin: 10px;
                padding: 20px;
            }
            
            .row {
                flex-direction: column;
                gap: 10px;
            }
            
            .header h1 {
                font-size: 2em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>WhatsApp Automation</h1>
            <div id="status" class="status-indicator status-disconnected">Disconnected</div>
        </div>

        <form id="automationForm">
            <div class="form-group">
                <label for="phoneNumber">Your Phone Number (with country code)</label>
                <input type="tel" id="phoneNumber" class="form-control" placeholder="+1234567890" required>
            </div>

            <div class="form-group">
                <label for="targetNumber">Target Number or Group ID</label>
                <input type="text" id="targetNumber" class="form-control" placeholder="+1234567890 or Group Name" required>
            </div>

            <div class="form-group">
                <label for="message">Message Content</label>
                <textarea id="message" class="form-control" rows="4" placeholder="Enter your message here..." required></textarea>
            </div>

            <div class="row">
                <div class="col">
                    <div class="form-group">
                        <label for="delay">Delay (seconds)</label>
                        <input type="number" id="delay" class="form-control" value="5" min="1" max="300">
                    </div>
                </div>
                <div class="col">
                    <div class="form-group">
                        <label for="count">Message Count</label>
                        <input type="number" id="count" class="form-control" value="1" min="1" max="100">
                    </div>
                </div>
            </div>

            <div class="form-group">
                <label>Upload Message File (Optional)</label>
                <div class="file-input-wrapper">
                    <input type="file" id="messageFile" class="file-input" accept=".txt,.csv">
                    <label for="messageFile" class="file-input-label">
                        Choose file or drag here
                    </label>
                </div>
            </div>

            <button type="button" id="connectBtn" class="btn btn-primary btn-block">Connect to WhatsApp</button>
            <button type="button" id="startBtn" class="btn btn-primary btn-block" disabled>Start Sending</button>
            <button type="button" id="stopBtn" class="btn btn-danger btn-block" disabled>Stop Sending</button>
        </form>

        <div class="progress-bar">
            <div id="progressFill" class="progress-fill"></div>
        </div>

        <div class="log-container">
            <div id="logs"></div>
        </div>
    </div>

    <script>
        const socket = io();
        let isConnected = false;
        let isSending = false;

        // DOM elements
        const statusEl = document.getElementById('status');
        const connectBtn = document.getElementById('connectBtn');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const logsEl = document.getElementById('logs');
        const progressFill = document.getElementById('progressFill');

        // Socket event listeners
        socket.on('status_update', function(data) {
            updateStatus(data.status, data.message);
        });

        socket.on('log_message', function(data) {
            addLog(data.message, data.type);
        });

        socket.on('progress_update', function(data) {
            updateProgress(data.progress);
        });

        socket.on('connection_status', function(data) {
            isConnected = data.connected;
            updateConnectionStatus();
        });

        // Button event listeners
        connectBtn.addEventListener('click', function() {
            const phoneNumber = document.getElementById('phoneNumber').value;
            if (!phoneNumber) {
                alert('Please enter your phone number');
                return;
            }
            
            connectBtn.disabled = true;
            connectBtn.textContent = 'Connecting...';
            
            socket.emit('connect_whatsapp', {phone_number: phoneNumber});
        });

        startBtn.addEventListener('click', function() {
            const formData = {
                target_number: document.getElementById('targetNumber').value,
                message: document.getElementById('message').value,
                delay: parseInt(document.getElementById('delay').value),
                count: parseInt(document.getElementById('count').value)
            };

            if (!formData.target_number || !formData.message) {
                alert('Please fill in all required fields');
                return;
            }

            isSending = true;
            updateSendingStatus();
            
            socket.emit('start_sending', formData);
        });

        stopBtn.addEventListener('click', function() {
            socket.emit('stop_sending');
            isSending = false;
            updateSendingStatus();
        });

        // File upload handler
        document.getElementById('messageFile').addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('message').value = e.target.result;
                };
                reader.readAsText(file);
            }
        });

        // Helper functions
        function updateStatus(status, message) {
            statusEl.textContent = status;
            statusEl.className = `status-indicator ${status.toLowerCase().includes('connected') ? 'status-connected' : 'status-disconnected'}`;
            if (message) {
                addLog(message, 'info');
            }
        }

        function updateConnectionStatus() {
            connectBtn.disabled = isConnected;
            connectBtn.textContent = isConnected ? 'Connected' : 'Connect to WhatsApp';
            startBtn.disabled = !isConnected || isSending;
        }

        function updateSendingStatus() {
            startBtn.disabled = !isConnected || isSending;
            stopBtn.disabled = !isSending;
            startBtn.textContent = isSending ? 'Sending...' : 'Start Sending';
        }

        function addLog(message, type = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${type}`;
            logEntry.textContent = `[${timestamp}] ${message}`;
            logsEl.appendChild(logEntry);
            logsEl.scrollTop = logsEl.scrollHeight;
        }

        function updateProgress(progress) {
            progressFill.style.width = `${progress}%`;
        }

        // Initialize
        addLog('Application started. Please connect to WhatsApp first.', 'info');
    </script>
</body>
</html>
"""

class WhatsAppAutomation:
    def __init__(self):
        self.driver = None
        self.is_connected = False
        
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Keep user data for session persistence
            chrome_options.add_argument("--user-data-dir=/tmp/whatsapp_chrome_profile")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            return True
        except Exception as e:
            logger.error(f"Failed to setup driver: {str(e)}")
            return False
    
    def connect_to_whatsapp(self, phone_number):
        """Connect to WhatsApp Web"""
        try:
            if not self.setup_driver():
                return False, "Failed to setup browser"
            
            socketio.emit('log_message', {'message': 'Opening WhatsApp Web...', 'type': 'info'})
            self.driver.get("https://web.whatsapp.com")
            
            # Wait for QR code or already logged in
            socketio.emit('log_message', {'message': 'Waiting for WhatsApp to load...', 'type': 'info'})
            
            # Check if already logged in
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-list']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "canvas")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='qr-code']"))
                    )
                )
                
                # Check if we're already logged in
                if self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='chat-list']"):
                    self.is_connected = True
                    socketio.emit('connection_status', {'connected': True})
                    socketio.emit('log_message', {'message': 'Already logged in to WhatsApp!', 'type': 'success'})
                    return True, "Connected successfully"
                else:
                    # QR code is present, need to scan
                    socketio.emit('log_message', {'message': 'Please scan the QR code on your phone to login', 'type': 'info'})
                    
                    # Wait for login completion
                    WebDriverWait(self.driver, 60).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-list']"))
                    )
                    
                    self.is_connected = True
                    socketio.emit('connection_status', {'connected': True})
                    socketio.emit('log_message', {'message': 'Successfully connected to WhatsApp!', 'type': 'success'})
                    return True, "Connected successfully"
                    
            except Exception as e:
                logger.error(f"Connection timeout: {str(e)}")
                return False, "Connection timeout. Please try again."
                
        except Exception as e:
            logger.error(f"Failed to connect to WhatsApp: {str(e)}")
            return False, f"Connection failed: {str(e)}"
    
    def send_message(self, target_number, message):
        """Send a message to target number"""
        try:
            if not self.is_connected or not self.driver:
                return False, "Not connected to WhatsApp"
            
            # Search for the contact
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='chat-list-search']"))
            )
            search_box.clear()
            search_box.send_keys(target_number)
            time.sleep(2)
            
            # Click on the first result
            try:
                first_result = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='cell-frame-container']"))
                )
                first_result.click()
            except:
                # If contact not found, try to start new chat
                new_chat_url = f"https://web.whatsapp.com/send?phone={target_number.replace('+', '')}"
                self.driver.get(new_chat_url)
                time.sleep(3)
            
            # Find message input and send message
            message_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='conversation-compose-box-input']"))
            )
            
            message_box.clear()
            message_box.send_keys(message)
            message_box.send_keys(Keys.ENTER)
            
            return True, "Message sent successfully"
            
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            return False, f"Failed to send message: {str(e)}"
    
    def close(self):
        """Close the driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
        self.is_connected = False

# Global WhatsApp automation instance
whatsapp_automation = WhatsAppAutomation()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('connect')
def handle_connect():
    emit('log_message', {'message': 'Connected to server', 'type': 'success'})

@socketio.on('connect_whatsapp')
def handle_connect_whatsapp(data):
    phone_number = data.get('phone_number', '')
    
    def connect_async():
        success, message = whatsapp_automation.connect_to_whatsapp(phone_number)
        if success:
            socketio.emit('status_update', {'status': 'Connected', 'message': message})
        else:
            socketio.emit('status_update', {'status': 'Connection Failed', 'message': message})
            socketio.emit('connection_status', {'connected': False})
    
    thread = threading.Thread(target=connect_async)
    thread.daemon = True
    thread.start()

@socketio.on('start_sending')
def handle_start_sending(data):
    global is_sending, stop_sending
    
    target_number = data.get('target_number', '')
    message = data.get('message', '')
    delay = data.get('delay', 5)
    count = data.get('count', 1)
    
    is_sending = True
    stop_sending = False
    
    def send_messages_async():
        global is_sending, stop_sending
        
        try:
            for i in range(count):
                if stop_sending:
                    break
                
                socketio.emit('log_message', {'message': f'Sending message {i+1}/{count}...', 'type': 'info'})
                
                success, result_message = whatsapp_automation.send_message(target_number, message)
                
                if success:
                    socketio.emit('log_message', {'message': f'Message {i+1} sent successfully', 'type': 'success'})
                else:
                    socketio.emit('log_message', {'message': f'Failed to send message {i+1}: {result_message}', 'type': 'error'})
                
                # Update progress
                progress = ((i + 1) / count) * 100
                socketio.emit('progress_update', {'progress': progress})
                
                # Wait before next message
                if i < count - 1 and not stop_sending:
                    socketio.emit('log_message', {'message': f'Waiting {delay} seconds...', 'type': 'info'})
                    time.sleep(delay)
            
            is_sending = False
            if not stop_sending:
                socketio.emit('log_message', {'message': 'All messages sent successfully!', 'type': 'success'})
            else:
                socketio.emit('log_message', {'message': 'Sending stopped by user', 'type': 'info'})
                
        except Exception as e:
            is_sending = False
            socketio.emit('log_message', {'message': f'Error during sending: {str(e)}', 'type': 'error'})
    
    thread = threading.Thread(target=send_messages_async)
    thread.daemon = True
    thread.start()

@socketio.on('stop_sending')
def handle_stop_sending():
    global stop_sending
    stop_sending = True
    socketio.emit('log_message', {'message': 'Stopping message sending...', 'type': 'info'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    print("Starting WhatsApp Automation Tool...")
    print("Open your browser and go to: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down...")
        whatsapp_automation.close()
    except Exception as e:
        print(f"Error: {e}")
        whatsapp_automation.close()

