#!/usr/bin/env python3
"""
Startup script for STONE RULEX Enhanced Facebook Bot
This script provides an easy way to start the server with proper configuration
"""

import os
import sys
import subprocess
import time

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = ['flask', 'flask_cors', 'requests']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - OK")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - Missing")
    
    if missing_packages:
        print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("✅ All dependencies installed successfully!")
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies. Please install manually:")
            print(f"pip3 install {' '.join(missing_packages)}")
            return False
    
    return True

def display_banner():
    """Display startup banner"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    STONE RULEX ENHANCED                      ║
║              Facebook Bot with Admin System                  ║
║                                                              ║
║  🚀 Features:                                                ║
║  • Admin Authentication System                               ║
║  • User Registration & Approval                              ║
║  • Advanced Suspension Prevention                            ║
║  • Smart Token Management                                    ║
║  • Real-time Logging & Monitoring                           ║
║  • Mobile-Friendly Interface                                 ║
║                                                              ║
║  🔐 Admin Credentials:                                       ║
║  Username: onfire_stone                                      ║
║  Password: stoneOO7                                          ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

def display_instructions():
    """Display usage instructions"""
    instructions = """
📋 USAGE INSTRUCTIONS:

1. 🌐 Access the System:
   • Open your browser and go to: http://localhost:5000
   • You'll be redirected to the login page

2. 👤 For New Users:
   • Click "Sign Up" to create a new account
   • Wait for admin approval before using tools

3. 🔐 For Admin:
   • Use admin credentials to access admin panel
   • Approve/manage users through the admin interface

4. 🛠️ Available Tools:
   • CONVO TOOL: Send messages to Facebook conversations
   • TOKEN CHECKER: Validate Facebook access tokens
   • UID FETCHER: Get messenger group/conversation UIDs
   • TASK MANAGER: Monitor and manage active tasks

5. 🛡️ Suspension Prevention:
   • System automatically implements anti-detection measures
   • Smart token rotation and rate limiting
   • Enhanced error handling and recovery

⚠️  IMPORTANT NOTES:
• Use valid Facebook tokens only
• Respect Facebook's Terms of Service
• Use reasonable delays between messages (minimum 2 seconds)
• Monitor your token usage to avoid suspension

🔧 Configuration:
• Admin credentials can be changed in integrated_facebook_bot.py
• Adjust rate limiting and delays as needed
• Check logs for troubleshooting information
"""
    print(instructions)

def start_server():
    """Start the Flask server"""
    print("🚀 Starting STONE RULEX Enhanced Server...")
    print("📡 Server will be available at: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop the server")
    print("-" * 60)
    
    try:
        # Import and run the main application
        from integrated_facebook_bot import app
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        print("💡 Make sure integrated_facebook_bot.py is in the same directory")

def main():
    """Main startup function"""
    display_banner()
    
    # Check if main script exists
    if not os.path.exists('integrated_facebook_bot.py'):
        print("❌ Error: integrated_facebook_bot.py not found!")
        print("💡 Make sure you're running this script from the correct directory")
        return
    
    # Check dependencies
    if not check_dependencies():
        print("❌ Dependency check failed. Please resolve issues and try again.")
        return
    
    display_instructions()
    
    # Ask user if they want to start the server
    try:
        response = input("\n🚀 Start the server now? (y/n): ").lower().strip()
        if response in ['y', 'yes', '']:
            start_server()
        else:
            print("👋 Server not started. Run this script again when ready.")
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
