# api/portfolio_routes.py

from flask import Blueprint, request, jsonify
import logging
import os
import requests
from bs4 import BeautifulSoup

# Import the worksheet object from our central client file
from gspread_client import worksheet

# Create a Blueprint
portfolio_bp = Blueprint('portfolio_bp', __name__)

# --- MOVED SCRAPING FUNCTION ---
def scrape_share_prices():
    url = os.getenv("SCRAPE_API") # Corrected from "scrape_API" to match .env
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
        raise ConnectionError(f"Failed to retrieve data from the website: {e}")
    except ValueError as e:
        raise ValueError(f"Error processing the website's HTML content: {e}")

# --- NEW ENDPOINT FOR SHARE PRICES ---
@portfolio_bp.route('/prices', methods=['GET'])
def get_share_prices():
    """Gets the latest share prices from the website."""
    try:
        data = scrape_share_prices()
        if not data:
            return jsonify({"error": "No data found on the page."}), 404
        return jsonify(data)
    except (ConnectionError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

# --- EXISTING PORTFOLIO ROUTES ---
@portfolio_bp.route('/', methods=['GET'])
def get_portfolio():
    """Gets all portfolio data from the sheet."""
    # ... (function is unchanged) ...
    if worksheet is None:
        return jsonify({"error": "Google Sheets not connected. Check server logs."}), 500
    try:
        records = worksheet.get_all_records()
        return jsonify(records)
    except Exception as e:
        logging.error(f"Error fetching from Google Sheets: {e}")
        return jsonify({"error": "An error occurred while fetching the portfolio."}), 500

@portfolio_bp.route('/add', methods=['POST'])
def add_stock():
    """Adds a new stock purchase to the sheet."""
    # ... (function is unchanged) ...
    if worksheet is None:
        return jsonify({"error": "Google Sheets not connected. Check server logs."}), 500
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON payload."}), 400

        required_fields = ['symbol', 'quantity', 'price', 'date']
        if not all(field in data for field in required_fields):
            return jsonify({"error": f"Missing required fields: {required_fields}"}), 400
        
        new_row = [data['symbol'], data['quantity'], data['price'], data['date']]
        
        worksheet.append_row(new_row, value_input_option='USER_ENTERED')
        
        logging.info(f"Successfully added new stock: {new_row}")
        return jsonify({"status": "success", "message": "Stock purchase added."}), 201
    except Exception as e:
        logging.error(f"Error adding stock to Google Sheets: {e}")
        return jsonify({"error": "An unexpected error occurred."}), 500
    

@portfolio_bp.route('/summary', methods=['GET'])
def get_portfolio_summary():
    """
    Merges portfolio data with live market prices to provide a full summary.
    """
    try:
        # Step 1: Get portfolio and market data
        portfolio_holdings = worksheet.get_all_records()
        market_data_list = scrape_share_prices()

        # Step 2: Convert market data to a dictionary for fast lookups (Symbol -> data)
        market_prices = {item['Symbol']: item for item in market_data_list}

        # Step 3: Calculate the total purchase value of the portfolio for weight calculation
        total_portfolio_purchase_value = sum(
            stock.get('quantity', 0) * stock.get('purchasePrice', 0)
            for stock in portfolio_holdings
        )
        # Avoid division by zero if portfolio is empty
        if total_portfolio_purchase_value == 0:
            total_portfolio_purchase_value = 1 

        # Step 4: Process each stock holding
        summary_list = []
        for stock in portfolio_holdings:
            symbol = stock.get('scrip')
            if not symbol or not stock.get('quantity'):
                continue

            purchase_price = stock.get('purchasePrice', 0)
            quantity = stock.get('quantity', 0)
            
            # Find the corresponding market data for the current stock
            stock_market_data = market_prices.get(symbol)
            
            # --- Initialize values ---
            ltp = 0.0
            week_high_low = "N/A"

            # --- Safely extract and convert data if market data exists ---
            if stock_market_data:
                try:
                    # Remove commas from numbers and convert to float
                    ltp = float(stock_market_data.get('LTP', '0').replace(',', ''))
                except (ValueError, AttributeError):
                    ltp = 0.0 # Default to 0 if data is invalid
                
                high = stock_market_data.get('52 Weeks High', 'N/A')
                low = stock_market_data.get('52 Weeks Low', 'N/A')
                week_high_low = f"{high} / {low}"

            # --- Perform calculations ---
            purchase_value = purchase_price * quantity
            current_value = ltp * quantity if ltp > 0 else 0 # <- ADDED CALCULATION
            profit_amount = current_value - purchase_value
            
            # Avoid division by zero for profit percentage
            if purchase_price > 0 and ltp > 0:
                profit_percentage = (profit_amount / purchase_value) * 100
            else:
                profit_percentage = 0

            weight_percentage = (purchase_value / total_portfolio_purchase_value) * 100

            # --- Construct the final JSON object for this stock ---
            summary_list.append({
                "Script": symbol,
                "quantity": quantity,
                "purchase price": purchase_price,
                "LTP": ltp,
                "Current Value": round(current_value, 2), # <- ADDED FIELD
                "52 week high/low": week_high_low,
                "Profit amount": round(profit_amount, 2),
                "profit percentage": f"{round(profit_percentage, 2)}%",
                "Purchase value": round(purchase_value, 2),
                "Weight%": f"{round(weight_percentage, 2)}%"
            })
            
        return jsonify(summary_list)

    except Exception as e:
        logging.error(f"Error creating portfolio summary: {e}")
        return jsonify({"error": f"An unexpected error occurred while generating summary: {e}"}), 500
