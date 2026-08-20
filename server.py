# -*- coding: utf-8 -*-
import os
import sys
import json
import sqlite3
import urllib.parse
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import random
import string
import csv
import io

DB_FILE = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
PUBLIC_DIR = os.path.join(os.path.dirname(__file__), 'public')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "zVjp5vlB3ojS0uT")

DELETED_LEADS_FILE = os.path.join(os.path.dirname(__file__), 'deleted_leads.json')

def send_smtp_email_ipv4(smtp_host, smtp_port, smtp_user, smtp_pass, recipient, subject, html_content, attachments=None):
    import socket
    import smtplib
    import base64
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    if attachments:
        for att in attachments:
            name = att.get('name') or 'file'
            b64_content = att.get('content')
            if b64_content:
                try:
                    raw_bytes = base64.b64decode(b64_content)
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(raw_bytes)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{name}"')
                    msg.attach(part)
                except Exception as ex:
                    print("Error attaching file to SMTP:", ex)

    old_getaddrinfo = socket.getaddrinfo

    def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_getaddrinfo

    port_num = int(smtp_port) if str(smtp_port).strip().isdigit() else 587
    ports_to_try = [port_num]
    if port_num == 465 and 587 not in ports_to_try:
        ports_to_try.append(587)
    elif port_num == 587 and 465 not in ports_to_try:
        ports_to_try.append(465)

    last_error = None
    try:
        for p in ports_to_try:
            try:
                if p == 465:
                    server = smtplib.SMTP_SSL(smtp_host, p, timeout=10)
                else:
                    server = smtplib.SMTP(smtp_host, p, timeout=10)
                    server.starttls()

                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [recipient], msg.as_string())
                server.quit()
                return
            except Exception as err:
                last_error = err
                continue

        if last_error:
            raise last_error
    finally:
        socket.getaddrinfo = old_getaddrinfo

def send_email_via_api(api_key, sender_email, recipient, subject, html_content, attachments=None):
    import urllib.request
    import json

    api_key = api_key.strip()
    sender = sender_email.strip() if sender_email else 'cloud_east@itstep.org'

    if api_key.startswith('re_'):
        url = 'https://api.resend.com/emails'
        from_addr = sender if ('@' in sender and not sender.endswith('@gmail.com') and not sender.endswith('@ukr.net')) else 'onboarding@resend.dev'
        payload = {
            "from": f"Академія ITSTEP <{from_addr}>",
            "to": [recipient],
            "subject": subject,
            "html": html_content
        }
        if attachments:
            payload["attachments"] = [
                {"filename": att["name"], "content": att["content"]}
                for att in attachments if att.get("content")
            ]

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            method='POST'
        )
    else:
        url = 'https://api.brevo.com/v3/smtp/email'
        payload = {
            "sender": {"name": "Академія ITSTEP", "email": sender},
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html_content
        }
        if attachments:
            payload["attachment"] = [
                {"name": att["name"], "content": att["content"]}
                for att in attachments if att.get("content")
            ]

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'accept': 'application/json',
                'api-key': api_key,
                'content-type': 'application/json'
            },
            method='POST'
        )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as he:
        try:
            err_json = json.loads(he.read().decode('utf-8'))
            msg = err_json.get('message') or err_json.get('code') or str(err_json)
            raise Exception(msg)
        except Exception as parse_e:
            if str(parse_e) != str(he):
                raise Exception(str(parse_e))
            raise he

