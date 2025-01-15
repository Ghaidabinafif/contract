from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import qrcode
from datetime import datetime
import sqlite3  # لإضافة قاعدة البيانات

app = Flask(__name__)

PASSWORD = "asmaa"
DB_FILE = 'contracts.db'  # اسم ملف قاعدة البيانات

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
    conn.commit()

# استدعاء دالة إنشاء قاعدة البيانات عند بدء تشغيل التطبيق
init_db()

def prepare_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

def get_contract_status(start_date, end_contract):
    today = datetime.now().date()
    start = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
    end = datetime.strptime(end_contract, '%Y-%m-%d').date() if end_contract else None

    if start and end:
        if today < start:
            return "لم يبدأ"
        elif start <= today <= end:
            return "فعال"
        else:
            return "منتهي"
    return "غير معروف"

@app.route('/contract-status')
def contract_status():
    contract_number = request.args.get('contract_number')
    # البحث عن العقد في قاعدة البيانات
    conn = get_db_connection()
    contract = conn.execute('SELECT * FROM contracts WHERE contract_number = ?', (contract_number,)).fetchone()
    conn.close()

    if contract:
        return render_template(
            'contract_status.html',
            contract_number=contract['contract_number'],
            start_date=contract['start_date'],
            end_contract=contract['end_contract'],
            status=contract['contract_status']
        )
    else:
        return "العقد غير موجود."

