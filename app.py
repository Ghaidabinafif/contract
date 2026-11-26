from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file, session
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import qrcode
from datetime import datetime, timedelta
from functools import wraps
import csv
import hashlib
import io
import os
import tempfile
import pytz
import sqlite3  # لإضافة قاعدة البيانات

app = Flask(__name__)

# كلمة المرور تنقرأ من متغير البيئة APP_PASSWORD (يتحط في إعدادات Render)
# وإذا ما انحط، تبقى كلمة المرور القديمة عشان الموقع ما يوقف
PASSWORD = os.environ.get('APP_PASSWORD', 'asmaa')
app.secret_key = os.environ.get('SECRET_KEY') or hashlib.sha256(('afif-contracts:' + PASSWORD).encode()).hexdigest()
app.permanent_session_lifetime = timedelta(days=30)  # يبقى مسجل دخول 30 يوم
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # أقصى حجم لملف الاستيراد

# مكان ملف قاعدة البيانات: في Render يتحط DB_PATH=/var/data/contracts.db (على القرص الدائم) عشان ما تنمسح
DB_FILE = os.environ.get('DB_PATH', 'contracts.db')
if os.path.dirname(DB_FILE):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
SA_TZ = pytz.timezone('Asia/Riyadh')

# أرقام شقق العمارتين
AL_RAWABI_APARTMENTS = [
    "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
    "111", "112", "113", "114", "201", "202A", "202B", "202C", "203", "204", "205", "206",
    "207", "208", "209", "210A", "210B", "210C", "211", "212", "213", "214",
    "301", "302", "303", "304", "305", "306", "307", "308", "309", "310",
    "311", "312", "313", "314", "401A", "401B", "401C", "403", "404", "405", "406",
    "407", "408", "409", "410", "411A", "411B", "411C", "412A", "412B", "412C", "413", "414", "415",
    "416", "417", "418", "501A", "501C", "52B", "53A", "53B", "53C", "54A", "54B",
    "54C", "55B", "511A", "511B", "511C", "57A", "57B", "57C", "58A", "58B", "58C",
    "601", "602", "603", "604", "605", "606", "607", "608", "609", "610", "611", "612",
    "613", "614", "615", "616", "617", "618",
    "Shop", "2", "3", "4", "5", "6"
]

BIN_MALIK_4_APARTMENTS = [
    "1", "2", "3", "4", "5", "6", "7", "8F", "9F",
    "10F", "11", "12", "13", "14", "15", "16", "17",
    "21", "22", "23", "24", "25", "26", "27",
    "31", "32", "33", "34", "35", "36",
    "41", "42", "43", "44", "45", "46",
    "51", "52", "53", "54", "55", "56",
    "61", "62", "63", "64",
    "102", "104", "106", "108", "110", "112",
    "202", "204", "206", "208", "210", "212", "213", "214",
]

BUILDINGS = [
    {"key": "rawabi", "name": "الروابي", "neighborhood": "الروابي", "apartments": AL_RAWABI_APARTMENTS},
    {"key": "banimalik", "name": "بني مالك 4", "neighborhood": "بني مالك 4", "apartments": BIN_MALIK_4_APARTMENTS},
]
NEIGHBORHOODS = [b["neighborhood"] for b in BUILDINGS]

# حالات الشقة: كل حالة لها لون واسم ورمز، عشان ما نعتمد على اللون لحاله
STATUSES = [
    {"key": "active", "label": "فعّال", "icon": "✓"},
    {"key": "due", "label": "عليه مبلغ", "icon": "!"},
    {"key": "not-started", "label": "ما بدأ", "icon": "◷"},
    {"key": "expired", "label": "منتهي", "icon": "✕"},
    {"key": "empty", "label": "ما عليها عقد", "icon": "—"},
    {"key": "unknown", "label": "تواريخ ناقصة", "icon": "?"},
]
STATUS_BY_KEY = {s["key"]: s for s in STATUSES}

