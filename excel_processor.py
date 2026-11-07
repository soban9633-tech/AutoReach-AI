import os
import re
from datetime import datetime
import pandas as pd
import phonenumbers
from phonenumbers import geocoder

COUNTRY_CODE_MAP = {
    'PK': '92',
    'AE': '971',
    'SA': '966',
    'US': '1',
    'GB': '44',
    'IN': '91',
    'CA': '1',
    'AU': '61',
    'DE': '49',
    'TR': '90',
    'OM': '968',
    'QA': '974',
    'KW': '965',
    'BH': '973'
}

def clean_phone_number(raw_phone, default_country="AUTO"):
    """
    Cleans and formats phone numbers from ANY country in the world:
    - Supports international format: +1..., +44..., +971..., +966..., +92..., +91...
    - Supports 00 prefix: 00971... -> 971...
    - Supports local formats: e.g. 03xx (Pakistan) -> 923xx, 05xx (UAE) -> 9715xx
    - Returns: (cleaned_digits, country_name)
    """
    if raw_phone is None or pd.isna(raw_phone):
        return None, None
    
    s = str(raw_phone).strip()
    if s.endswith('.0'):
        s = s[:-2]
    
    # Replace leading '00' with '+'
    if s.startswith('00'):
        s = '+' + s[2:]

    # Remove all characters except digits and leading '+'
    digits_only = re.sub(r'[^\d]', '', s)
    if not digits_only:
        return None, None

    default_region = default_country if default_country != "AUTO" else "PK"

    try:
        # If starts with '+', parse with international rule
        if s.startswith('+'):
            parsed = phonenumbers.parse(s, None)
        else:
            # If already starts with known international country code without '+'
            # Check if parsing with '+' works first for long numbers (> 10 digits and not starting with 0)
            if len(digits_only) > 10 and not digits_only.startswith('0'):
                try:
                    test_parsed = phonenumbers.parse('+' + digits_only, None)
                    if phonenumbers.is_valid_number(test_parsed):
                        country = geocoder.country_name_for_number(test_parsed, 'en') or 'International'
                        return f"{test_parsed.country_code}{test_parsed.national_number}", country
                except Exception:
                    pass

            # Otherwise parse with default region (e.g. PK, AE, US, etc.)
            parsed = phonenumbers.parse(digits_only, default_region)

        if phonenumbers.is_possible_number(parsed):
            formatted = f"{parsed.country_code}{parsed.national_number}"
            country = geocoder.country_name_for_number(parsed, 'en') or 'International'
            return formatted, country

    except Exception:
        pass

    # Fallback: If digits >= 7, return digits
    if len(digits_only) >= 7:
        # If local 03xx Pakistan fallback
        if digits_only.startswith('03') and len(digits_only) == 11:
            return '92' + digits_only[1:], 'Pakistan'
        return digits_only, 'International'

    return None, None

def read_contacts_file(filepath, default_country="AUTO"):
    """
    Reads .xlsx, .xls, or .csv and returns structured dictionary:
    - columns: list of headers
    - rows: list of dicts (row data)
    - detected_columns: suggested mappings for phone, email, name
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.xlsx', '.xls']:
        df = pd.read_excel(filepath, dtype=str)
    elif ext == '.csv':
        df = pd.read_csv(filepath, dtype=str)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Please upload .xlsx, .xls, or .csv")

    # Replace NaN with empty string
    df = df.fillna('')
    columns = [str(c).strip() for c in df.columns]
    df.columns = columns

    detected = {
        'phone': None,
        'email': None,
        'name': None
    }

    phone_patterns = [r'phone', r'mobile', r'cell', r'whatsapp', r'contact', r'number', r'rabta', r'num', r'tel']
    email_patterns = [r'email', r'e-mail', r'mail']
    name_patterns = [r'name', r'customer', r'client', r'full.*name', r'first.*name', r'naam', r'person']

    for col in columns:
        col_lower = col.lower()
        if not detected['phone'] and any(re.search(p, col_lower) for p in phone_patterns):
            detected['phone'] = col
        if not detected['email'] and any(re.search(p, col_lower) for p in email_patterns):
            detected['email'] = col
        if not detected['name'] and any(re.search(p, col_lower) for p in name_patterns):
            detected['name'] = col

    # Fallbacks if not detected
    if not detected['phone'] and len(columns) > 0:
        detected['phone'] = columns[0]
    if not detected['email'] and len(columns) > 1:
        detected['email'] = columns[1]
    if not detected['name'] and len(columns) > 2:
        detected['name'] = columns[2]

    rows = df.to_dict(orient='records')
    return {
        'columns': columns,
        'total_rows': len(rows),
        'preview': rows[:5],
        'rows': rows,
        'detected_columns': detected
    }

def format_message(template, contact_row):
    """
    Replaces placeholders like {Name}, {Company}, {Email}, etc.
    Case-insensitive matching for keys.
    """
    if not template:
        return ""
    
    text = template
    # Replace all columns
    for key, val in contact_row.items():
        pattern = re.compile(re.escape('{' + key + '}'), re.IGNORECASE)
        text = pattern.sub(str(val) if val is not None else '', text)
    
    return text

def save_campaign_report(rows, results, output_filepath):
    """
    Saves campaign execution results to an Excel report.
    """
    df = pd.DataFrame(rows)
    wa_status = []
    wa_notes = []
    wa_country = []
    email_status = []
    email_notes = []
    timestamps = []

    for i in range(len(rows)):
        res = results.get(i, {})
        wa_status.append(res.get('whatsapp_status', 'Skipped'))
        wa_notes.append(res.get('whatsapp_note', ''))
        wa_country.append(res.get('country', 'Unknown'))
        email_status.append(res.get('email_status', 'Skipped'))
        email_notes.append(res.get('email_note', ''))
        timestamps.append(res.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    df['Country'] = wa_country
    df['WhatsApp_Status'] = wa_status
    df['WhatsApp_Details'] = wa_notes
    df['Email_Status'] = email_status
    df['Email_Details'] = email_notes
    df['Processed_At'] = timestamps

    df.to_excel(output_filepath, index=False)
    return output_filepath
