from flask import Flask, request, jsonify
import re

app = Flask(__name__)

@app.route('/extract_token', methods=['POST'])
def extract_token():
    """
    Extracts a Facebook token from a given cookie string.
    Expects a JSON payload with a 'cookie' field.
    e.g., {"cookie": "your_full_cookie_string_here"}
    """
    data = request.get_json()
    if not data or 'cookie' not in data:
        return jsonify({"error": "Please provide the cookie in the 'cookie' field."}), 400

    cookie_string = data['cookie']
    
    # Regular expression to find the specified token format starting with EAAD6V7os0gc
    # This regex will match the token you provided.
    match = re.search(r'EAAD6V7os0gc[a-zA-Z0-9_.-]+', cookie_string)
    
    if match:
        token = match.group(0)
        return jsonify({"token": token})
    else:
        # If the specific token is not found, try a more generic pattern for EAAD tokens
        generic_match = re.search(r'EAAD[a-zA-Z0-9_.-]+', cookie_string)
        if generic_match:
            token = generic_match.group(0)
            return jsonify({"token": token, "note": "Found a generic EAAD token, not the specific one requested."})
        
        return jsonify({"error": "Token not found in the provided cookie."}), 404

if __name__ == '__main__':
    # To run this:
    # 1. Save the code as app.py
    # 2. Make sure you have Flask installed (`pip install Flask`).
    # 3. Run the script from your terminal: `python app.py`
    # 4. The app will be running on http://127.0.0.1:5000
    #
    # To test it, you can use a tool like curl:
    # curl -X POST -H "Content-Type: application/json" -d "{\"cookie\": \"your_long_cookie_string_containing_the_token\"}" http://127.0.0.1:5000/extract_token
    app.run(debug=True, port=5000)
    
