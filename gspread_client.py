# gspread_client.py

import os
import json
import gspread
import logging
from dotenv import load_dotenv

load_dotenv()

# Initialize worksheet to None
worksheet = None

try:
    creds_json_str = os.getenv("GOOGLE_CREDENTIAL")
    if not creds_json_str:
        raise ValueError("GOOGLE_CREDENTIALS environment variable not set.")
    
    creds_dict = json.loads(creds_json_str)
    
    gc = gspread.service_account_from_dict(creds_dict)
    
    spreadsheet = gc.open_by_key(os.getenv("SPREADSHEET_ID"))
    worksheet = spreadsheet.sheet1 # Assign the connected worksheet
    logging.info("Successfully connected to Google Sheets.")

except Exception as e:
    logging.error(f"FATAL: Could not connect to Google Sheets. The application may not function correctly. Details: {e}")