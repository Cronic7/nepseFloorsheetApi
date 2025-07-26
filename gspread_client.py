# gspread_client.py

import os
import json
import gspread
import logging
from dotenv import load_dotenv

load_dotenv()

# Initialize worksheet variables to None
portfolio_sheet = None
turnover_sheet = None
daily_data_sheet = None
watchlist_sheets=None

try:
    creds_json_str = os.getenv("GOOGLE_CREDENTIAL")
    if not creds_json_str:
        raise ValueError("GOOGLE_CREDENTIALS environment variable not set.")
    
    creds_dict = json.loads(creds_json_str)
    
    gc = gspread.service_account_from_dict(creds_dict)
    
    spreadsheet = gc.open_by_key(os.getenv("SPREADSHEET_ID"))
    
    # --- UPDATED SECTION ---
    # Assign the 'Portfolio' sheet (or your primary data sheet)
    # Using spreadsheet.sheet1 assumes it's the first tab. 
    # It's safer to open by name if possible.
    portfolio_sheet = spreadsheet.worksheet("Portfolio") # <-- Best Practice: Use the sheet name

    # Assign the 'Turnover' sheet
    turnover_sheet = spreadsheet.worksheet("Turnover")
    # --- END UPDATE ---
    daily_data_sheet = spreadsheet.worksheet("Market")
    watchlist_sheet = spreadsheet.worksheet("Watchlist")

    logging.info("Successfully connected to Google Sheets and loaded worksheets.")

except gspread.exceptions.WorksheetNotFound as e:
    logging.error(f"FATAL: A required worksheet was not found: {e}")
except Exception as e:
    logging.error(f"FATAL: Could not connect to Google Sheets. Details: {e}")