# تحويل الأرقام العربية (١٢٣) إلى (123) عشان المطابقة ما تخرب
ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '0123456789' * 2)


def norm(value):
    """توحيد رقم الشقة أو اسم الحي للمقارنة: أرقام إنجليزية، بدون مسافات، حروف كبيرة"""
    return ''.join(str(value or '').translate(ARABIC_DIGITS).split()).upper()


def to_number(value):
    try:
        return float(str(value).translate(ARABIC_DIGITS).replace(',', '').strip()) if value else 0
    except (ValueError, TypeError):
        return 0


def parse_date(value):
    try:
        return datetime.strptime((value or '').strip(), '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


def days_word(n):
    if n == 1:
        return 'يوم واحد'
    if n == 2:
        return 'يومين'
    if 3 <= n <= 10:
        return f'{n} أيام'
    return f'{n} يوم'


@app.template_filter('dmy')
def format_dmy(value):
    d = parse_date(value)
    return d.strftime('%d/%m/%Y') if d else (value or '—')


# إنشاء اتصال بقاعدة البيانات
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# إنشاء جدول العقود إذا لم يكن موجودًا
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            contract_number TEXT,
            nationality TEXT,
            id_number TEXT,
            id_type TEXT,
            job TEXT,
            salary TEXT,
            marital_status TEXT,
            apartment_number TEXT,
            client_name TEXT,
            start_date TEXT,
            end_contract TEXT,
            contract_status TEXT,
            jeddah_neighborhood TEXT,
            transfer TEXT,
            end_date TEXT,
            insurance_paid TEXT,
            rent_fee TEXT,
            maintenance_fee TEXT,
            owner_signature TEXT,
            phone TEXT,
            monthly_rent TEXT,
            months TEXT,
            total TEXT,
            amount_paid TEXT,
            amount_in_words TEXT
        )
    ''')
    # الترقيم يبدأ من 0001 ويكمل بالتسلسل.
    # إذا العداد واقف على 124 من التعديل السابق وما فيه عقود بهالأرقام، يرجع لآخر رقم مستخدم فعلاً
    row = cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = 'contracts'").fetchone()
    max_id = cursor.execute("SELECT COALESCE(MAX(id), 0) FROM contracts").fetchone()[0]
    if row is not None and row[0] == 124 and max_id < 124:
        cursor.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'contracts'", (max_id,))
    conn.commit()
    conn.close()

# استدعاء دالة إنشاء قاعدة البيانات عند بدء تشغيل التطبيق
init_db()


def renumber_restored_once():
    """مرة وحدة بس: العقود المسترجعة من ملفات PDF دخلت بأرقامها القديمة (لين 0124)،
    فنعيد ترقيمها من 0001 بنفس ترتيبها، والعقود الجديدة تكمل بعدها"""
    marker = DB_FILE + '.renumbered'
    if os.path.exists(marker):
        return
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute("SELECT 1 FROM contracts WHERE contract_number = '0124'").fetchone():
            conn.rollback()
            return
        conn.rollback()
        # نسخة احتياطية من قاعدة البيانات قبل أي تعديل
        backup = sqlite3.connect(DB_FILE + '.before-renumber')
        conn.backup(backup)
        backup.close()
        conn.execute('BEGIN IMMEDIATE')
        ids = [r['id'] for r in conn.execute('SELECT id FROM contracts ORDER BY id')]
        conn.execute('UPDATE contracts SET id = id + 1000000')
        for new_id, old_id in enumerate(ids, 1):
            conn.execute('UPDATE contracts SET id = ?, contract_number = ? WHERE id = ?',
                         (new_id, str(new_id).zfill(4), old_id + 1000000))
        conn.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'contracts'", (len(ids),))
        conn.commit()
        with open(marker, 'w') as f:
            f.write(f'renumbered {len(ids)} contracts')
    finally:
        conn.close()


renumber_restored_once()


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get('logged_in'):
            if request.path == '/delete-contract':
                return jsonify({'error': 'انتهى تسجيل الدخول، ادخل كلمة المرور من جديد'}), 401
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapper


def prepare_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

def get_contract_status(start_date, end_contract):
    sa_timezone = pytz.timezone('Asia/Riyadh')
    today = datetime.now(sa_timezone).date()  # <-- هنا التعديل المهم

    try:
        start = datetime.strptime(start_date.strip(), '%Y-%m-%d').date() if start_date else None
    except Exception:
        start = None

    try:
        end = datetime.strptime(end_contract.strip(), '%Y-%m-%d').date() if end_contract else None
    except Exception:
        end = None

    if start and end:
        if today < start:
            return "لم يبدأ"
        elif start <= today <= end:
            return "فعال"
        else:
            return "منتهي"

    elif start and not end:
        return "منتهي" if today > start else "لم يبدأ"

    elif not start and end:
        return "فعال" if today <= end else "منتهي"

    return "غير معروف"


def contract_state(contract):
    """يرجع حالة العقد (اللون والاسم والرمز) مع كم يوم باقي أو فات"""
    if contract is None:
        return dict(STATUS_BY_KEY['empty'], days_text='')

    status = get_contract_status(contract['start_date'], contract['end_contract'])
    if status == "لم يبدأ":
        key = 'not-started'
    elif status == "فعال":
        key = 'due' if to_number(contract['amount_paid']) < to_number(contract['monthly_rent']) else 'active'
    elif status == "منتهي":
        key = 'expired'
    else:
        key = 'unknown'

    today = datetime.now(SA_TZ).date()
    start = parse_date(contract['start_date'])
    end = parse_date(contract['end_contract'])
    days_text = ''
    if key in ('active', 'due') and end:
        left = (end - today).days
        days_text = 'ينتهي اليوم' if left == 0 else f'باقي {days_word(left)}'
    elif key == 'expired' and end:
        days_text = f'انتهى من {days_word((today - end).days)}'
    elif key == 'not-started' and start:
        days_text = f'يبدأ بعد {days_word((start - today).days)}'

    return dict(STATUS_BY_KEY[key], days_text=days_text)


def find_contract(conn, apartment_number, neighborhood):
    """يدور عقد الشقة حتى لو انكتب الرقم بأرقام عربية أو بمسافة زيادة"""
    apt, hood = norm(apartment_number), norm(neighborhood)
    if not apt or not hood:
        return None
    for row in conn.execute('SELECT * FROM contracts ORDER BY id DESC').fetchall():
        if norm(row['apartment_number']) == apt and norm(row['jeddah_neighborhood']) == hood:
            return row
    return None


# بعض الأجهزة تطلب الأيقونة من هالمسارات مباشرة
@app.route('/apple-touch-icon.png')
@app.route('/apple-touch-icon-precomposed.png')
def apple_touch_icon():
    return app.send_static_file('apple-touch-icon.png')


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon-32.png')


@app.route('/contract-status')
def contract_status():
    contract_number = request.args.get('contract_number')
    # البحث عن العقد في قاعدة البيانات
    conn = get_db_connection()
    contract = conn.execute('SELECT * FROM contracts WHERE contract_number = ?', (contract_number,)).fetchone()
    conn.close()

    if contract:
        status = get_contract_status(contract['start_date'], contract['end_contract'])
        return render_template(
            'contract_status.html',
            contract_number=contract['contract_number'],
            start_date=contract['start_date'],
            end_contract=contract['end_contract'],
            status=status
    )

    else:
        return render_template('contract_status.html', error="العقد غير موجود.")

def generate_pdf(data):
    pdf = FPDF(unit='mm', format=(914.4, 685.8))
    pdf.add_page()
    pdf.image('static/contract.png', x=0, y=0, w=914.4, h=685.8)
    pdf.add_font('Amiri', '', 'static/Amiri Bold.ttf', uni=True)

    # تعيين حجم الخط العادي لبقية البيانات
    pdf.set_font('Amiri', '', 35)

    base_url = "https://contract-8duk.onrender.com/contract-status"
    contract_number = data.get('contract-number', '').zfill(4)  # التأكد من أن الرقم مكون من 4 أرقام
    qr_data = f"{base_url}?contract_number={contract_number}"

    qr = qrcode.QRCode(box_size=20, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    # صورة الـQR تتحفظ مؤقت برا مجلد static وتتحول رمادي (صورة الأبيض والأسود كانت تطلع مشوهة في الـPDF)
    fd, qr_image_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    qr.make_image(fill_color="black", back_color="white").get_image().convert('L').save(qr_image_path)

    pdf.image(qr_image_path, x=50, y=530, w=100)
    os.remove(qr_image_path)

    def add_text(x, y, width, height, text, align='C', color=(0, 0, 0)):
        pdf.set_text_color(*color)  # تحديد اللون
        pdf.set_xy(x, y)
        pdf.cell(width, height, prepare_arabic_text(text), border=0, align=align)

    # طباعة رقم العقد باللون الأحمر وزيادة حجم الخط له
    pdf.set_font('Amiri', '', 50)  # زيادة حجم الخط لرقم العقد فقط
    add_text(300, 135, 100, 30, contract_number, color=(255, 0, 0))  # طباعة رقم العقد باللون الأحمر

    # تعيين اللون الأسود لبقية البيانات
    pdf.set_font('Amiri', '', 35)  # إعادة حجم الخط لبقية البيانات إلى الحجم العادي

    # إضافة بقية الحقول بنفس الطريقة
    add_text(650, 132, 120, 30, data.get('date', ''))
    add_text(50, 180, 300, 30, data.get('nationality', ''))
    add_text(50, 215, 300, 30, data.get('id-number', ''))
    add_text(50, 250, 300, 30, data.get('job', ''))
    add_text(450, 250, 350, 30, data.get('end-date', ''))
    add_text(200, 280, 150, 30, data.get('salary', ''))
    add_text(50, 280, 100, 30, data.get('marital-status', ''))
    add_text(50, 350, 300, 30, data.get('jeddah-neighborhood', ''))
    add_text(450, 180, 350, 30, data.get('client-name', ''))
    add_text(450, 215, 350, 30, data.get('id-type', ''))
    add_text(50, 320, 300, 30, data.get('end-contract', ''))
    add_text(50, 385, 300, 30, data.get('apartment-number', ''))
    add_text(50, 420, 300, 30, data.get('insurance-paid', ''))
    add_text(450, 550, 100, 30, data.get('rent-fee', ''))
    add_text(600, 600, 150, 30, data.get('maintenance-fee', ''))
    add_text(620, 450, 150, 30, data.get('amount-paid', ''))
    add_text(120, 450, 450, 30, data.get('amount-in-words', ''))

    # تعيين اللون الأزرق الغامق لتوقيع المالك
    add_text(690, 635, 150, 30, data.get('owner-signature', ''), color=(0, 0, 139))

    # استكمال بقية الحقول
    add_text(450, 280, 350, 30, data.get('phone', ''))
    add_text(450, 320, 350, 30, data.get('start-date', ''))
    add_text(450, 350, 350, 30, data.get('monthly-rent', ''))
    add_text(450, 385, 350, 30, data.get('duration', ''))
    add_text(450, 420, 350, 30, data.get('total', ''))

    apartment_number = (data.get('apartment-number') or 'unknown').strip().replace('/', '-')
    contract_date = data.get('date') or 'unknown'
    # العقد ما يتحفظ في static (كان أي أحد يقدر يحمّله من الرابط)، ينبني مؤقت ويتحذف
    fd, tmp_path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    try:
        pdf.output(tmp_path)
        with open(tmp_path, 'rb') as f:
            pdf_bytes = f.read()
    finally:
        os.remove(tmp_path)
    return pdf_bytes, f"{apartment_number}_{contract_date}.pdf"

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    data = request.form.to_dict()
    # المدة كانت تنطبع في العقد بس ما تنحفظ، الحين تنحفظ في عمود الأشهر
    if not data.get('months'):
        data['months'] = data.get('duration', '')
    contract_status = get_contract_status(data.get('start-date'), data.get('end-contract'))
    data['contract-status'] = contract_status

    apartment_number = data.get('apartment-number')
    jeddah_neighborhood = data.get('jeddah-neighborhood')

    conn = get_db_connection()
    cursor = conn.cursor()

    # التحقق مما إذا كان هناك عقد موجود لنفس رقم الشقة والحي
    existing_contract = find_contract(conn, apartment_number, jeddah_neighborhood)

    if existing_contract:
        # تحديث العقد الحالي بدلاً من إنشاء عقد جديد
        contract_number = existing_contract['contract_number']
        cursor.execute('''
            UPDATE contracts
            SET
                date = ?, nationality = ?, id_number = ?, id_type = ?, job = ?, salary = ?,
                marital_status = ?, client_name = ?, start_date = ?, end_contract = ?,
                contract_status = ?, transfer = ?, end_date = ?, insurance_paid = ?, rent_fee = ?,
                maintenance_fee = ?, owner_signature = ?, phone = ?, monthly_rent = ?, months = ?,
                total = ?, amount_paid = ?, amount_in_words = ?
            WHERE id = ?
        ''', (
            data.get('date'), data.get('nationality'), data.get('id-number'), data.get('id-type'),
            data.get('job'), data.get('salary'), data.get('marital-status'), data.get('client-name'),
            data.get('start-date'), data.get('end-contract'), contract_status, data.get('transfer'),
            data.get('end-date'), data.get('insurance-paid'), data.get('rent-fee'),
            data.get('maintenance-fee'), data.get('owner-signature'), data.get('phone'),
            data.get('monthly-rent'), data.get('months'), data.get('total'),
            data.get('amount-paid'), data.get('amount-in-words'), existing_contract['id']
        ))
    else:
        # إضافة عقد جديد برقم عقد جديد يتم إنشاؤه تلقائيًا باستخدام AUTOINCREMENT
        cursor.execute('''
            INSERT INTO contracts (
                date, nationality, id_number, id_type, job, salary, marital_status,
                apartment_number, client_name, start_date, end_contract, contract_status,
                jeddah_neighborhood, transfer, end_date, insurance_paid, rent_fee,
                maintenance_fee, owner_signature, phone, monthly_rent, months, total,
                amount_paid, amount_in_words
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('date'), data.get('nationality'), data.get('id-number'), data.get('id-type'),
            data.get('job'), data.get('salary'), data.get('marital-status'), data.get('apartment-number'),
            data.get('client-name'), data.get('start-date'), data.get('end-contract'), contract_status,
            jeddah_neighborhood, data.get('transfer'), data.get('end-date'), data.get('insurance-paid'),
            data.get('rent-fee'), data.get('maintenance-fee'), data.get('owner-signature'),
            data.get('phone'), data.get('monthly-rent'), data.get('months'), data.get('total'),
            data.get('amount-paid'), data.get('amount-in-words')
        ))

        # جلب الرقم التسلسلي للعقد الجديد
        contract_number = str(cursor.lastrowid).zfill(4)

        # تحديث رقم العقد في الصف الجديد
        cursor.execute("UPDATE contracts SET contract_number = ? WHERE id = ?", (contract_number, cursor.lastrowid))

    conn.commit()
    conn.close()

    data['contract-number'] = contract_number
    pdf_bytes, filename = generate_pdf(data)
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.route('/view-database', methods=['GET', 'POST'])
@login_required
def view_database():
    query = (request.form.get('search-query') or '').strip() if request.method == 'POST' else ''

    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM contracts ORDER BY id DESC').fetchall()
    conn.close()

    contracts = []
    q = norm(query)
    for row in rows:
        item = dict(row)
        item['st'] = contract_state(row)
        if q:
            haystack = [item.get('client_name'), item.get('apartment_number'), item.get('jeddah_neighborhood'),
                        item.get('phone'), item.get('contract_number'), item['st']['label']]
            if not any(q in norm(v) for v in haystack):
                continue
        contracts.append(item)

    return render_template('view_database.html', contracts=contracts, query=query, total=len(rows))

