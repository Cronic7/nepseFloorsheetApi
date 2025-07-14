# app.py

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS

# Import the Blueprint from your new routes file
from api.portfolio_routes import portfolio_bp

# --- Configure logging ---
logging.basicConfig(level=logging.INFO)

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- Register Blueprints ---
# This prefix applies to all routes in portfolio_bp, including our new '/prices' route
app.register_blueprint(portfolio_bp, url_prefix='/api/v1/portfolio')

# --- Health Check Endpoint ---
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

# --- Main execution block ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)