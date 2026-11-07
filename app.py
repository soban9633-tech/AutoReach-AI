import os
import time
import random
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename

import excel_processor
import email_bot
from whatsapp_bot import WhatsAppBot

app = Flask(__name__)

is_vercel = bool(os.environ.get('VERCEL'))
if is_vercel:
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
    app.config['REPORTS_FOLDER'] = '/tmp/reports'
else:
    app.config['UPLOAD_FOLDER'] = os.path.abspath('./uploads')
    app.config['REPORTS_FOLDER'] = os.path.abspath('./reports')

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORTS_FOLDER'], exist_ok=True)

# Global State
whatsapp_instance = None
campaign_state = {
    'running': False,
    'stopped': False,
    'total': 0,
    'current_index': 0,
    'current_name': '',
    'sent_count': 0,
    'failed_count': 0,
    'logs': [],
    'completed': False,
    'report_path': None
}

loaded_dataset = {
    'filename': None,
    'columns': [],
    'rows': [],
    'detected_columns': {},
    'total_rows': 0
}

def add_log(message, level="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {"time": timestamp, "message": message, "level": level}
    campaign_state['logs'].append(entry)
    # Keep last 200 logs
    if len(campaign_state['logs']) > 200:
        campaign_state['logs'].pop(0)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{int(time.time())}_{filename}")
    file.save(filepath)

    try:
        data = excel_processor.read_contacts_file(filepath)
        loaded_dataset['filename'] = filename
        loaded_dataset['filepath'] = filepath
        loaded_dataset['columns'] = data['columns']
        loaded_dataset['rows'] = data['rows']
        loaded_dataset['detected_columns'] = data['detected_columns']
        loaded_dataset['total_rows'] = data['total_rows']

        return jsonify({
            'success': True,
            'filename': filename,
            'columns': data['columns'],
            'total_rows': data['total_rows'],
            'preview': data['preview'],
            'detected': data['detected_columns']
        })
    except Exception as e:
        return jsonify({'error': f"Failed to parse file: {str(e)}"}), 500

@app.route('/api/load-sample', methods=['GET'])
def load_sample():
    sample_path = os.path.abspath('./sample_contacts.csv')
    if not os.path.exists(sample_path):
        return jsonify({'error': 'Sample file not found'}), 404
    try:
        data = excel_processor.read_contacts_file(sample_path)
        loaded_dataset['filename'] = 'sample_contacts.csv'
        loaded_dataset['filepath'] = sample_path
        loaded_dataset['columns'] = data['columns']
        loaded_dataset['rows'] = data['rows']
        loaded_dataset['detected_columns'] = data['detected_columns']
        loaded_dataset['total_rows'] = data['total_rows']

        return jsonify({
            'success': True,
            'filename': 'sample_contacts.csv',
            'columns': data['columns'],
            'total_rows': data['total_rows'],
            'preview': data['preview'],
            'detected': data['detected_columns']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/whatsapp/launch', methods=['POST'])
def launch_whatsapp():
    global whatsapp_instance
    try:
        if whatsapp_instance is None:
            whatsapp_instance = WhatsAppBot()
        whatsapp_instance.start_browser()
        is_ready = whatsapp_instance.is_logged_in()
        return jsonify({
            'success': True, 
            'logged_in': is_ready,
            'message': 'WhatsApp Web browser opened. Please scan the QR code if prompted.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/whatsapp/status', methods=['GET'])
def check_whatsapp_status():
    global whatsapp_instance
    if not whatsapp_instance or not whatsapp_instance.driver:
        return jsonify({'running': False, 'logged_in': False})
    
    logged_in = whatsapp_instance.is_logged_in()
    return jsonify({'running': True, 'logged_in': logged_in})

@app.route('/api/test-email', methods=['POST'])
def test_email():
    payload = request.get_json() or {}
    provider = payload.get('provider', 'gmail')
    sender_email = payload.get('sender_email', '')
    password = payload.get('password', '')
    custom_host = payload.get('custom_host', '')
    custom_port = payload.get('custom_port', 587)
    use_ssl = payload.get('use_ssl', False)

    if not sender_email or not password:
        return jsonify({'success': False, 'message': 'Email and Password are required'}), 400

    success, msg = email_bot.test_smtp_connection(
        provider, sender_email, password, custom_host, custom_port, use_ssl
    )
    return jsonify({'success': success, 'message': msg})

def campaign_worker(options):
    global campaign_state, whatsapp_instance
    rows = loaded_dataset['rows']
    total = len(rows)
    campaign_state['running'] = True
    campaign_state['stopped'] = False
    campaign_state['total'] = total
    campaign_state['current_index'] = 0
    campaign_state['sent_count'] = 0
    campaign_state['failed_count'] = 0
    campaign_state['completed'] = False
    campaign_state['logs'] = []
    
    channels = options.get('channels', [])
    col_map = options.get('column_mapping', {})
    wa_template = options.get('whatsapp_template', '')
    email_cfg = options.get('email_config', {})
    min_delay = int(options.get('min_delay', 6))
    max_delay = int(options.get('max_delay', 12))
    default_country = options.get('default_country', 'AUTO')

    send_wa = 'whatsapp' in channels
    send_em = 'email' in channels

    phone_col = col_map.get('phone')
    email_col = col_map.get('email')
    name_col = col_map.get('name')

    results = {}

    add_log(f"Campaign started for {total} contacts (All Countries Supported).", "info")

    if send_wa:
        if whatsapp_instance is None:
            whatsapp_instance = WhatsAppBot()
        if not whatsapp_instance.driver:
            add_log("Starting Chrome for WhatsApp...", "info")
            whatsapp_instance.start_browser()

        add_log("Checking WhatsApp Web login status...", "info")
        if not whatsapp_instance.is_logged_in():
            add_log("Waiting up to 60s for WhatsApp QR login...", "warning")
            ready = whatsapp_instance.wait_for_login(max_wait_seconds=60)
            if not ready:
                add_log("WhatsApp login timed out. Aborting WhatsApp sending.", "error")
                send_wa = False

    for idx, contact in enumerate(rows):
        if campaign_state['stopped']:
            add_log("Campaign was paused/stopped by user.", "warning")
            break

        campaign_state['current_index'] = idx + 1
        name = contact.get(name_col, f"Contact #{idx+1}") if name_col else f"Contact #{idx+1}"
        campaign_state['current_name'] = str(name)
        
        row_res = {'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        contact_success = True

        # 1. WhatsApp Delivery
        if send_wa:
            raw_phone = contact.get(phone_col)
            cleaned_phone, country_name = excel_processor.clean_phone_number(raw_phone, default_country)
            row_res['country'] = country_name or 'Unknown'
            if not cleaned_phone:
                row_res['whatsapp_status'] = 'Failed'
                row_res['whatsapp_note'] = f"Invalid phone: {raw_phone}"
                add_log(f"[{name}] WhatsApp Skipped: Invalid phone '{raw_phone}'", "error")
                contact_success = False
            else:
                wa_msg = excel_processor.format_message(wa_template, contact)
                add_log(f"[{name}] Sending WhatsApp to +{cleaned_phone} [{country_name}]...", "info")
                ok, note = whatsapp_instance.send_message(cleaned_phone, wa_msg)
                if ok:
                    row_res['whatsapp_status'] = 'Sent'
                    row_res['whatsapp_note'] = note
                    add_log(f"[{name}] WhatsApp Sent successfully to {country_name}!", "success")
                else:
                    row_res['whatsapp_status'] = 'Failed'
                    row_res['whatsapp_note'] = note
                    add_log(f"[{name}] WhatsApp Failed: {note}", "error")
                    contact_success = False

        # 2. Email Delivery
        if send_em:
            recipient_email = contact.get(email_col, '').strip()
            if not recipient_email or '@' not in recipient_email:
                row_res['email_status'] = 'Failed'
                row_res['email_note'] = f"Invalid email: {recipient_email}"
                add_log(f"[{name}] Email Skipped: Invalid email '{recipient_email}'", "error")
                contact_success = False
            else:
                subject = excel_processor.format_message(email_cfg.get('subject', ''), contact)
                body = excel_processor.format_message(email_cfg.get('body', ''), contact)
                add_log(f"[{name}] Sending Email to {recipient_email}...", "info")
                
                ok, note = email_bot.send_email(
                    provider=email_cfg.get('provider', 'gmail'),
                    sender_email=email_cfg.get('sender_email'),
                    password=email_cfg.get('password'),
                    recipient_email=recipient_email,
                    subject=subject,
                    body=body,
                    attachments=email_cfg.get('attachments', []),
                    custom_host=email_cfg.get('custom_host'),
                    custom_port=email_cfg.get('custom_port'),
                    use_ssl=email_cfg.get('use_ssl', False),
                    is_html=email_cfg.get('is_html', False)
                )
                if ok:
                    row_res['email_status'] = 'Sent'
                    row_res['email_note'] = note
                    add_log(f"[{name}] Email Sent successfully!", "success")
                else:
                    row_res['email_status'] = 'Failed'
                    row_res['email_note'] = note
                    add_log(f"[{name}] Email Failed: {note}", "error")
                    contact_success = False

        results[idx] = row_res

        if contact_success:
            campaign_state['sent_count'] += 1
        else:
            campaign_state['failed_count'] += 1

        # Safe Anti-ban delay between contacts (if not last contact)
        if idx < total - 1 and not campaign_state['stopped']:
            sleep_sec = random.randint(min_delay, max_delay)
            add_log(f"Waiting {sleep_sec}s safe delay before next contact...", "info")
            time.sleep(sleep_sec)

    # Generate Report
    report_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    report_path = os.path.join(app.config['REPORTS_FOLDER'], report_filename)
    try:
        excel_processor.save_campaign_report(rows, results, report_path)
        campaign_state['report_path'] = report_path
        add_log(f"Campaign completed! Report generated: {report_filename}", "success")
    except Exception as e:
        add_log(f"Could not save report file: {str(e)}", "error")

    campaign_state['running'] = False
    campaign_state['completed'] = True

@app.route('/api/start-campaign', methods=['POST'])
def start_campaign():
    if campaign_state['running']:
        return jsonify({'error': 'A campaign is already running'}), 400

    if not loaded_dataset['rows']:
        return jsonify({'error': 'Please upload an Excel file or load sample data first'}), 400

    options = request.get_json() or {}
    t = threading.Thread(target=campaign_worker, args=(options,), daemon=True)
    t.start()
    return jsonify({'success': True, 'message': 'Campaign started in background'})

@app.route('/api/stop-campaign', methods=['POST'])
def stop_campaign():
    if campaign_state['running']:
        campaign_state['stopped'] = True
        return jsonify({'success': True, 'message': 'Stopping campaign...'})
    return jsonify({'success': False, 'message': 'No campaign currently running'})

@app.route('/api/campaign-status', methods=['GET'])
def get_campaign_status():
    return jsonify({
        'running': campaign_state['running'],
        'total': campaign_state['total'],
        'current_index': campaign_state['current_index'],
        'current_name': campaign_state['current_name'],
        'sent_count': campaign_state['sent_count'],
        'failed_count': campaign_state['failed_count'],
        'completed': campaign_state['completed'],
        'logs': campaign_state['logs'],
        'has_report': campaign_state['report_path'] is not None and os.path.exists(campaign_state['report_path'] or '')
    })

@app.route('/api/download-report', methods=['GET'])
def download_report():
    if campaign_state['report_path'] and os.path.exists(campaign_state['report_path']):
        return send_file(campaign_state['report_path'], as_attachment=True)
    return jsonify({'error': 'No report file available'}), 404

if __name__ == '__main__':
    print("=" * 60)
    print(" Automated Bulk Outreach Tool (Excel -> WhatsApp & Email)")
    print(" Server running at: http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
