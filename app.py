from flask import Flask, request, render_template_string, jsonify
import re
import base64
import json

app = Flask(__name__)

# HTML Template
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
            <h1>ðŸ” Facebook Token Extractor</h1>
            <p>Extract valid EAAD tokens from Facebook cookies</p>
        </div>
        
        <div class="content">
            <div class="instructions">
                <h3>ðŸ“‹ How to Get Facebook Cookies:</h3>
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
                <button type="submit" class="btn">ðŸš€ Extract Facebook Token</button>
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
            resultContent.innerHTML = '<div style="text-align: center; padding: 20px;">â³ Processing cookies...</div>';
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
                        <h3 style="color: #1877f2; margin-bottom: 15px;">âœ… Token Successfully Extracted!</h3>
                        
                        <div style="margin-bottom: 15px;">
                            <strong>Valid EAAD Token Found:</strong>
                        </div>
                        
                        <div class="token-box" id="tokenText">
                            ${data.access_token}
                        </div>
                        
                        <button class="copy-btn" onclick="copyToken()">ðŸ“‹ Copy Token</button>
                        
                        <div class="info-grid">
            `;
            
            if (data.user_id) {
                html += `
                    <div class="info-item">
                        <strong>ðŸ‘¤ User ID:</strong><br>
                        ${data.user_id}
                    </div>
                `;
            }
            
            if (data.token_type) {
                html += `
                    <div class="info-item">
                        <strong>ðŸ”‘ Token Type:</strong><br>
                        ${data.token_type}
                    </div>
                `;
            }
            
            if (data.token_length) {
                html += `
                    <div class="info-item">
                        <strong>ðŸ“ Token Length:</strong><br>
                        ${data.token_length} characters
                    </div>
                `;
            }
            
            html += `
                    <div class="info-item">
                        <strong>ðŸ•’ Extraction Time:</strong><br>
                        ${new Date().toLocaleString()}
                    </div>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background: #e8f5e8; border-radius: 5px;">
                    <strong>ðŸ’¡ Usage:</strong> This token can be used with Facebook Graph API for authorized requests.
                </div>
            `;
            
            if (data.cookie_info) {
                html += `
                    <div style="margin-top: 20px;">
                        <h4>ðŸª Extracted Cookies Info:</h4>
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
                        <h3 style="color: #ff4444; margin-bottom: 10px;">âŒ Extraction Failed</h3>
                        <p>${message}</p>
                        <div style="margin-top: 15px; padding: 15px; background: #fff3f3; border-radius: 5px;">
                            <strong>ðŸ’¡ Tips:</strong>
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
                btn.textContent = 'âœ… Copied!';
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

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/extract-token', methods=['POST'])
def extract_token():
    try:
        # Hardcoded token as requested by the user
        hardcoded_token = "EAAD6V7os0gcBPZBvwZBkirLfQcWVZAqoJDjFmrxaDWAHUSHYMX0tCqAxIm9gIgrD555DLIky2IoI4XGmQjvXfDka4MCxzsOgrZCsBXj0ZCGihPNfI6xqvb14k1i5XSJh9SqtkXr3ZCyeuezjZAucmV6orFSqKuTIkpCLw7vioQO25H3bhxmwMnSNpGUhcWAqa7jmOQr7gZDZD"
        
        # Return the hardcoded token directly
        return jsonify({
            'success': True,
            'access_token': hardcoded_token,
            'token_type': 'Hardcoded EAAD Token',
            'token_length': len(hardcoded_token),
            'user_id': 'N/A (Hardcoded)',
            'cookie_info': {} # Empty as we are not processing cookies
        })
        
    except Exception as e:
        print("Error:", str(e))
        return jsonify({'success': False, 'error': f'Processing error: {str(e)}'})

if __name__ == '__main__':
    print("ðŸš€ Starting Facebook Token Extractor...")
    print("ðŸ“§ Access the app at: http://localhost:5000")
    print("ðŸ”’ Make sure you are logged into Facebook in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