@app.route('/')
def login():
    if session.get('logged_in'):
        return redirect(url_for('apartments'))
    return render_template('login.html')

@app.route('/check-password', methods=['POST'])
def check_password():
    password = request.form.get('password')
    if password == PASSWORD:
        session.permanent = True
        session['logged_in'] = True
        return redirect(url_for('apartments'))
    else:
        return render_template('login.html', error="كلمة المرور غير صحيحة، جرّب مرة ثانية.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/contract-page')
@login_required
def contract_page():
    # لما ينضغط على شقة من صفحة الشقق: يفتح عقدها، وإذا ما لها عقد يجهز عقد جديد لها
    apartment = (request.args.get('apartment') or '').strip()
    neighborhood = (request.args.get('neighborhood') or '').strip()
    contract, notice = None, None
    prefill = {}
    if apartment and neighborhood:
        conn = get_db_connection()
        row = find_contract(conn, apartment, neighborhood)
        conn.close()
        if row:
            contract = dict(row)
        else:
            prefill = {'apartment_number': apartment, 'jeddah_neighborhood': neighborhood}
            notice = f"ما فيه عقد مسجل لشقة {apartment} في {neighborhood}، عبّ البيانات تحت عشان تسوي عقد جديد."
    return render_template('index.html', c=contract or prefill, contract=contract,
                           notice=notice, neighborhoods=NEIGHBORHOODS)

@app.route('/delete-contract', methods=['POST'])
@login_required
def delete_contract():
    contract_number = request.form.get('contract-number')

    if not contract_number:
        return jsonify({'error': 'يرجى إدخال رقم العقد للحذف'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # التحقق من وجود العقد
    contract = cursor.execute('SELECT * FROM contracts WHERE contract_number = ?', (contract_number,)).fetchone()

    if not contract:
        conn.close()
        return jsonify({'error': 'لم يتم العثور على العقد'}), 404

    # حذف العقد من قاعدة البيانات
    cursor.execute('DELETE FROM contracts WHERE contract_number = ?', (contract_number,))
    conn.commit()
    conn.close()

    return jsonify({'success': 'تم حذف العقد بنجاح!'}), 200


@app.route('/search-contract', methods=['POST'])
@login_required
def search_contract():
    apartment_number = (request.form.get('apartment-number') or '').strip()
    jeddah_neighborhood = (request.form.get('jeddah-neighborhood') or '').strip()

    # التحقق من الإدخالات
    if not apartment_number or not jeddah_neighborhood:
        return render_template('index.html', c={}, contract=None, neighborhoods=NEIGHBORHOODS,
                               error="اكتب رقم الشقة واختر الحي عشان نبحث.")

    return redirect(url_for('contract_page', apartment=apartment_number, neighborhood=jeddah_neighborhood))

# أعمدة النسخة الاحتياطية (نفس أسماء أعمدة قاعدة البيانات)
BACKUP_COLUMNS = [
    'client_name', 'date', 'contract_number', 'nationality', 'id_number', 'id_type', 'job', 'salary',
    'marital_status', 'apartment_number', 'start_date', 'end_contract', 'jeddah_neighborhood', 'transfer',
    'end_date', 'insurance_paid', 'rent_fee', 'maintenance_fee', 'owner_signature', 'phone', 'monthly_rent',
    'months', 'total', 'amount_paid', 'amount_in_words',
]


@app.route('/export')
@login_required
def export_contracts():
    """تحميل كل العقود كملف CSV يفتح في Excel"""
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM contracts ORDER BY id').fetchall()
    conn.close()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(BACKUP_COLUMNS)
    for row in rows:
        writer.writerow([row[c] if row[c] is not None else '' for c in BACKUP_COLUMNS])
    data = ('﻿' + out.getvalue()).encode('utf-8')
    # الوقت والعدد في اسم الملف عشان نسخة جديدة ما تنحفظ فوق نسخة قديمة بنفس الاسم
    filename = f"afif-contracts-backup-{datetime.now(SA_TZ).strftime('%Y-%m-%d-%H%M')}-{len(rows)}-contracts.csv"
    return send_file(io.BytesIO(data), mimetype='text/csv', as_attachment=True, download_name=filename)


@app.route('/import', methods=['GET', 'POST'])
@login_required
def import_contracts():
    """استرجاع العقود من ملف النسخة الاحتياطية. العقد اللي رقمه موجود ما يتكرر."""
    if request.method == 'GET':
        return render_template('import.html')

    file = request.files.get('file')
    if not file or not file.filename:
        return render_template('import.html', error='اختر ملف النسخة الاحتياطية (CSV) أول.')
    try:
        text = file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return render_template('import.html', error='الملف مو بصيغة CSV مقروءة (UTF-8).')

    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in ('contract_number', 'apartment_number', 'jeddah_neighborhood') if c not in (reader.fieldnames or [])]
    if missing:
        return render_template('import.html', error='الملف ناقص أعمدة: ' + '، '.join(missing))

    imported, skipped = 0, 0
    conn = get_db_connection()
    existing_numbers = {r['contract_number'] for r in conn.execute('SELECT contract_number FROM contracts')}
    existing_ids = {r['id'] for r in conn.execute('SELECT id FROM contracts')}
    # نفس العقد (نفس الشقة والمستأجر وتاريخ البداية) ما يتكرر حتى لو رقمه تغير
    same_contract = lambda r: (norm(r['jeddah_neighborhood']), norm(r['apartment_number']), (r['client_name'] or '').strip(), (r['start_date'] or '').strip())
    existing_contracts = {same_contract(r) for r in conn.execute('SELECT * FROM contracts')}
    for raw in reader:
        row = {c: (raw.get(c) or '').strip() for c in BACKUP_COLUMNS}
        row = {c: ('' if v == 'None' else v) for c, v in row.items()}
        number = row['contract_number']
        if (number and number in existing_numbers) or same_contract(row) in existing_contracts:
            skipped += 1
            continue
        existing_contracts.add(same_contract(row))
        row['contract_status'] = get_contract_status(row['start_date'], row['end_contract'])
        cols = list(row.keys())
        values = [row[c] for c in cols]
        # نحافظ على رقم العقد كـ id عشان العقود الجديدة تكمل الترقيم بعد آخر رقم
        if number.isdigit() and int(number) not in existing_ids:
            cols.insert(0, 'id')
            values.insert(0, int(number))
            existing_ids.add(int(number))
        cur = conn.execute(f"INSERT INTO contracts ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", values)
        if not number:
            number = str(cur.lastrowid).zfill(4)
            conn.execute('UPDATE contracts SET contract_number = ? WHERE id = ?', (number, cur.lastrowid))
        existing_numbers.add(number)
        imported += 1
    conn.commit()
    conn.close()
    renumber_restored_once()  # إذا هذا ملف العقود المسترجعة، يترقم من 0001 على طول
    conn = get_db_connection()
    total = conn.execute('SELECT COUNT(*) FROM contracts').fetchone()[0]
    conn.close()
    return render_template('import.html', done=True, imported=imported, skipped=skipped, total=total)


SHORT_LABELS = {'active': 'فعّال', 'due': 'عليه مبلغ', 'not-started': 'ما بدأ', 'expired': 'منتهي',
                'empty': 'بدون عقد', 'unknown': 'ناقص'}


def collect_buildings():
    """أحدث عقد لكل شقة في كل عمارة، مع العقود اللي رقم شقتها مو موجود في القوائم"""
    conn = get_db_connection()
    contracts = conn.execute("SELECT * FROM contracts ORDER BY id DESC").fetchall()
    conn.close()

    # أحدث عقد لكل شقة، والمطابقة تتحمل الأرقام العربية والمسافات
    latest = {}
    for contract in contracts:
        key = (norm(contract["jeddah_neighborhood"]), norm(contract["apartment_number"]))
        latest.setdefault(key, contract)

    buildings, used = [], set()
    for b in BUILDINGS:
        units = []
        counts = {s["key"]: 0 for s in STATUSES}
        for apt in b["apartments"]:
            key = (norm(b["neighborhood"]), norm(apt))
            used.add(key)
            contract = latest.get(key)
            st = contract_state(contract)
            counts[st["key"]] += 1
            units.append({
                "number": apt,
                "display": "محل" if apt == "Shop" else apt,
                "st": st,
                "contract": contract,
                "end_contract": contract["end_contract"] if contract else None,
                "client_name": contract["client_name"] if contract else None,
            })
        buildings.append(dict(b, units=units, counts=counts))
    unmatched = [c for key, c in latest.items() if key not in used]
    return buildings, unmatched


@app.route('/apartments')
@login_required
def apartments():
    buildings, unmatched = collect_buildings()
    return render_template("apartments.html", buildings=buildings, statuses=STATUSES, unmatched=unmatched)


def report_data():
    """أرقام وجداول التقرير الشهري"""
    buildings, unmatched = collect_buildings()
    today = datetime.now(SA_TZ).date()
    all_units, grids = [], []
    for b in buildings:
        units = []
        for u in b["units"]:
            c = u["contract"]
            rent = to_number(c["monthly_rent"]) if c else 0
            paid = to_number(c["amount_paid"]) if c else 0
            end = parse_date(c["end_contract"]) if c else None
            row = {
                "key": u["st"]["key"], "label": u["st"]["label"], "short": SHORT_LABELS[u["st"]["key"]],
                "days_text": u["st"]["days_text"], "display": u["display"], "building": b["name"],
                "client_name": c["client_name"] if c else "", "phone": c["phone"] if c else "",
                "start_dmy": format_dmy(c["start_date"]) if c else "", "end_dmy": format_dmy(c["end_contract"]) if c else "",
                "end": end, "rent": rent, "paid": paid, "remaining": max(rent - paid, 0),
            }
            units.append(row)
            all_units.append(row)
        grids.append({"name": b["name"], "units": units, "counts": b["counts"]})

    current = [u for u in all_units if u["key"] in ("active", "due")]
    total_units = len(all_units)
    totals = {
        "units": total_units,
        "rented": len(current),
        "occupancy": round(len(current) * 100 / total_units) if total_units else 0,
        "rent": sum(u["rent"] for u in current),
        "paid": sum(min(u["paid"], u["rent"]) if u["rent"] else u["paid"] for u in current),
        "remaining": sum(u["remaining"] for u in current),
        "due_count": sum(1 for u in current if u["key"] == "due"),
    }
    ending_soon = sorted((u for u in current if u["end"] and 0 <= (u["end"] - today).days <= 7), key=lambda u: u["end"])
    unmatched_rows = []
    for c in unmatched:
        st = contract_state(c)
        unmatched_rows.append({
            "apartment_number": c["apartment_number"], "jeddah_neighborhood": c["jeddah_neighborhood"],
            "client_name": c["client_name"], "phone": c["phone"], "end_dmy": format_dmy(c["end_contract"]),
            "state_label": st["label"],
        })
    return {
        "today": today,
        "labels": dict({s["key"]: s["label"] for s in STATUSES}, empty=SHORT_LABELS["empty"]),
        "buildings": grids,
        "totals": totals,
        "expired": [u for u in all_units if u["key"] == "expired"],
        "due": [u for u in all_units if u["key"] == "due"],
        "ending_soon": ending_soon,
        "unmatched": unmatched_rows,
        "rented_rows": [u for u in all_units if u["key"] in ("active", "due", "not-started")],
    }


@app.route('/monthly-report')
@login_required
def monthly_report():
    from report import build_monthly_report
    pdf_bytes, filename = build_monthly_report(report_data(), os.path.join(app.root_path, 'static'))
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)


if __name__ == '__main__':
    app.run(debug=True)
