from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import requests
import json
from datetime import datetime
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# In-memory storage for demonstration (replace with database in production)
tasks_storage = {}
users_storage = {}

# HTML Template with embedded CSS and JavaScript
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Automation Tool</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }

        .navbar {
            background: rgba(0, 0, 0, 0.8);
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .navbar-brand {
            color: #fff;
            font-size: 24px;
            font-weight: bold;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .navbar-brand:hover {
            color: #667eea;
        }

        .navbar-links {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .navbar-links a, .navbar-links button {
            color: #fff;
            text-decoration: none;
            padding: 8px 15px;
            border-radius: 5px;
            transition: all 0.3s ease;
            border: none;
            background: transparent;
            cursor: pointer;
            font-size: 14px;
        }

        .navbar-links a:hover, .navbar-links button:hover {
            background: #667eea;
            transform: translateY(-2px);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 30px 20px;
        }

        .home-header {
            text-align: center;
            color: white;
            margin-bottom: 50px;
            animation: slideDown 0.6s ease;
        }

        .home-header h1 {
            font-size: 48px;
            margin-bottom: 15px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }

        .home-header p {
            font-size: 18px;
            opacity: 0.9;
        }

        .tools-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }

        .tool-card {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            cursor: pointer;
            animation: fadeInUp 0.6s ease;
        }

        .tool-card:hover {
            transform: translateY(-10px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
        }

        .tool-image {
            width: 100%;
            height: 200px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 60px;
        }

        .tool-content {
            padding: 20px;
            text-align: center;
        }

        .tool-content h3 {
            margin-bottom: 15px;
            color: #333;
            font-size: 20px;
        }

        .tool-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
            width: 100%;
        }

        .tool-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .tool-btn.green {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }

        .tool-btn.yellow {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }

        .tool-btn.orange {
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }

        .tool-section {
            display: none;
            animation: fadeIn 0.4s ease;
        }

        .tool-section.active {
            display: block;
        }

        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
        }

        .form-group input,
        .form-group textarea,
        .form-group select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s ease;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        .form-group input:focus,
        .form-group textarea:focus,
        .form-group select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 10px rgba(102, 126, 234, 0.2);
        }

        .form-group textarea {
            resize: vertical;
            min-height: 100px;
        }

        .submit-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
            width: 100%;
        }

        .submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }

        .submit-btn:active {
            transform: translateY(0);
        }

        .home-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 30px;
            transition: all 0.3s ease;
        }

        .home-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .result-box {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            display: none;
        }

        .result-box.show {
            display: block;
            animation: slideIn 0.4s ease;
        }

        .result-box.success {
            border-left-color: #38ef7d;
            background: #f0fdf4;
        }

        .result-box.error {
            border-left-color: #f5576c;
            background: #fdf0f0;
        }

        .result-box h4 {
            margin-bottom: 10px;
            color: #333;
        }

        .result-box p {
            color: #666;
            line-height: 1.6;
            word-break: break-all;
        }

        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }

        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        .tool-wrapper {
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            max-width: 600px;
            margin: 0 auto;
        }

        .tool-wrapper h2 {
            color: #333;
            margin-bottom: 30px;
            text-align: center;
            font-size: 28px;
        }

        .developer-link {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            transition: all 0.3s ease;
            margin-left: 10px;
        }

        .developer-link:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .token-result {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            display: none;
        }

        .token-result.show {
            display: block;
        }

        .token-valid {
            border-left: 4px solid #38ef7d;
            background: #f0fdf4;
        }

        .token-invalid {
            border-left: 4px solid #f5576c;
            background: #fdf0f0;
        }

        .profile-info {
            display: grid;
            grid-template-columns: 100px 1fr;
            gap: 20px;
            align-items: center;
            margin-top: 15px;
        }

        .profile-pic {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid #667eea;
        }

        .profile-details h4 {
            color: #333;
            margin-bottom: 5px;
        }

        .profile-details p {
            color: #666;
            margin: 5px 0;
            font-size: 14px;
        }

        .tasks-container {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }

        .task-item {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }

        .task-item h4 {
            color: #333;
            margin-bottom: 10px;
        }

        .task-info {
            color: #666;
            font-size: 14px;
            line-height: 1.6;
        }

        @media (max-width: 768px) {
            .tools-grid {
                grid-template-columns: 1fr;
            }

            .home-header h1 {
                font-size: 32px;
            }

            .tool-wrapper {
                padding: 20px;
            }

            .navbar {
                flex-direction: column;
                gap: 15px;
            }

            .navbar-links {
                flex-direction: column;
                width: 100%;
            }

            .navbar-links a, .navbar-links button {
                width: 100%;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="navbar-brand">
            📱 FB Automation Tool
        </div>
        <div class="navbar-links">
            <a href="/" onclick="goHome(event)">🏠 Home</a>
            <a href="https://www.facebook.com/SH33T9N.BOII.ONIFR3" target="_blank" class="developer-link">👨‍💻 Developer</a>
        </div>
    </nav>

    <div class="container">
        <!-- Home Section -->
        <div id="home-section" class="tool-section active">
            <div class="home-header">
                <h1>🎯 Facebook Automation Suite</h1>
                <p>All-in-one tool for Facebook automation tasks</p>
            </div>

            <div class="tools-grid">
                <!-- Conversation Tool -->
                <div class="tool-card">
                    <div class="tool-image">💬</div>
                    <div class="tool-content">
                        <h3>Conversation Sender</h3>
                        <button class="tool-btn" onclick="showTool('convo-section')">Open Tool</button>
                    </div>
                </div>

                <!-- Post Comment Tool -->
                <div class="tool-card">
                    <div class="tool-image">💭</div>
                    <div class="tool-content">
                        <h3>Post Comment Tool</h3>
                        <button class="tool-btn orange" onclick="showTool('comment-section')">Open Tool</button>
                    </div>
                </div>

                <!-- Token Checker -->
                <div class="tool-card">
                    <div class="tool-image">🔐</div>
                    <div class="tool-content">
                        <h3>Token Checker</h3>
                        <button class="tool-btn green" onclick="showTool('token-section')">Open Tool</button>
                    </div>
                </div>

                <!-- UID Fetcher -->
                <div class="tool-card">
                    <div class="tool-image">🔍</div>
                    <div class="tool-content">
                        <h3>Messenger Groups UID</h3>
                        <button class="tool-btn yellow" onclick="showTool('uid-section')">Open Tool</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Conversation Tool Section -->
        <div id="convo-section" class="tool-section">
            <button class="home-btn" onclick="goHome()">← Back to Home</button>
            <div class="tool-wrapper">
                <h2>💬 Conversation Message Sender</h2>
                <form onsubmit="sendConversationMessage(event)">
                    <div class="form-group">
                        <label for="convo-token">Facebook Token:</label>
                        <input type="password" id="convo-token" name="token" required placeholder="Enter your Facebook token">
                    </div>
                    <div class="form-group">
                        <label for="convo-uid">Recipient UID:</label>
                        <input type="text" id="convo-uid" name="uid" required placeholder="Enter recipient user ID">
                    </div>
                    <div class="form-group">
                        <label for="convo-message">Message:</label>
                        <textarea id="convo-message" name="message" required placeholder="Enter your message here..."></textarea>
                    </div>
                    <div class="loading" id="convo-loading">
                        <div class="spinner"></div>
                        <p>Sending message...</p>
                    </div>
                    <button type="submit" class="submit-btn">Send Message</button>
                </form>
                <div class="result-box" id="convo-result"></div>
            </div>
        </div>

        <!-- Post Comment Tool Section -->
        <div id="comment-section" class="tool-section">
            <button class="home-btn" onclick="goHome()">← Back to Home</button>
            <div class="tool-wrapper">
                <h2>💭 Post Comment Tool</h2>
                <form onsubmit="postComment(event)">
                    <div class="form-group">
                        <label for="comment-token">Facebook Token:</label>
                        <input type="password" id="comment-token" name="token" required placeholder="Enter your Facebook token">
                    </div>
                    <div class="form-group">
                        <label for="post-id">Post ID:</label>
                        <input type="text" id="post-id" name="post_id" required placeholder="Enter post ID">
                    </div>
                    <div class="form-group">
                        <label for="comment-text">Comment Text:</label>
                        <textarea id="comment-text" name="comment" required placeholder="Enter your comment..."></textarea>
                    </div>
                    <div class="loading" id="comment-loading">
                        <div class="spinner"></div>
                        <p>Posting comment...</p>
                    </div>
                    <button type="submit" class="submit-btn">Post Comment</button>
                </form>
                <div class="result-box" id="comment-result"></div>
            </div>
        </div>

        <!-- Token Checker Section -->
        <div id="token-section" class="tool-section">
            <button class="home-btn" onclick="goHome()">← Back to Home</button>
            <div class="tool-wrapper">
                <h2>🔐 Token Checker</h2>
                <form onsubmit="checkToken(event)">
                    <div class="form-group">
                        <label for="check-token">Facebook Token:</label>
                        <input type="password" id="check-token" name="token" required placeholder="Enter your Facebook token">
                    </div>
                    <div class="loading" id="token-loading">
                        <div class="spinner"></div>
                        <p>Checking token...</p>
                    </div>
                    <button type="submit" class="submit-btn">Check Token</button>
                </form>
                <div class="token-result" id="token-result"></div>
            </div>
        </div>

        <!-- UID Fetcher Section -->
        <div id="uid-section" class="tool-section">
            <button class="home-btn" onclick="goHome()">← Back to Home</button>
            <div class="tool-wrapper">
                <h2>🔍 Messenger Groups UID Fetcher</h2>
                <form onsubmit="fetchMessengerGroups(event)">
                    <div class="form-group">
                        <label for="uid-token">Facebook Token:</label>
                        <input type="password" id="uid-token" name="token" required placeholder="Enter your Facebook token">
                    </div>
                    <div class="loading" id="uid-loading">
                        <div class="spinner"></div>
                        <p>Fetching groups...</p>
                    </div>
                    <button type="submit" class="submit-btn">Fetch Groups</button>
                </form>
                <div class="result-box" id="uid-result"></div>
            </div>
        </div>
    </div>

    <script>
        function showTool(toolId) {
            // Hide all sections
            const sections = document.querySelectorAll('.tool-section');
            sections.forEach(section => section.classList.remove('active'));
            
            // Show selected tool
            document.getElementById(toolId).classList.add('active');
            
            // Scroll to top
            window.scrollTo(0, 0);
        }

        function goHome(event) {
            if (event) event.preventDefault();
            
            // Hide all sections
            const sections = document.querySelectorAll('.tool-section');
            sections.forEach(section => section.classList.remove('active'));
            
            // Show home section
            document.getElementById('home-section').classList.add('active');
            
            // Clear all results
            document.querySelectorAll('.result-box, .token-result').forEach(box => {
                box.classList.remove('show');
            });
            
            // Scroll to top
            window.scrollTo(0, 0);
        }

        function showResult(elementId, message, isSuccess = true, isTokenResult = false) {
            const resultBox = document.getElementById(elementId);
            resultBox.innerHTML = `
                <h4>${isSuccess ? '✅ Success' : '❌ Error'}</h4>
                <p>${message}</p>
            `;
            resultBox.classList.add('show');
            resultBox.classList.add(isSuccess ? 'success' : 'error');
            if (isTokenResult) {
                resultBox.classList.add(isSuccess ? 'token-valid' : 'token-invalid');
            }
        }

        function sendConversationMessage(event) {
            event.preventDefault();
            
            const token = document.getElementById('convo-token').value;
            const uid = document.getElementById('convo-uid').value;
            const message = document.getElementById('convo-message').value;
            const loading = document.getElementById('convo-loading');
            const resultBox = document.getElementById('convo-result');
            
            loading.style.display = 'block';
            resultBox.classList.remove('show');
            
            fetch('/api/send-message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    token: token,
                    uid: uid,
                    message: message
                })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.success) {
                    showResult('convo-result', `Message sent successfully! Message ID: ${data.message_id}`);
                    document.getElementById('convo-message').value = '';
                } else {
                    showResult('convo-result', data.error, false);
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                showResult('convo-result', `Error: ${error.message}`, false);
            });
        }

        function postComment(event) {
            event.preventDefault();
            
            const token = document.getElementById('comment-token').value;
            const postId = document.getElementById('post-id').value;
            const comment = document.getElementById('comment-text').value;
            const loading = document.getElementById('comment-loading');
            const resultBox = document.getElementById('comment-result');
            
            loading.style.display = 'block';
            resultBox.classList.remove('show');
            
            fetch('/api/post-comment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    token: token,
                    post_id: postId,
                    comment: comment
                })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.success) {
                    showResult('comment-result', `Comment posted successfully! Comment ID: ${data.comment_id}`);
                    document.getElementById('comment-text').value = '';
                } else {
                    showResult('comment-result', data.error, false);
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                showResult('comment-result', `Error: ${error.message}`, false);
            });
        }

        function checkToken(event) {
            event.preventDefault();
            
            const token = document.getElementById('check-token').value;
            const loading = document.getElementById('token-loading');
            const resultBox = document.getElementById('token-result');
            
            loading.style.display = 'block';
            resultBox.classList.remove('show');
            
            fetch('/api/check-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    token: token
                })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.valid) {
                    const profileHtml = `
                        <h4>✅ Token is Valid</h4>
                        <div class="profile-info">
                            <img src="${data.profile_pic}" alt="Profile" class="profile-pic" onerror="this.src='https://via.placeholder.com/100'">
                            <div class="profile-details">
                                <h4>${data.name}</h4>
                                <p><strong>UID:</strong> ${data.uid}</p>
                                <p><strong>Email:</strong> ${data.email || 'N/A'}</p>
                            </div>
                        </div>
                    `;
                    resultBox.innerHTML = profileHtml;
                    resultBox.classList.add('show', 'token-valid');
                } else {
                    resultBox.innerHTML = `
                        <h4>❌ Token is Invalid</h4>
                        <p>${data.error}</p>
                    `;
                    resultBox.classList.add('show', 'token-invalid');
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                resultBox.innerHTML = `
                    <h4>❌ Error</h4>
                    <p>${error.message}</p>
                `;
                resultBox.classList.add('show', 'token-invalid');
            });
        }

        function fetchMessengerGroups(event) {
            event.preventDefault();
            
            const token = document.getElementById('uid-token').value;
            const loading = document.getElementById('uid-loading');
            const resultBox = document.getElementById('uid-result');
            
            loading.style.display = 'block';
            resultBox.classList.remove('show');
            
            fetch('/api/fetch-groups', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    token: token
                })
            })
            .then(response => response.json())
            .then(data => {
                loading.style.display = 'none';
                if (data.success) {
                    let groupsHtml = '<h4>✅ Groups Found</h4>';
                    if (data.groups && data.groups.length > 0) {
                        groupsHtml += '<div style="max-height: 400px; overflow-y: auto;">';
                        data.groups.forEach(group => {
                            groupsHtml += `
                                <div style="background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 5px;">
                                    <strong>${group.name}</strong><br>
                                    <small>UID: ${group.id}</small>
                                </div>
                            `;
                        });
                        groupsHtml += '</div>';
                    } else {
                        groupsHtml += '<p>No groups found.</p>';
                    }
                    resultBox.innerHTML = groupsHtml;
                    resultBox.classList.add('show', 'success');
                } else {
                    resultBox.innerHTML = `
                        <h4>❌ Error</h4>
                        <p>${data.error}</p>
                    `;
                    resultBox.classList.add('show', 'error');
                }
            })
            .catch(error => {
                loading.style.display = 'none';
                resultBox.innerHTML = `
                    <h4>❌ Error</h4>
                    <p>${error.message}</p>
                `;
                resultBox.classList.add('show', 'error');
            });
        }
    </script>
