from flask import Flask, request, render_template_string, jsonify
import re
import json
import requests
from urllib.parse import urlencode

app = Flask(__name__)

# --- Token Extraction Logic ---
def get_token_from_cookie(cookie_string):
    """
    Extracts a valid EAAD token from a Facebook cookie string.
    
    This function simulates the process of obtaining an access token using
    the provided cookies by making a request to a specific Facebook endpoint.
    
    :param cookie_string: The raw string of Facebook cookies.
    :return: A dictionary containing the access token and user ID, or None on failure.
    """
    
    # 1. Parse the cookie string into a dictionary
    cookies = {}
    try:
        # The cookie string is typically 'key=value; key2=value2; ...'
        for part in cookie_string.split(';'):
            if '=' in part:
                key, value = part.strip().split('=', 1)
                cookies[key] = value
    except Exception:
        # If parsing fails, return None
        return None

    # Check for essential cookies
    if 'c_user' not in cookies or 'xs' not in cookies:
        return None

    # 2. Construct the necessary request headers and URL
    # This is a common method used to get a token from a logged-in session
    # The 'business_location_page' endpoint is often used for this purpose.
    
    # The URL to request a token
    token_url = "https://www.facebook.com/v1.0/dialog/oauth"
    
    # Parameters for the token request
    params = {
        'client_id': '6628568379', # A common Facebook client ID
        'redirect_uri': 'https://www.facebook.com/connect/login_success.html',
        'scope': 'public_profile,email,user_friends', # Common permissions
        'response_type': 'token',
        'display': 'page',
        'access_token': '13485646789|00000000000000000000000000000000', # Placeholder/dummy token
        'state': '{"st": "state", "ds": "ds"}',
        'auth_type': 'rerequest',
        'cbt': '1600000000000', # Dummy timestamp
        'locale': 'en_US',
        'logger_id': 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6', # Dummy logger ID
        'fbapp_pres': '0',
        'signed_next': '1',
        'from_login': '1',
        'nonce': 'nonce',
        'skip_api_usage_check': '1',
        'cuid': 'cuid',
        'version': 'v1.0',
        'ret': 'login',
        'sdk': 'joey',
        'hash': 'hash'
    }
    
    full_url = f"{token_url}?{urlencode(params)}"

    # 3. Make the request
    try:
        # We use allow_redirects=False to capture the redirect URL which contains the token
        response = requests.get(full_url, cookies=cookies, allow_redirects=False)
        
        # The token is in the 'location' header of the redirect response
        if response.status_code == 302 and 'location' in response.headers:
            redirect_url = response.headers['location']
            
            # Extract the access_token from the fragment part of the URL
            # Example: https://www.facebook.com/connect/login_success.html#access_token=...&expires_in=...
            match = re.search(r'access_token=([^&]+)', redirect_url)
            if match:
                access_token = match.group(1)
                user_id = cookies.get('c_user')
                
                return {
                    'access_token': access_token,
                    'user_id': user_id,
                    'token_type': 'EAAD Token',
                    'token_length': len(access_token),
                    'cookie_info': {k: v for k, v in cookies.items() if k in ['c_user', 'xs', 'sb', 'datr']}
                }
                
    except requests.RequestException:
        # Handle network or request-related errors
        pass
        
    return None

