import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler # Import APScheduler
import logging

# --- Configure logging ---
# It's good practice to log scheduler activity
logging.basicConfig(level=logging.INFO)

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- Web Scraping Function (Your original function) ---
def scrape_share_prices():
    """
    Scrapes the 'Today Share Price' table from sharesansar.com and returns it as a list of dictionaries.
    """
    url = 'https://www.sharesansar.com/today-share-price'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    }
    try:
        req = requests.get(url, headers=headers, timeout=10)
        req.raise_for_status()
        soup = BeautifulSoup(req.text, 'html.parser')
        data_table = soup.find('table', id='headFixed')
        if not data_table:
            raise ValueError("Could not find the main data table with id='headFixed'.")
        thead = data_table.find('thead')
        if not thead:
            raise ValueError("Could not find the table header (<thead>).")
        header = [th.get_text(strip=True) for th in thead.find_all('th')]
        tbody = data_table.find('tbody')
        if not tbody:
            raise ValueError("Could not find the table body (<tbody>).")
        all_rows = []
        for row in tbody.find_all('tr'):
            cols = [ele.get_text(strip=True) for ele in row.find_all('td')]
            row_dict = dict(zip(header, cols))
            all_rows.append(row_dict)
        return all_rows
    except requests.exceptions.RequestException as e:
        print(f"Error making the request: {e}")
        raise ConnectionError(f"Failed to retrieve data from the website: {e}")
    except ValueError as e:
        print(f"Error parsing the HTML: {e}")
        raise ValueError(f"Error processing the website's HTML content: {e}")


# --- Health Check Function ---
def health_check():
    """
    Internal function to ping the app itself to keep it from sleeping.
    """
    try:
        # NOTE: This URL needs to point to your service. 
        # On Render's free tier, the internal host is typically '0.0.0.0' and port is 10000.
        # However, for a self-ping, use the service's public URL if available, or localhost.
        # Let's ping the new /health endpoint.
        r = requests.get('http://127.0.0.1:5000/health')
        r.raise_for_status() # Raise an exception for bad status codes
        logging.info(f"Health check ping successful: {r.status_code}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Health check failed: {e}")

# --- API Endpoints ---
@app.route('/health', methods=['GET'])
def health():
    """
    A lightweight endpoint that the scheduler can hit.
    It doesn't perform any heavy operations like scraping.
    """
    return jsonify({"status": "ok"}), 200

@app.route('/api/v1/share-prices', methods=['GET'])
def get_share_prices():
    """
    API endpoint to get the latest share prices.
    """
    try:
        data = scrape_share_prices()
        if not data:
            return jsonify({"error": "No data found on the page."}), 404
        return jsonify(data)
    except (ConnectionError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

# --- Main execution block ---
if __name__ == '__main__':
    # --- Initialize and start the scheduler ---
    scheduler = BackgroundScheduler()
    # Schedule the health_check function to run every 5 minutes
    scheduler.add_job(func=health_check, trigger="interval", minutes=5)
    scheduler.start()
    
    # Ensure the app runs on the port Render expects, or 5000 for local dev
    # For Render, you might need to use port 10000
    # port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=5000)