from flask import Flask, request, render_template_string, jsonify
import re
import json

app = Flask(__name__)

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Cookie Token Extractor</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f0f2f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #1877f2;
            text-align: center;
        }
        .cookie-input {
            width: 100%;
            height: 150px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin-bottom: 15px;
            font-family: monospace;
        }
        .btn {
            background-color: #1877f2;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }
        .btn:hover {
            background-color: #166fe5;
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 5px;
            background-color: #f8f9fa;
            display: none;
        }
        .token {
            word-break: break-all;
            background: #f1f3f4;
            padding: 10px;
            border-radius: 3px;
            margin-top: 10px;
        }
        .instructions {
            background: #e7f3ff;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Facebook Cookie Token Extractor</h1>
        
        <div class="instructions">
            <h3>How to use:</h3>
            <ol>
                <li>Open Facebook in your browser</li>
                <li>Press F12 to open Developer Tools</li>
                <li>Go to Console tab</li>
                <li>Type: <code>document.cookie</code> and press Enter</li>
                <li>Copy all cookies and paste below</li>
            </ol>
        </div>

        <form id="cookieForm">
            <textarea 
                class="cookie-input" 
                placeholder="Paste your Facebook cookies here..."
                id="cookies"
                name="cookies"></textarea>
            <button type="submit" class="btn">Extract Token</button>
        </form>

        <div id="result" class="result">
            <h3>Extracted Information:</h3>
            <div id="output"></div>
        </div>
    </div>

    <script>
        document.getElementById('cookieForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const cookies = document.getElementById('cookies').value;
            
            fetch('/extract-token', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({cookies: cookies})
            })
            .then(response => response.json())
            .then(data => {
                const resultDiv = document.getElementById('result');
                const outputDiv = document.getElementById('output');
                
                if (data.success) {
                    let html = '<h4>✅ Token found!</h4>';
                    
                    if (data.access_token) {
                        html += `<p><strong>Access Token:</strong></p>
                                <div class="token">${data.access_token}</div>`;
                    }
                    
                    if (data.user_id) {
                        html += `<p><strong>User ID:</strong> ${data.user_id}</p>`;
                    }
                    
                    if (data.cookie_info) {
                        html += '<h4>Cookie Information:</h4>';
                        for (const [key, value] of Object.entries(data.cookie_info)) {
                            html += `<p><strong>${key}:</strong> ${value}</p>`;
                        }
                    }
                    
                    outputDiv.innerHTML = html;
                } else {
                    outputDiv.innerHTML = `<p style="color: red;">❌ ${data.error}</p>`;
                }
                
                resultDiv.style.display = 'block';
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('output').innerHTML = '<p style="color: red;">An error occurred</p>';
                document.getElementById('result').style.display = 'block';
            });
        });
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
        data = request.get_json()
        cookies_string = data.get('cookies', '')
        
        if not cookies_string:
            return jsonify({'success': False, 'error': 'No cookies provided'})
        
        # Parse cookies
        cookies = {}
        cookie_pairs = cookies_string.split(';')
        
        for pair in cookie_pairs:
            pair = pair.strip()
            if '=' in pair:
                key, value = pair.split('=', 1)
                cookies[key.strip()] = value.strip()
        
        # Extract potential tokens and user information
        extracted_data = {}
        cookie_info = {}
        
        # Look for common Facebook cookie patterns
        for key, value in cookies.items():
            cookie_info[key] = value[:50] + '...' if len(value) > 50 else value
            
            # Look for access tokens
            if 'token' in key.lower() or 'access' in key.lower():
                extracted_data['access_token'] = value
            
            # Look for user ID
            if 'user' in key.lower() or 'uid' in key.lower():
                extracted_data['user_id'] = value
        
        # Try to find tokens in cookie values using regex
        token_patterns = [
            r'EAAG\w+',  # Facebook access token pattern
            r'[\w-]{100,}',  # Long strings that might be tokens
        ]
        
        for pattern in token_patterns:
            matches = re.findall(pattern, cookies_string)
            for match in matches:
                if len(match) > 50:  # Likely a token
                    extracted_data['access_token'] = match
                    break
        
        if not extracted_data:
            return jsonify({
                'success': False, 
                'error': 'No recognizable tokens found in cookies',
                'cookie_info': cookie_info
            })
        
        return jsonify({
            'success': True,
            **extracted_data,
            'cookie_info': cookie_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
