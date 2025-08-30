from flask import Flask, request, render_template_string, jsonify
from flask_cors import CORS
import fbchat_muqit
import asyncio
import json
import threading
import time

app = Flask(__name__)
CORS(app)

# HTML Template embedded in the Python file
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Messenger Group Tool</title>
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
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            padding: 40px;
            max-width: 500px;
            width: 100%;
            animation: slideUp 0.5s ease-out;
        }
        
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 28px;
            font-weight: 600;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
        }
        
        input[type="text"], textarea {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }
        
        input[type="text"]:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        textarea {
            resize: vertical;
            min-height: 100px;
        }
        
        .submit-btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 10px;
        }
        
        .submit-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .submit-btn:active {
            transform: translateY(0);
        }
        
        .submit-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-weight: 500;
            display: none;
        }
        
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .status.loading {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        
        .help-text {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        
        .loader {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        @media (max-width: 600px) {
            .container {
                padding: 30px 20px;
                margin: 10px;
            }
            
            h1 {
                font-size: 24px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Messenger Group Tool</h1>
        <form id="messengerForm">
            <div class="form-group">
                <label for="group_id">Group/Conversation ID:</label>
                <input type="text" id="group_id" name="group_id" required>
                <div class="help-text">Find this in the URL of your Messenger group chat</div>
            </div>
            
            <div class="form-group">
                <label for="message">Message:</label>
                <textarea id="message" name="message" placeholder="Type your message here..." required></textarea>
            </div>
            
            <div class="form-group">
                <label for="c_user">c_user Cookie:</label>
                <input type="text" id="c_user" name="c_user" required>
                <div class="help-text">Get this from your browser's Facebook cookies</div>
            </div>
            
            <div class="form-group">
                <label for="xs">xs Cookie:</label>
                <input type="text" id="xs" name="xs" required>
                <div class="help-text">Get this from your browser's Facebook cookies</div>
            </div>
            
            <button type="submit" class="submit-btn" id="submitBtn">
                Send Message
            </button>
        </form>
        
        <div id="status" class="status"></div>
    </div>

    <script>
        document.getElementById('messengerForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitBtn = document.getElementById('submitBtn');
            const status = document.getElementById('status');
            
            // Get form data
            const formData = {
                group_id: document.getElementById('group_id').value,
                message: document.getElementById('message').value,
                c_user: document.getElementById('c_user').value,
                xs: document.getElementById('xs').value
            };
            
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loader"></span>Sending...';
            status.className = 'status loading';
            status.style.display = 'block';
            status.innerHTML = 'Sending message to Facebook Messenger...';
            
            try {
                const response = await fetch('/send_message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(formData)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    status.className = 'status success';
                    status.innerHTML = '✅ ' + result.message;
                } else {
                    status.className = 'status error';
                    status.innerHTML = '❌ ' + result.message;
                }
            } catch (error) {
                status.className = 'status error';
                status.innerHTML = '❌ Network error: ' + error.message;
            }
            
            // Reset button
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Send Message';
        });
    </script>
</body>
</html>
"""

# Global variable to store async results
message_results = {}

async def send_message_async(group_id, message, cookies, result_id):
    """Async function to send message to Facebook Messenger group"""
    try:
        # Create session from cookies
        session = fbchat_muqit.Session.from_cookies(cookies)
        client = fbchat_muqit.Client(session=session)
        
        # Start the client
        await client.start()
        
        # Fetch thread to ensure it's a valid group
        thread = await client.fetch_thread(group_id)
        if not thread.is_group:
            message_results[result_id] = {
                'success': False,
                'message': f'Thread ID {group_id} is not a group chat.'
            }
            await client.stop()
            return
        
        # Send the message
        await client.send_text(message, thread_id=group_id)
        
        # Stop the client
        await client.stop()
        
        message_results[result_id] = {
            'success': True,
            'message': f'Message sent successfully to group {group_id}!'
        }
        
    except fbchat_muqit.FacebookError as e:
        message_results[result_id] = {
            'success': False,
            'message': f'Facebook Error: {str(e)}'
        }
    except Exception as e:
        message_results[result_id] = {
            'success': False,
            'message': f'Unexpected error: {str(e)}'
        }

def run_async_in_thread(coro, result_id):
    """Run async function in a new thread with its own event loop"""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()
    
    thread = threading.Thread(target=run)
    thread.start()
    return thread

@app.route('/')
def index():
    """Main page route"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/send_message', methods=['POST'])
def send_message():
    """API endpoint to send message"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['group_id', 'message', 'c_user', 'xs']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Prepare cookies
        cookies = {
            'c_user': data['c_user'],
            'xs': data['xs']
        }
        
        # Generate unique result ID
        result_id = str(int(time.time() * 1000))
        
        # Start async message sending in a separate thread
        coro = send_message_async(data['group_id'], data['message'], cookies, result_id)
        thread = run_async_in_thread(coro, result_id)
        
        # Wait for the thread to complete (with timeout)
        thread.join(timeout=30)  # 30 second timeout
        
        # Check if we have a result
        if result_id in message_results:
            result = message_results.pop(result_id)  # Remove from memory
            return jsonify(result)
        else:
            return jsonify({
                'success': False,
                'message': 'Request timed out or failed to complete'
            }), 408
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