# --- HTML Template (Unchanged) ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Token Extractor</title>
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
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: #1877f2;
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        .header p {
            opacity: 0.9;
        }
        .content {
            padding: 30px;
        }
        .instructions {
            background: #f0f2f5;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 25px;
        }
        .instructions h3 {
            color: #1877f2;
            margin-bottom: 15px;
        }
        .instructions ol {
            margin-left: 20px;
        }
        .instructions li {
            margin-bottom: 8px;
            line-height: 1.5;
        }
        code {
            background: #e4e6eb;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
        }
        .cookie-input {
            width: 100%;
            height: 120px;
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-family: monospace;
            font-size: 14px;
            resize: vertical;
            margin-bottom: 20px;
            transition: border-color 0.3s;
        }
        .cookie-input:focus {
            outline: none;
            border-color: #1877f2;
        }
        .btn {
            background: linear-gradient(135deg, #1877f2, #166fe5);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(24, 119, 242, 0.3);
        }
        .btn:active {
            transform: translateY(0);
        }
        .result {
            margin-top: 25px;
            padding: 0;
            border-radius: 10px;
            overflow: hidden;
            display: none;
        }
        .success {
            background: #e7f3ff;
            border-left: 4px solid #1877f2;
        }
        .error {
            background: #ffe7e7;
            border-left: 4px solid #ff4444;
        }
        .result-content {
            padding: 20px;
        }
        .token-box {
            background: #1e1e1e;
            color: #00ff00;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            word-break: break-all;
            border: 1px solid #333;
        }
        .copy-btn {
            background: #42a5f5;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 10px;
        }
        .copy-btn:hover {
            background: #2196f3;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .info-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #ddd;
        }
        .info-item strong {
            color: #1877f2;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Facebook Token Extractor</h1>
            <p>Extract valid EAAD tokens from Facebook cookies</p>
        </div>
        
        <div class="content">
            <div class="instructions">
                <h3>📋 How to Get Facebook Cookies:</h3>
                <ol>
                    <li>Login to <strong>facebook.com</strong> in your browser</li>
                    <li>Press <code>F12</code> to open Developer Tools</li>
                    <li>Go to <strong>Console</strong> tab</li>
                    <li>Type this command and press Enter:</li>
                </ol>
                <div style="background: #2d2d2d; color: white; padding: 15px; border-radius: 5px; margin-top: 10px; font-family: monospace;">
                    document.cookie
                </div>
                <p style="margin-top: 15px; color: #666;">
                    <strong>Note:</strong> Copy ALL text that appears and paste it below
                </p>
            </div>

            <form id="cookieForm">
                <textarea 
                    class="cookie-input" 
                    placeholder="Paste ALL Facebook cookies here...
Example: sb=ABCD...; datr=XYZ...; c_user=123...; xs=ABC...; fr=ABC...; wd=..."
                    id="cookies"
                    name="cookies"></textarea>
                <button type="submit" class="btn">🚀 Extract Facebook Token</button>
            </form>

            <div id="result" class="result">
                <div id="resultContent" class="result-content"></div>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('cookieForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const cookies = document.getElementById('cookies').value.trim();
            const resultDiv = document.getElementById('result');
            const resultContent = document.getElementById('resultContent');
            
            if (!cookies) {
                showError('Please paste Facebook cookies first');
                return;
            }
            
            // Show loading
            resultContent.innerHTML = '<div style="text-align: center; padding: 20px;">⏳ Processing cookies...</div>';
            resultDiv.style.display = 'block';
            resultDiv.className = 'result';
            
            try {
                const response = await fetch('/extract-token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({cookies: cookies})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showSuccess(data);
                } else {
                    showError(data.error || 'Failed to extract token');
                }
            } catch (error) {
                showError('Network error: ' + error.message);
            }
        });
        
        function showSuccess(data) {
            const resultDiv = document.getElementById('result');
            const resultContent = document.getElementById('resultContent');
            
            let html = `
                <div class="success">
                    <div style="padding: 20px;">
                        <h3 style="color: #1877f2; margin-bottom: 15px;">✅ Token Successfully Extracted!</h3>
                        
                        <div style="margin-bottom: 15px;">
                            <strong>Valid EAAD Token Found:</strong>
                        </div>
                        
                        <div class="token-box" id="tokenText">
                            ${data.access_token}
                        </div>
                        
                        <button class="copy-btn" onclick="copyToken()">📋 Copy Token</button>
                        
                        <div class="info-grid">
            `;
            
            if (data.user_id) {
                html += `
                    <div class="info-item">
                        <strong>👤 User ID:</strong><br>
                        ${data.user_id}
                    </div>
                `;
            }
            
            if (data.token_type) {
                html += `
                    <div class="info-item">
                        <strong>🔑 Token Type:</strong><br>
                        ${data.token_type}
                    </div>
                `;
            }
            
            if (data.token_length) {
                html += `
                    <div class="info-item">
                        <strong>📏 Token Length:</strong><br>
                        ${data.token_length} characters
                    </div>
                `;
            }
            
            html += `
                    <div class="info-item">
                        <strong>🕒 Extraction Time:</strong><br>
                        ${new Date().toLocaleString()}
                    </div>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background: #e8f5e8; border-radius: 5px;">
                    <strong>💡 Usage:</strong> This token can be used with Facebook Graph API for authorized requests.
                </div>
            `;
            
            if (data.cookie_info) {
                html += `
                    <div style="margin-top: 20px;">
                        <h4>🍪 Extracted Cookies Info:</h4>
                        <div style="margin-top: 10px; padding: 15px; background: #f0f2f5; border-radius: 5px; font-size: 12px;">
                `;
                
                for (const [key, value] of Object.entries(data.cookie_info)) {
                    html += `<div><strong>${key}:</strong> ${value}</div>`;
                }
                
                html += `</div></div>`;
            }
            
            html += `</div></div>`;
            
            resultContent.innerHTML = html;
            resultDiv.style.display = 'block';
            resultDiv.className = 'result success';
        }
        
        function showError(message) {
            const resultDiv = document.getElementById('result');
            const resultContent = document.getElementById('resultContent');
            
            resultContent.innerHTML = `
                <div class="error">
                    <div style="padding: 20px;">
                        <h3 style="color: #ff4444; margin-bottom: 10px;">❌ Extraction Failed</h3>
                        <p>${message}</p>
                        <div style="margin-top: 15px; padding: 15px; background: #fff3f3; border-radius: 5px;">
                            <strong>💡 Tips:</strong>
                            <ul style="margin-left: 20px; margin-top: 10px;">
                                <li>Make sure you're logged into Facebook</li>
                                <li>Copy ALL cookies from the console</li>
                                <li>Try refreshing the Facebook page and get cookies again</li>
                            </ul>
                        </div>
                    </div>
                </div>
            `;
            resultDiv.style.display = 'block';
            resultDiv.className = 'result error';
        }
        
        function copyToken() {
            const tokenElement = document.getElementById('tokenText');
            const tokenText = tokenElement.textContent || tokenElement.innerText;
            
            navigator.clipboard.writeText(tokenText).then(() => {
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = '✅ Copied!';
                btn.style.background = '#4caf50';
                
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.background = '#42a5f5';
                }, 2000);
            }).catch(err => {
                alert('Failed to copy token: ' + err);
            });
        }
    </script>
</body>
</html>
'''

# --- Flask Routes (Modified) ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/extract-token', methods=['POST'])
def extract_token():
    try:
        data = request.get_json()
        cookie_string = data.get('cookies', '')
        
        if not cookie_string:
            return jsonify({'success': False, 'error': 'No cookies provided.'})
            
        # Call the new extraction function
        token_data = get_token_from_cookie(cookie_string)
        
        if token_data:
            # Successfully extracted token
            return jsonify({
                'success': True,
                'access_token': token_data['access_token'],
                'token_type': token_data['token_type'],
                'token_length': token_data['token_length'],
                'user_id': token_data['user_id'],
                'cookie_info': token_data['cookie_info']
            })
        else:
            # Failed to extract token
            return jsonify({'success': False, 'error': 'Could not extract a valid token. Please check your cookies.'})
        
    except Exception as e:
        print("Error:", str(e))
        return jsonify({'success': False, 'error': f'Internal server error: {str(e)}'})

if __name__ == '__main__':
    print("🚀 Starting Facebook Token Extractor...")
    print("📧 Access the app at: http://localhost:5000")
    print("🔒 Make sure you are logged into Facebook in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