</body>
</html>
'''

# Routes
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/send-message', methods=['POST'])
def send_message():
    """Send a conversation message via Facebook API"""
    try:
        data = request.json
        token = data.get('token')
        uid = data.get('uid')
        message = data.get('message')
        
        if not all([token, uid, message]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Facebook Graph API endpoint
        url = f'https://graph.facebook.com/v18.0/{uid}/messages'
        params = {
            'access_token': token,
            'message': message
        }
        
        response = requests.post(url, params=params, timeout=10)
        result = response.json()
        
        if 'id' in result:
            # Store task
            task_id = f"msg_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tasks_storage[task_id] = {
                'type': 'message',
                'recipient': uid,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            
            return jsonify({
                'success': True,
                'message_id': result['id']
            })
        else:
            error_msg = result.get('error', {}).get('message', 'Unknown error')
            return jsonify({
                'success': False,
                'error': error_msg
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/post-comment', methods=['POST'])
def post_comment():
    """Post a comment on a Facebook post"""
    try:
        data = request.json
        token = data.get('token')
        post_id = data.get('post_id')
        comment = data.get('comment')
        
        if not all([token, post_id, comment]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Facebook Graph API endpoint
        url = f'https://graph.facebook.com/v18.0/{post_id}/comments'
        params = {
            'access_token': token,
            'message': comment
        }
        
        response = requests.post(url, params=params, timeout=10)
        result = response.json()
        
        if 'id' in result:
            # Store task
            task_id = f"comment_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tasks_storage[task_id] = {
                'type': 'comment',
                'post_id': post_id,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            
            return jsonify({
                'success': True,
                'comment_id': result['id']
            })
        else:
            error_msg = result.get('error', {}).get('message', 'Unknown error')
            return jsonify({
                'success': False,
                'error': error_msg
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/check-token', methods=['POST'])
def check_token():
    """Check if a Facebook token is valid and get user info"""
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'valid': False, 'error': 'Token is required'}), 400
        
        # Facebook Graph API endpoint to get user info
        url = 'https://graph.facebook.com/v18.0/me'
        params = {
            'access_token': token,
            'fields': 'id,name,email,picture.type(large)'
        }
        
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        if 'id' in result:
            profile_pic = result.get('picture', {}).get('data', {}).get('url', 'https://via.placeholder.com/100')
            
            return jsonify({
                'valid': True,
                'uid': result['id'],
                'name': result.get('name', 'Unknown'),
                'email': result.get('email', 'N/A'),
                'profile_pic': profile_pic
            })
        else:
            error_msg = result.get('error', {}).get('message', 'Invalid token')
            return jsonify({
                'valid': False,
                'error': error_msg
            })
    except Exception as e:
        return jsonify({
            'valid': False,
            'error': str(e)
        }), 500

@app.route('/api/fetch-groups', methods=['POST'])
def fetch_groups():
    """Fetch messenger groups for the user"""
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'success': False, 'error': 'Token is required'}), 400
        
        # Facebook Graph API endpoint to get conversations
        url = 'https://graph.facebook.com/v18.0/me/conversations'
        params = {
            'access_token': token,
            'fields': 'id,name,type',
            'limit': 50
        }
        
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        if 'data' in result:
            # Filter only group conversations
            groups = [
                {
                    'id': conv['id'],
                    'name': conv.get('name', 'Unnamed Group'),
                    'type': conv.get('type', 'unknown')
                }
                for conv in result['data']
                if conv.get('type') == 'GROUP'
            ]
            
            return jsonify({
                'success': True,
                'groups': groups,
                'total': len(groups)
            })
        else:
            error_msg = result.get('error', {}).get('message', 'Failed to fetch groups')
            return jsonify({
                'success': False,
                'error': error_msg
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