def generate_pdf(data):
    pdf = FPDF(unit='mm', format=(914.4, 685.8))
    pdf.add_page()
    pdf.image('static/contract_new.jpg', x=0, y=0, w=914.4, h=685.8)
    pdf.add_font('Amiri', '', 'static/Amiri-Regular.ttf', uni=True)
    pdf.set_font('Amiri', '', 35)

    base_url = "https://contract-8duk.onrender.com/contract-status"
    contract_number = data.get('contract-number', '')
    qr_data = f"{base_url}?contract_number={contract_number}"

    qr = qrcode.QRCode(box_size=20, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_image_path = "static/qr_temp.png"
    qr.make_image(fill="black", back_color="white").save(qr_image_path)

    pdf.image(qr_image_path, x=50, y=530, w=100)

    def add_text(x, y, width, height, text, align='C'):
        pdf.set_xy(x, y)
        pdf.cell(width, height, prepare_arabic_text(text), border=0, align=align)

    add_text(650, 125, 120, 30, data.get('date', ''))
    add_text(100, 125, 100, 30, data.get('contract-number', ''))
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
    add_text(480, 550, 100, 30, data.get('rent-fee', ''))
    add_text(630, 600, 150, 30, data.get('maintenance-fee', ''))
    add_text(620, 450, 150, 30, data.get('amount-paid', ''))
    add_text(120, 450, 450, 30, data.get('amount-in-words', ''))
    add_text(690, 630, 150, 30, data.get('owner-signature', ''))
    add_text(450, 280, 350, 30, data.get('phone', ''))
    add_text(450, 320, 350, 30, data.get('start-date', ''))
    add_text(450, 350, 350, 30, data.get('monthly-rent', ''))
    add_text(450, 385, 350, 30, data.get('months', ''))
    add_text(450, 420, 350, 30, data.get('total', ''))

    pdf_path = f"static/contract_{data.get('contract-number', 'unknown')}.pdf"
    pdf.output(pdf_path)
    return pdf_path

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()
    contract_status = get_contract_status(data.get('start-date'), data.get('end-contract'))
    data['contract-status'] = contract_status

    conn = get_db_connection()
    cursor = conn.cursor()

    apartment_number = data.get('apartment-number')
    jeddah_neighborhood = data.get('jeddah-neighborhood')  # الحي
    # التحقق من وجود عقد بنفس رقم الشقة والحي
    existing_contract = cursor.execute(
        'SELECT * FROM contracts WHERE apartment_number = ? AND jeddah_neighborhood = ?',
        (apartment_number, jeddah_neighborhood)
    ).fetchone()

    if existing_contract:
        cursor.execute(''' 
            UPDATE contracts
            SET
                date = ?, contract_number = ?, nationality = ?, id_number = ?, id_type = ?,
                job = ?, salary = ?, marital_status = ?, client_name = ?, start_date = ?,
                end_contract = ?, contract_status = ?, jeddah_neighborhood = ?, transfer = ?,
                end_date = ?, insurance_paid = ?, rent_fee = ?, maintenance_fee = ?, 
                owner_signature = ?, phone = ?, monthly_rent = ?, months = ?, total = ?, 
                amount_paid = ?, amount_in_words = ?
            WHERE apartment_number = ? AND jeddah_neighborhood = ?
        ''', (
            data.get('date'), data.get('contract-number'), data.get('nationality'),
            data.get('id-number'), data.get('id-type'), data.get('job'), data.get('salary'),
            data.get('marital-status'), data.get('client-name'), data.get('start-date'),
            data.get('end-contract'), contract_status, jeddah_neighborhood, data.get('transfer'),
            data.get('end-date'), data.get('insurance-paid'), data.get('rent-fee'),
            data.get('maintenance-fee'), data.get('owner-signature'), data.get('phone'),
            data.get('monthly-rent'), data.get('months'), data.get('total'),
            data.get('amount-paid'), data.get('amount-in-words'),
            apartment_number, jeddah_neighborhood
        ))
    else:
        cursor.execute(''' 
            INSERT INTO contracts (
                date, contract_number, nationality, id_number, id_type, job, salary,
                marital_status, apartment_number, client_name, start_date, end_contract,
                contract_status, jeddah_neighborhood, transfer, end_date, insurance_paid, 
                rent_fee, maintenance_fee, owner_signature, phone, monthly_rent, months, 
                total, amount_paid, amount_in_words
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('date'), data.get('contract-number'), data.get('nationality'),
            data.get('id-number'), data.get('id-type'), data.get('job'), data.get('salary'),
            data.get('marital-status'), data.get('apartment-number'), data.get('client-name'),
            data.get('start-date'), data.get('end-contract'), contract_status,
            jeddah_neighborhood, data.get('transfer'), data.get('end-date'),
            data.get('insurance-paid'), data.get('rent-fee'), data.get('maintenance-fee'),
            data.get('owner-signature'), data.get('phone'), data.get('monthly-rent'),
            data.get('months'), data.get('total'), data.get('amount-paid'),
            data.get('amount-in-words')
        ))

    conn.commit()
    conn.close()

    pdf_path = generate_pdf(data)
    return send_file(pdf_path, as_attachment=True, download_name="contract.pdf")

@app.route('/view-database', methods=['GET', 'POST'])
def view_database():
    conn = get_db_connection()

    # إذا كان الطلب GET، عرض جميع العقود
    if request.method == 'GET':
        contracts = conn.execute('SELECT * FROM contracts').fetchall()
    else:
        # إذا كان الطلب POST، قم بمعالجة استعلام البحث
        search_query = request.form.get('search-query')
        if search_query:
            contracts = conn.execute('''
                SELECT * FROM contracts
                WHERE client_name LIKE ? OR apartment_number LIKE ? OR jeddah_neighborhood LIKE ?
            ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
        else:
            contracts = conn.execute('SELECT * FROM contracts').fetchall()

    conn.close()
    return render_template('view_database.html', contracts=contracts)


@app.route('/')
def login():
    return '''
        <form method="POST" action="/check-password">
            <label for="password">ادخل كلمة المرور:</label>
            <input type="password" id="password" name="password">
            <button type="submit">تسجيل الدخول</button>
        </form>
    '''

@app.route('/check-password', methods=['POST'])
def check_password():
    password = request.form.get('password')
    if password == PASSWORD:
        return redirect(url_for('contract_page'))
    else:
        return "كلمة المرور غير صحيحة! حاول مرة أخرى."

@app.route('/contract-page')
def contract_page():
    return render_template('index.html')



@app.route('/search-contract', methods=['POST'])
def search_contract():
    apartment_number = request.form.get('apartment-number')
    jeddah_neighborhood = request.form.get('jeddah-neighborhood')

    # التحقق من الإدخالات
    if not apartment_number or not jeddah_neighborhood:
        return render_template('index.html', error="يرجى إدخال رقم الشقة والحي للبحث.")

    # البحث عن العقد
    conn = get_db_connection()
    contract = conn.execute('''
        SELECT * FROM contracts
        WHERE apartment_number = ? AND jeddah_neighborhood = ?
    ''', (apartment_number, jeddah_neighborhood)).fetchone()
    conn.close()

    # التحقق من نتيجة البحث
    if contract:
        return render_template('index.html', contract=contract)
    else:
        return render_template('index.html', error="لم يتم العثور على عقد مطابق.")

    
    
    
if __name__ == '__main__':
    app.run(debug=True)
