# api/portfolio_routes.py

from flask import Blueprint, request, jsonify
import logging
import os
import requests
from bs4 import BeautifulSoup
from datetime import date 

# --- CORRECTED IMPORT ---
# Import the new, correct variable names from your client file
from gspread_client import portfolio_sheet, turnover_sheet, daily_data_sheet , watchlist_sheet

# Create a Blueprint
portfolio_bp = Blueprint('portfolio_bp', __name__)

# --- Market Summary and other functions from before ---
# (No changes needed in these helper functions).00.
def scrape_market_summary():
    # ... (function is correct)
    url = os.getenv("SCRAPE_API")+'/market-summary'
    print(url)
    headers = { 'User-Agent': 'Mozilla/5.0 ...' }
    try:
        req = requests.get(url, headers=headers, timeout=10)
        req.raise_for_status()
        soup = BeautifulSoup(req.text, 'html.parser')
        summary_div = soup.find('div', id='market_symmary_data')
        if not summary_div:
            raise ValueError("Could not find market summary container.")
        date_span = summary_div.find('span', class_='text-org')
        if not date_span:
            raise ValueError("Could not find market date.")
        market_date = date_span.get_text(strip=True)
        summary_data = {"Date": market_date}
        rows = summary_div.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) == 2:
                key = cells[0].get_text(strip=True).replace('(Rs.)', '').strip()
                value = cells[1].get_text(strip=True)
                summary_data[key] = value
        return summary_data
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Failed to retrieve market summary: {e}")
    except ValueError as e:
        raise ValueError(f"Error processing market summary HTML: {e}")

def scrape_share_prices():
    # ... (function is correct)
    url = os.getenv("SCRAPE_API")+'/today-share-price'
    headers = {'User-Agent': 'Mozilla/5.0 ...'}
    try:
        req = requests.get(url, headers=headers, timeout=10)
        req.raise_for_status()
        soup = BeautifulSoup(req.text, 'html.parser')
        data_table = soup.find('table', id='headFixed')
        if not data_table:
            raise ValueError("Could not find data table with id='headFixed'.")
        thead = data_table.find('thead')
        if not thead:
            raise ValueError("Could not find table header.")
        header = [th.get_text(strip=True) for th in thead.find_all('th')]
        tbody = data_table.find('tbody')
        if not tbody:
            raise ValueError("Could not find table body.")
        all_rows = []
        for row in tbody.find_all('tr'):
            cols = [ele.get_text(strip=True) for ele in row.find_all('td')]
            row_dict = dict(zip(header, cols))
            all_rows.append(row_dict)
        return all_rows
       
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Failed to retrieve data from website: {e}")
    except ValueError as e:
        raise ValueError(f"Error processing HTML content: {e}")

# --- UPDATED ROUTES ---

def save_full_daily_snapshot(all_share_data):
    """
    Appends a full snapshot of the day's share data to the DailyMarketData sheet.
    Checks for the date to avoid saving duplicate data for the same day.
    """
    if daily_data_sheet is None:
        logging.error("Google Sheets 'DailyMarketData' not connected. Cannot save full snapshot.")
        return

    if not all_share_data:
        logging.warning("No share data provided to save_full_daily_snapshot.")
        return
        
    try:
        today_str = date.today().isoformat()

        # --- NEW: Check if data for today already exists ---
        # This prevents adding duplicate data if the script is run multiple times a day.
        # It checks the first column ('Date') for today's date.
        cell = daily_data_sheet.find(today_str, in_column=1)
        if cell:
            logging.info(f"Full market snapshot for {today_str} already exists. Skipping save.")
            return

        # Define headers in the correct order, with 'Date' first.
        headers = [
            'Date', 'S.No', 'Symbol', 'Conf.', 'Open', 'High', 'Low', 'Close', 
            'LTP', 'Close - LTP', 'Close - LTP %', 'VWAP', 'Vol', 'Prev. Close', 
            'Turnover', 'Trans.', 'Diff', 'Range', 'Diff %', 'Range %', 'VWAP %', 
            '120 Days', '180 Days', '52 Weeks High', '52 Weeks Low'
        ]
        
        # Prepare all rows for a single batch update
        rows_to_add = []
        for record in all_share_data:
            # Create a list of values for the current record, starting with the date
            # Note: We skip the first header ('Date') when mapping record values
            row_values = [today_str] + [record.get(h, "N/A") for h in headers[1:]]
            rows_to_add.append(row_values)
            
        if rows_to_add:
            # --- MODIFIED: Use append_rows without clearing the sheet ---
            daily_data_sheet.append_rows(rows_to_add, value_input_option='USER_ENTERED')
            logging.info(f"Successfully APPENDED full market snapshot with {len(all_share_data)} records for {today_str}.")

    except Exception as e:
        logging.error(f"Failed to save and append full daily snapshot to Google Sheets: {e}")