def get_guide_pdf_base64():
    import base64
    # 1. Check if custom parent_guide was uploaded via Admin Panel
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT filename FROM files WHERE file_type = ?', ('parent_guide',))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            uploaded_path = os.path.join(UPLOADS_DIR, row[0])
            if os.path.exists(uploaded_path):
                with open(uploaded_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print("Error checking files DB for guide:", e)

    # 2. Check fallback file locations
    possible_paths = [
        os.path.join(UPLOADS_DIR, 'parent_guide.pdf'),
        os.path.join(PUBLIC_DIR, 'assets', 'default_guide.pdf')
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                with open(p, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')
            except Exception as e:
                print("Error reading guide PDF:", e)
    return None

def get_deleted_records():
    if os.path.exists(DELETED_LEADS_FILE):
        try:
            with open(DELETED_LEADS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print("Error reading deleted_leads.json:", e)
    return {'ids': [], 'tickets': []}

def save_deleted_lead_record(lead_id, ticket_number=None):
    records = get_deleted_records()
    if 'ids' not in records:
        records['ids'] = []
    if 'tickets' not in records:
        records['tickets'] = []

    if lead_id:
        try:
            lid_int = int(lead_id)
            if lid_int not in records['ids']:
                records['ids'].append(lid_int)
        except (ValueError, TypeError):
            pass

    if ticket_number and ticket_number not in records['tickets']:
        records['tickets'].append(ticket_number)

    try:
        with open(DELETED_LEADS_FILE, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Error saving deleted_leads.json:", e)

    purge_deleted_leads_from_db(records)

def purge_deleted_leads_from_db(records=None):
    if records is None:
        records = get_deleted_records()
    ids = records.get('ids', [])
    tickets = records.get('tickets', [])

    if not ids and not tickets:
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        for lid in ids:
            c.execute('DELETE FROM leads WHERE id = ?', (lid,))
        for tnum in tickets:
            c.execute('DELETE FROM leads WHERE ticket_number = ?', (tnum,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Error purging deleted leads from DB:", e)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            child_name TEXT,
            child_age INTEGER,
            city TEXT,
            parent_name TEXT,
            parent_phone TEXT,
            parent_email TEXT,
            ticket_number TEXT UNIQUE,
            result_profile TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            file_type TEXT PRIMARY KEY,
            filename TEXT,
            original_name TEXT,
            uploaded_at TEXT
        )
    ''')
    
    defaults = {
        'branch_name': 'Cloud east',
        'youtube_url': 'https://youtube.com/shorts/2Uz2AQn4Z-U?feature=share',
        'phone': '+380 96 23 11 331',
        'email': 'cloud_east@itstep.org',
        'address': 'UKRAINE',
        'telegram': '@StepCloudEast'
    }
    for k, v in defaults.items():
        c.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))
    conn.commit()
    conn.close()

    purge_deleted_leads_from_db()

init_db()

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'settings.json')

DEFAULT_SETTINGS = {
    'branch_name': 'Cloud east',
    'youtube_url': 'https://youtube.com/shorts/2Uz2AQn4Z-U?feature=share',
    'phone': '+380 96 23 11 331',
    'email': 'cloud_east@itstep.org',
    'address': 'UKRAINE',
    'telegram': '@StepCloudEast',
    'email_api_key': '',
    'smtp_host': '',
    'smtp_port': '587',
    'smtp_user': '',
    'smtp_pass': ''
}

def get_settings():
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                for k, v in saved.items():
                    if v:
                        settings[k] = str(v)
        except Exception as e:
            print("Error reading settings.json:", e)

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT key, value FROM settings WHERE value IS NOT NULL AND value != ""')
        rows = c.fetchall()
        conn.close()
        for k, v in rows:
            if v:
                settings[k] = v
    except Exception as e:
        print("Error reading settings DB:", e)

    return settings

def update_settings(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for k, v in data.items():
        c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, str(v)))
    conn.commit()
    conn.close()

    try:
        current = get_settings()
        current.update(data)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Error writing settings.json:", e)

def generate_ticket():
    digits = ''.join(random.choices(string.digits, k=6))
    return f"ITS-{digits}"

class QuizRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message, status=400):
        self._send_json({'error': message}, status=status)

    def _send_file(self, filepath, content_type=None, filename=None):
        if not os.path.exists(filepath):
            self.send_error(404, "File not found")
            return
        if content_type is None:
            content_type, _ = mimetypes.guess_type(filepath)
            content_type = content_type or 'application/octet-stream'
        with open(filepath, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        if filename:
            encoded_fn = urllib.parse.quote(filename)
            self.send_header('Content-Disposition', f'attachment; filename="{encoded_fn}"; filename*=UTF-8\'\'{encoded_fn}')
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == '/api/settings':
            self._send_json(get_settings())
            return

        if path == '/api/admin/leads':
            auth_header = self.headers.get('Authorization', '')
            if auth_header != f'Bearer {ADMIN_PASSWORD}' and query.get('pwd', [''])[0] != ADMIN_PASSWORD:
                self._send_error('Unauthorized', 401)
                return
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('SELECT id, created_at, child_name, child_age, city, parent_name, parent_phone, parent_email, ticket_number, result_profile FROM leads ORDER BY id DESC')
            rows = c.fetchall()
            conn.close()
            leads = [{
                'id': r[0],
                'created_at': r[1],
                'child_name': r[2],
                'child_age': r[3],
                'city': r[4],
                'parent_name': r[5],
                'parent_phone': r[6],
                'parent_email': r[7],
                'ticket_number': r[8],
                'result_profile': r[9]
            } for r in rows]
            self._send_json({'leads': leads})
            return

        if path == '/api/admin/leads/export':
            pwd = query.get('pwd', [''])[0]
            if pwd != ADMIN_PASSWORD:
                self.send_error(401, 'Unauthorized')
                return
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('SELECT id, created_at, child_name, child_age, city, parent_name, parent_phone, parent_email, ticket_number, result_profile FROM leads ORDER BY id DESC')
            rows = c.fetchall()
            conn.close()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Дата створення', 'Ім\'я дитини', 'Вік дитини', 'Місто', 'Ім\'я батьків', 'Телефон батьків', 'Email батьків', 'Номер квитка', 'IT-Профіль'])
            for r in rows:
                writer.writerow(r)
            
            csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="leads_itstep.csv"')
            self.send_header('Content-Length', str(len(csv_bytes)))
            self.end_headers()
            self.wfile.write(csv_bytes)
            return

        if path == '/api/files/download':
            file_type = query.get('type', [''])[0]
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('SELECT filename, original_name FROM files WHERE file_type = ?', (file_type,))
            row = c.fetchone()
            conn.close()
            if row:
                filepath = os.path.join(UPLOADS_DIR, row[0])
                if os.path.exists(filepath):
                    self._send_file(filepath, filename=row[1])
                    return
            
            if file_type == 'parent_guide':
                filepath = os.path.join(PUBLIC_DIR, 'assets', 'default_guide.pdf')
                if os.path.exists(filepath):
                    self._send_file(filepath, filename='IT_Guide_For_Parents.pdf')
                    return
            self._send_error("Файл ще не завантажено в адмінпанелі", 404)
            return

        if path == '/api/admin/files':
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('SELECT file_type, filename, original_name, uploaded_at FROM files')
            rows = c.fetchall()
            conn.close()
            files_dict = {r[0]: {'filename': r[1], 'original_name': r[2], 'uploaded_at': r[3]} for r in rows}
            self._send_json(files_dict)
            return

        req_path = path.lstrip('/')
        if not req_path:
            req_path = 'index.html'
        filepath = os.path.join(PUBLIC_DIR, req_path)
        if os.path.exists(filepath) and os.path.isfile(filepath):
            self._send_file(filepath)
        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        if path == '/api/admin/login':
            try:
                data = json.loads(body.decode('utf-8'))
                if data.get('password') == ADMIN_PASSWORD:
                    self._send_json({'success': True, 'token': ADMIN_PASSWORD})
                else:
                    self._send_error('Невірний пароль адміністратора', 401)
            except Exception as e:
                self._send_error(str(e), 400)
            return

        if path == '/api/admin/settings':
            auth_header = self.headers.get('Authorization', '')
            if auth_header != f'Bearer {ADMIN_PASSWORD}':
                self._send_error('Unauthorized', 401)
                return
            try:
                data = json.loads(body.decode('utf-8'))
                update_settings(data)
                self._send_json({'success': True, 'settings': get_settings()})
            except Exception as e:
                self._send_error(str(e), 400)
            return

        if path == '/api/admin/leads/delete' or (path == '/api/admin/leads' and self.command == 'DELETE'):
            auth_header = self.headers.get('Authorization', '')
            if auth_header != f'Bearer {ADMIN_PASSWORD}':
                self._send_error('Unauthorized', 401)
                return
            try:
                lead_id = None
                if body:
                    data = json.loads(body.decode('utf-8'))
                    lead_id = data.get('id')
                if not lead_id:
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    if 'id' in query_params:
                        lead_id = query_params['id'][0]

                if not lead_id:
                    self._send_error('Не вказано ID запису для видалення', 400)
                    return

                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute('SELECT ticket_number FROM leads WHERE id = ?', (lead_id,))
                row = c.fetchone()
                ticket_number = row[0] if row else None

                c.execute('DELETE FROM leads WHERE id = ?', (lead_id,))
                if ticket_number:
                    c.execute('DELETE FROM leads WHERE ticket_number = ?', (ticket_number,))
                conn.commit()
                conn.close()

                save_deleted_lead_record(lead_id, ticket_number)

                self._send_json({'success': True, 'deleted_id': lead_id})
            except Exception as e:
                self._send_error(str(e), 400)
            return

        if path == '/api/register':
            try:
                data = json.loads(body.decode('utf-8'))
                child_name = data.get('child_name', '').strip()
                child_age = int(data.get('child_age', 0))
                city = data.get('city', '').strip()
                parent_name = data.get('parent_name', '').strip()
                parent_phone = data.get('parent_phone', '').strip()
                parent_email = data.get('parent_email', '').strip()

                if not (child_name and child_age and city and parent_name and parent_phone and parent_email):
                    self._send_error('Будь ласка, заповніть всі поля форми', 400)
                    return

                ticket_number = generate_ticket()
                created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute('''
                    INSERT INTO leads (created_at, child_name, child_age, city, parent_name, parent_phone, parent_email, ticket_number, result_profile)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (created_at, child_name, child_age, city, parent_name, parent_phone, parent_email, ticket_number, 'Очікує проходження квізу'))
                conn.commit()
                lead_id = c.lastrowid
                conn.close()

                self._send_json({
                    'success': True,
                    'lead_id': lead_id,
                    'ticket_number': ticket_number,
                    'child_name': child_name,
                    'parent_email': parent_email
                })
            except Exception as e:
                self._send_error(f"Помилка реєстрації: {str(e)}", 400)
            return

        if path == '/api/send-results-email':
            try:
                data = json.loads(body.decode('utf-8'))
                email = data.get('email', '').strip()
                child_name = data.get('child_name', '').strip()
                ticket_number = data.get('ticket_number', '').strip()
                result_profile = data.get('result_profile', '').strip()

                if email:
                    current_s = get_settings()
                    email_api_key = (data.get('email_api_key') or os.environ.get('EMAIL_API_KEY') or current_s.get('email_api_key') or '').strip()
                    smtp_host = (os.environ.get('SMTP_HOST') or current_s.get('smtp_host') or '').strip()
                    smtp_port_raw = str(os.environ.get('SMTP_PORT') or current_s.get('smtp_port') or '587').strip()
                    smtp_port = int(smtp_port_raw) if smtp_port_raw.isdigit() else 587
                    smtp_user = (os.environ.get('SMTP_USER') or current_s.get('smtp_user') or '').strip()
                    smtp_pass = (os.environ.get('SMTP_PASSWORD') or current_s.get('smtp_pass') or '').strip()

                    email_sent = False
                    email_error = None

                    cert_b64 = data.get('cert_base64')
                    guide_b64 = get_guide_pdf_base64()

                    attachments = []
                    if cert_b64:
                        attachments.append({
                            "name": f"Certificate_{(child_name or 'Participant').replace(' ', '_')}.png",
                            "content": cert_b64
                        })
                    if guide_b64:
                        attachments.append({
                            "name": "IT_Guide_For_Parents.pdf",
                            "content": guide_b64
                        })

                    subject = f"Сертифікат та IT-гайд для {child_name} | Академія ITSTEP"
                    html_content = f"""
                    <html>
                      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                          <h2 style="color: #0284c7;">Академія ITSTEP</h2>
                          <p>Вітаємо!</p>
                          <p>Дякуємо за участь у квізі <strong>«Мої літні канікули — це баг чи фіча?»</strong>.</p>
                          <p>Учасник: <strong>{child_name}</strong><br>
                          Визначений IT-профіль: <strong>{result_profile}</strong><br>
                          Унікальний номер учасника розіграшу: <strong>{ticket_number}</strong></p>
                          <p>📎 <strong>Ваші вкладені матеріали:</strong><br>
                          1. Офіційний персональний сертифікат учасника (PNG)<br>
                          2. IT-гайд для батьків (PDF)</p>
                          <p style="font-size: 0.9em; color: #666; margin-top: 20px;">З повагою,<br>Команда Академії ITSTEP</p>
                        </div>
                      </body>
                    </html>
                    """

                    if email_api_key:
                        try:
                            send_email_via_api(email_api_key, smtp_user, email, subject, html_content, attachments=attachments)
                            email_sent = True
                            print(f"SUCCESS: Email sent via API to {email} with {len(attachments)} attachments")
                        except Exception as ae:
                            email_error = f"API Error: {ae}"
                            print("API Send Error:", ae)
                    elif smtp_host and smtp_user and smtp_pass:
                        try:
                            send_smtp_email_ipv4(smtp_host, smtp_port, smtp_user, smtp_pass, email, subject, html_content, attachments=attachments)
                            email_sent = True
                            print(f"SUCCESS: Email sent via SMTP to {email} with {len(attachments)} attachments")
                        except Exception as se:
                            email_error = f"SMTP Error: {se}"
                            print("SMTP send error:", se)
                    else:
                        email_error = "Пошта не налаштована (Вкажіть Brevo/Resend API Key або SMTP)"

                self._send_json({
                    'success': True, 
                    'email': email, 
                    'email_sent': email_sent, 
                    'error': email_error
                })
            except Exception as e:
                self._send_error(str(e), 400)
            return

        if path == '/api/admin/test-email':
            auth_header = self.headers.get('Authorization', '')
            if auth_header != f'Bearer {ADMIN_PASSWORD}':
                self._send_error('Unauthorized', 401)
                return
            try:
                data = json.loads(body.decode('utf-8'))
                current_s = get_settings()
                email_api_key = (data.get('email_api_key') or os.environ.get('EMAIL_API_KEY') or current_s.get('email_api_key') or '').strip()
                smtp_host = (data.get('smtp_host') or os.environ.get('SMTP_HOST') or current_s.get('smtp_host') or '').strip()
                smtp_port_raw = str(data.get('smtp_port') or os.environ.get('SMTP_PORT') or current_s.get('smtp_port') or '587').strip()
                smtp_port = int(smtp_port_raw) if smtp_port_raw.isdigit() else 587
                smtp_user = (data.get('smtp_user') or os.environ.get('SMTP_USER') or current_s.get('smtp_user') or '').strip()
                smtp_pass = (data.get('smtp_pass') or os.environ.get('SMTP_PASSWORD') or current_s.get('smtp_pass') or '').strip()

                if not (email_api_key or (smtp_host and smtp_user and smtp_pass)):
                    self._send_json({'success': False, 'error': 'Будь ласка, заповніть Brevo/Resend API Key АБО SMTP налаштування в адмінці'})
                    return

                subject = "🧪 Тестовий лист від сайту Академії ITSTEP"
                html_content = """
                <html>
                  <body style="font-family: Arial, sans-serif; color: #333;">
                    <h3 style="color: #0284c7;">Вітаємо! Налаштування пошти працюють ідеально! ✅</h3>
                    <p>Цей тестовий лист підтверджує, що ваш поштовий сервер успішно підключено та відправка функціонує бездоганно.</p>
                  </body>
                </html>
                """

                target_recipient = smtp_user if smtp_user else 'test@example.com'
                if email_api_key:
                    send_email_via_api(email_api_key, smtp_user, target_recipient, subject, html_content)
                else:
                    send_smtp_email_ipv4(smtp_host, smtp_port, smtp_user, smtp_pass, target_recipient, subject, html_content)

                self._send_json({'success': True, 'email': target_recipient})
            except Exception as e:
                self._send_json({'success': False, 'error': str(e)})
            return

        if path == '/api/update-result':
            try:
                data = json.loads(body.decode('utf-8'))
                lead_id = data.get('lead_id')
                result_profile = data.get('result_profile', '').strip()

                if lead_id and result_profile:
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute('UPDATE leads SET result_profile = ? WHERE id = ?', (result_profile, lead_id))
                    conn.commit()
                    conn.close()
                self._send_json({'success': True})
            except Exception as e:
                self._send_error(str(e), 400)
            return

        if path == '/api/admin/upload':
            auth_header = self.headers.get('Authorization', '')
            if auth_header != f'Bearer {ADMIN_PASSWORD}':
                self._send_error('Unauthorized', 401)
                return

            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self._send_error('Invalid content type', 400)
                return

            boundary = content_type.split('boundary=')[1].encode()
            parts = body.split(b'--' + boundary)
            
            file_type = None
            file_data = None
            original_filename = "file.pdf"

            for part in parts:
                if b'name="file_type"' in part:
                    file_type = part.split(b'\r\n\r\n')[1].split(b'\r\n')[0].decode('utf-8').strip()
                elif b'name="file"' in part:
                    headers_part = part.split(b'\r\n\r\n')[0].decode('utf-8', errors='ignore')
                    if 'filename="' in headers_part:
                        original_filename = headers_part.split('filename="')[1].split('"')[0]
                    file_data = part.split(b'\r\n\r\n')[1].rstrip(b'\r\n--')

            if file_type and file_data:
                filename = f"{file_type}_{int(datetime.now().timestamp())}.pdf"
                filepath = os.path.join(UPLOADS_DIR, filename)
                with open(filepath, 'wb') as f:
                    f.write(file_data)

                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                uploaded_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                c.execute('INSERT OR REPLACE INTO files (file_type, filename, original_name, uploaded_at) VALUES (?, ?, ?, ?)',
                          (file_type, filename, original_filename, uploaded_at))
                conn.commit()
                conn.close()

                self._send_json({'success': True, 'filename': filename, 'original_name': original_filename})
            else:
                self._send_error('Помилка завантаження файла', 400)
            return

    def do_DELETE(self):
        self.do_POST()

handler = QuizRequestHandler
app = QuizRequestHandler

def run(port=8080):
    port = int(os.environ.get('PORT', port))
    server_address = ('', port)
    httpd = HTTPServer(server_address, QuizRequestHandler)
    print(f"Сервер воронки продажів ITSTEP запущено на порту {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
