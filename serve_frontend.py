#!/usr/bin/env python3
"""
Simple HTTP server to serve the frontend HTML file.
This prevents CORS issues when opening HTML files directly.

Usage:
    python serve_frontend.py

Then visit: http://localhost:3000/index.html
"""
import http.server
import socketserver
import os
import sys
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()
PORT = 3000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler with better error messages"""
    
    def end_headers(self):
        # Add CORS headers for development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def log_message(self, format, *args):
        """Override to show cleaner log messages"""
        print(f"[{self.address_string()}] {args[0]}")

def main():
    """Start the HTTP server"""
    # Change to the script directory
    os.chdir(SCRIPT_DIR)
    
    # Check if index.html exists
    if not (SCRIPT_DIR / "index.html").exists():
        print(f"❌ Error: index.html not found in {SCRIPT_DIR}")
        print("   Please make sure index.html is in the same directory as this script.")
        sys.exit(1)
    
    # Create server
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print("=" * 60)
        print("🚀 Frontend Server Started!")
        print("=" * 60)
        print(f"📁 Serving directory: {SCRIPT_DIR}")
        print(f"🌐 Server running at: http://localhost:{PORT}/")
        print(f"📄 Open in browser: http://localhost:{PORT}/index.html")
        print("=" * 60)
        print("Press Ctrl+C to stop the server")
        print("=" * 60)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n🛑 Server stopped by user")
            sys.exit(0)

if __name__ == "__main__":
    main()