@portfolio_bp.route('/market-summary', methods=['GET'])
def get_market_summary():
    if turnover_sheet is None:
        return jsonify({"error": "Google Sheets 'Turnover' tab not connected."}), 500
    # ... (rest of this function is correct and uses turnover_sheet)
    try:
        latest_data = scrape_market_summary()
        latest_date = latest_data.get("Date")
        existing_records = turnover_sheet.get_all_records()
        saved_dates = {str(record.get('Date')) for record in existing_records}
        if latest_date in saved_dates:
            logging.info(f"Market data for {latest_date} already exists.")
            for record in existing_records:
                if str(record.get('Date')) == latest_date:
                    return jsonify(record)
            return jsonify({"error": "Data found but could not be retrieved."}), 500
        else:
            logging.info(f"New market data for {latest_date} found. Saving to sheet.")
            headers = ["Date", "Total Turnovers", "Total Traded Shares", "Total Transaction", "Total Scrips Traded", "Total Market Cap", "Floated Market Cap"]
            new_row = [latest_data.get(header, "N/A") for header in headers]
            turnover_sheet.append_row(new_row, value_input_option='USER_ENTERED')
            return jsonify(latest_data)
    except (ConnectionError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@portfolio_bp.route('/prices', methods=['GET'])
def get_share_prices():
    """
    Fetches live prices AND triggers the save to Google Sheets.
    """
    try:
        data = scrape_share_prices()
        if not data:
            return jsonify({"error": "No data found on the page."}), 404

        # --- FIX: Call the save function here ---
        # This line was missing. It tells the app to save the data it just scraped.
        save_full_daily_snapshot(data)

        return jsonify(data)
    except (ConnectionError, ValueError) as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

@portfolio_bp.route('/', methods=['GET'])
def get_portfolio():
    """Gets all portfolio data from the sheet."""
    # **FIX**: Use portfolio_sheet instead of worksheet
    if portfolio_sheet is None:
        return jsonify({"error": "Google Sheets 'Portfolio' not connected."}), 500
    try:
        # **FIX**: Use portfolio_sheet instead of worksheet
        records = portfolio_sheet.get_all_records()
        return jsonify(records)
    except Exception as e:
        logging.error(f"Error fetching from Google Sheets: {e}")
        return jsonify({"error": "An error occurred while fetching the portfolio."}), 500


#put watchlist

@portfolio_bp.route('/wishlist/add', methods=['PUT'])
def add_to_wishlist():
    """
    Adds a stock scrip to the wishlist sheet.
    Returns an error if the scrip already exists.
    """
    try:
        # Check if the 'watchlist_sheet' is connected
        if watchlist_sheet is None:
            return jsonify({"error": "Google Sheets 'Watchlist' not connected."}), 500

        data = request.get_json()

        # Validate that the 'scrip' field is in the request body
        if 'scrip' not in data:
            return jsonify({"error": "Missing required field: 'scrip'"}), 400
        
        scrip_to_add = data['scrip']

        # --- NEW: Check if the scrip already exists ---
        # This assumes scrips are in the first column (A)
        existing_cell = watchlist_sheet.find(scrip_to_add, in_column=1)
        if existing_cell:
            return jsonify({"error": f"Scrip '{scrip_to_add}' already exists in wishlist."}), 409 # 409 Conflict

        # If it doesn't exist, prepare the new row
        new_row = [scrip_to_add]
        
        # Append the new row to the watchlist sheet
        watchlist_sheet.append_row(new_row, value_input_option='USER_ENTERED')
        
        return jsonify({"message": "Scrip added to wishlist successfully."}), 201
        
    except Exception as e:
        logging.error(f"Error adding to wishlist: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500
    
# Delete Watchlist
@portfolio_bp.route('/wishlist/remove', methods=['DELETE'])
def remove_from_wishlist():
    """Removes a stock scrip from the wishlist sheet."""
    try:
        # Check if the 'watchlist_sheet' is connected
        if watchlist_sheet is None:
            return jsonify({"error": "Google Sheets 'Watchlist' not connected."}), 500

        data = request.get_json()

        # Validate that the 'scrip' field is in the request body
        if 'scrip' not in data:
            return jsonify({"error": "Missing required field: 'scrip'"}), 400
            
        scrip_to_delete = data['scrip']

        # Find the cell with the matching scrip
        # This assumes scrips are in the first column (A)
        cell_to_delete = watchlist_sheet.find(scrip_to_delete, in_column=1)
        
        if cell_to_delete:
            # If found, delete the entire row
            watchlist_sheet.delete_rows(cell_to_delete.row)
            return jsonify({"message": f"Scrip '{scrip_to_delete}' removed from wishlist."}), 200
        else:
            # If not found, return a 404 error
            return jsonify({"error": f"Scrip '{scrip_to_delete}' not found in wishlist."}), 404
            
    except Exception as e:
        logging.error(f"Error removing from wishlist: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500
    
# Get watchlist
@portfolio_bp.route('/wishlist', methods=['GET'])
def get_wishlist():
    """Fetches all scrips from the wishlist sheet."""
    try:
        # Check if the 'watchlist_sheet' is connected
        if watchlist_sheet is None:
            return jsonify({"error": "Google Sheets 'Watchlist' not connected."}), 500

        # Fetch all records from the sheet
        records = watchlist_sheet.get_all_records()
        
        return jsonify(records), 200
            
    except Exception as e:
        logging.error(f"Error fetching wishlist: {e}")
        return jsonify({"error": f"An unexpected error occurred while fetching the wishlist: {e}"}), 500

@portfolio_bp.route('/add', methods=['POST'])
def add_stock():
    """Adds a stock to the default portfolio sheet."""
    try:
        # **FIX**: Use portfolio_sheet instead of worksheet
        if portfolio_sheet is None:
            return jsonify({"error": "Google Sheets 'Portfolio' not connected."}), 500

        data = request.get_json()
        required_fields = ['scrip', 'quantity', 'purchasePrice', 'sector']
        if not all(field in data for field in required_fields):
            return jsonify({"error": f"Missing required fields: {required_fields}"}), 400
            
        new_row = [data['scrip'], data['sector'], data['quantity'], data['purchasePrice']]
        
        # **FIX**: Use portfolio_sheet instead of worksheet
        portfolio_sheet.append_row(new_row, value_input_option='USER_ENTERED')
        
        return jsonify({"message": "Stock added successfully."}), 201
        
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500

@portfolio_bp.route('/summary', methods=['GET'])
def get_portfolio_summary():
    """Merges portfolio data with live market prices to provide a full summary."""
    try:
        # **FIX**: Use portfolio_sheet instead of worksheet
        if portfolio_sheet is None:
             return jsonify({"error": "Google Sheets 'Portfolio' not connected."}), 500
        
        # **FIX**: Use portfolio_sheet instead of worksheet
        portfolio_holdings = portfolio_sheet.get_all_records()
        market_data_list = scrape_share_prices()
        save_full_daily_snapshot(market_data_list)
        market_prices = {item['Symbol']: item for item in market_data_list}
        
        # ... (rest of the summary logic is correct)
        total_portfolio_purchase_value = sum(stock.get('quantity', 0) * stock.get('purchasePrice', 0) for stock in portfolio_holdings)
        if total_portfolio_purchase_value == 0:
            total_portfolio_purchase_value = 1 

        summary_list = []
        for stock in portfolio_holdings:
            symbol = stock.get('scrip')
            if not symbol or not stock.get('quantity'):
                continue
            purchase_price = stock.get('purchasePrice', 0)
            quantity = stock.get('quantity', 0)
            sector = stock.get('sector', 'N/A') 
            stock_market_data = market_prices.get(symbol)
            ltp = 0.0
            week_high_low = "N/A"
            if stock_market_data:
                try:
                    ltp = float(stock_market_data.get('LTP', '0').replace(',', ''))
                except (ValueError, AttributeError):
                    ltp = 0.0
                high = stock_market_data.get('52 Weeks High', 'N/A')
                low = stock_market_data.get('52 Weeks Low', 'N/A')
                week_high_low = f"{high} / {low}"
            purchase_value = purchase_price * quantity
            current_value = ltp * quantity if ltp > 0 else 0
            profit_amount = current_value - purchase_value
            if purchase_price > 0 and ltp > 0:
                profit_percentage = (profit_amount / purchase_value) * 100
            else:
                profit_percentage = 0
            weight_percentage = (purchase_value / total_portfolio_purchase_value) * 100
            summary_list.append({
                "Script": symbol, "Sector": sector, "quantity": quantity,
                "purchase price": purchase_price, "LTP": ltp,
                "Current Value": round(current_value, 2),
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