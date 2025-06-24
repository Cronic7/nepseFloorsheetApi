import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify

# --- Flask App Initialization ---
# Create an instance of the Flask class. This is our web application.
app = Flask(__name__)

# --- Web Scraping Function ---
# This function contains the logic to scrape the data from the website.
def scrape_share_prices():
    """
    Scrapes the 'Today Share Price' table from sharesansar.com and returns it as a list of dictionaries.
    """
    # URL and headers for the request
    url = 'https://www.sharesansar.com/today-share-price'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    }

    # Make the GET request to the website
    # A try-except block is used to handle potential network or parsing errors gracefully.
    try:
        req = requests.get(url, headers=headers, timeout=10) # Added a timeout for safety
        req.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the HTML content of the page
        soup = BeautifulSoup(req.text, 'html.parser')

        # Find the main table element
        data_table = soup.find('table', id='headFixed')
        if not data_table:
            # If the specific table is not found, raise an error.
            raise ValueError("Could not find the main data table with id='headFixed'.")

        # --- Find and process the table header ---
        thead = data_table.find('thead')
        if not thead:
            raise ValueError("Could not find the table header (<thead>).")
            
        # Extract header titles from th tags. These will become the keys in our JSON objects.
        # A list comprehension provides a concise way to create the list.
        header = [th.get_text(strip=True) for th in thead.find_all('th')]
        
        # --- Find and process the table body ---
        tbody = data_table.find('tbody')
        if not tbody:
            raise ValueError("Could not find the table body (<tbody>).")

        # --- Extract data and structure it as a list of dictionaries ---
        # This is a more API-friendly format than separate lists for header and data.
        all_rows = []
        # Iterate over each table row (tr) in the table body
        for row in tbody.find_all('tr'):
            # Get all cell (td) texts for the current row
            cols = [ele.get_text(strip=True) for ele in row.find_all('td')]
            # Create a dictionary by zipping the header and the row's columns together
            # This pairs each data point with its corresponding header (e.g., {'Symbol': 'NABIL', 'LTP': '550'})
            row_dict = dict(zip(header, cols))
            all_rows.append(row_dict)
            
        return all_rows

    # Catch specific exceptions for better error handling
    except requests.exceptions.RequestException as e:
        print(f"Error making the request: {e}")
        # Re-raise with a custom message for the API response
        raise ConnectionError(f"Failed to retrieve data from the website: {e}")
    except ValueError as e:
        print(f"Error parsing the HTML: {e}")
        # Re-raise with a custom message
        raise ValueError(f"Error processing the website's HTML content: {e}")


 
@app.route('/api/v1/share-prices', methods=['GET'])
def get_share_prices():
    """
    API endpoint to get the latest share prices.
    """
    try:
        # Call the scraping function to get the data
        data = scrape_share_prices()
        
        # Check if data was actually returned
        if not data:
            # Return a 404 Not Found error if no data could be scraped
            return jsonify({"error": "No data found on the page."}), 404
            
        # Use Flask's jsonify to convert our list of dictionaries into a JSON response.
        # This also sets the correct Content-Type header to 'application/json'.
        return jsonify(data)
        
    except (ConnectionError, ValueError) as e:
        # If any of our custom errors are raised during scraping, return a 500 Internal Server Error.
        # This tells the API consumer that something went wrong on our end.
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        # A general catch-all for any other unexpected errors.
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

# --- Main execution block ---
# This code runs only when the script is executed directly (not when imported).
if __name__ == '__main__':
   
    app.run(debug=True, host='0.0.0.0', port=5000)
