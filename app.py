from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file
import csv
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import qrcode
from datetime import datetime
import sqlite3

app = Flask(__name__)

PASSWORD = "asmaa"
db_file = 'contracts.db'

# دالة لإنشاء اتصال بقاعدة البيانات
def get_db_connection():
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row  # للحصول على البيانات كـ dictionary
    return conn

# دالة لإنشاء جدول العقود إذا لم يكن موجودًا
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
            end_date TEXT,
            end_contract TEXT,
            insurance_paid TEXT,
            rent_fee TEXT,
            maintenance_fee TEXT,
            owner_signature TEXT,
            phone TEXT,
            start_date TEXT,
            monthly_rent TEXT,
            months INTEGER,
            total TEXT,
            amount_paid TEXT,
            amount_in_words TEXT,
            contract_status TEXT,
            jeddah_neighborhood TEXT,
            transfer TEXT
            )
    ''')
    conn.commit()
    conn.close()

init_db()



# دالة لمعالجة النصوص العربية
def prepare_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# دالة لحساب حالة العقد
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
    contract_number = request.args.get('contract_number')  # الحصول على رقم العقد من الطلب
    conn = get_db_connection()  # إنشاء اتصال بقاعدة البيانات
    contract = conn.execute('SELECT * FROM contracts WHERE contract_number = ?', (contract_number,)).fetchone()
    conn.close()

    if contract:
        # إذا تم طلب البيانات بصيغة JSON
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                "contract_number": contract['contract_number'],
                "start_date": contract['start_date'],
                "end_contract": contract['end_contract'],
                "status": contract['contract_status']
            })
        # إذا لم يتم طلب JSON، عرض صفحة HTML
        return render_template(
            'contract_status.html',
            contract_number=contract['contract_number'],
            start_date=contract['start_date'],
            end_contract=contract['end_contract'],
            status=contract['contract_status']
        )

    # في حالة عدم العثور على العقد
    if request.headers.get('Accept') == 'application/json':
        return jsonify({"error": "العقد غير موجود"}), 404
    return render_template('contract_status.html', error="العقد غير موجود")




# توليد ملف PDF
def generate_pdf(data):
    pdf = FPDF(unit='mm', format=(914.4, 685.8))  # أبعاد صفحة PDF
    pdf.add_page()
    pdf.image('static/contract_new.jpg', x=0, y=0, w=914.4, h=685.8)  # الخلفية
    pdf.add_font('Amiri', '', 'static/Amiri-Regular.ttf', uni=True)  # خط عربي
    pdf.set_font('Amiri', '', 35)  # حجم الخط

    base_url = "https://contract-8duk.onrender.com/contract-status"
    contract_number = data.get('contract-number', '')
    
    qr_data = f"{base_url}?contract_number={contract_number}"


    # إنشاء الباركود
    qr = qrcode.QRCode(box_size=20, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)

    # حفظ صورة الباركود مؤقتًا
    qr_image_path = "static/qr_temp.png"
    qr.make_image(fill="black", back_color="white").save(qr_image_path)

    # إضافة الباركود إلى PDF
    pdf.image(qr_image_path, x=50, y=530, w=100)

    # تعريف نصوص الحقول مع التأكد من بقائها داخل الصفحة
    def add_text(x, y, width, height, text, align='C'):
        """إضافة نص داخل الصفحة مع التأكد من عدم تجاوز الحدود"""
        if y + height > 685.8 - 10:  # التأكد من أن النص لا يخرج عن الصفحة
            print(f"Warning: تجاوز النص الحدود السفلية عند y={y}. النص لن يتم عرضه.")
            return
        pdf.set_xy(x, y)
        pdf.cell(width, height, prepare_arabic_text(text), border=0, align=align)

    # كتابة البيانات في الحقول
    add_text(650, 125, 120, 30, data.get('date', ''))  # التاريخ
    add_text(100, 125, 100, 30, data.get('contract-number', ''))  # رقم العقد
    add_text(50, 180, 300, 30, data.get('nationality', ''))  # الجنسية
    add_text(50, 215, 300, 30, data.get('id-number', ''))  # رقم الإثبات
    add_text(50, 250, 300, 30, data.get('job', ''))  # العمل
    add_text(450, 250, 350, 30, data.get('end-date', ''))  # تاريخ الانتهاء
    add_text(200, 280, 150, 30, data.get('salary', ''))  # الراتب
    add_text(50, 280, 100, 30, data.get('marital-status', ''))  # الحالة الاجتماعية
    add_text(50, 350, 300, 30, data.get('jeddah-neighborhood', ''))  # جدة حي
    add_text(450, 180, 350, 30, data.get('client-name', ''))  # اسم العميل
    add_text(450, 215, 350, 30, data.get('id-type', ''))  # نوع الإثبات
    add_text(50, 320, 300, 30, data.get('end-contract', ''))  # نهاية العقد
    add_text(50, 385, 300, 30, data.get('apartment-number', ''))  # شقة رقم
    add_text(50, 420, 300, 30, data.get('insurance-paid', ''))  # التأمين المدفوع
    add_text(480, 550, 100, 30, data.get('rent-fee', ''))  # أجرة
    add_text(630, 600, 150, 30, data.get('maintenance-fee', ''))  # نفقة
    add_text(620, 450, 150, 30, data.get('amount-paid', ''))  # المبلغ المدفوع
    add_text(120, 450, 450, 30, data.get('amount-in-words', ''))  # مبلغا وقدره
    add_text(690, 630, 150, 30, data.get('owner-signature', ''))  # توقيع المالك
    add_text(450, 280, 350, 30, data.get('phone', ''))  # الجوال
    add_text(450, 320, 350, 30, data.get('start-date', ''))  # بداية العقد
    add_text(450, 350, 350, 30, data.get('monthly-rent', ''))  # الإيجار الشهري
    add_text(450, 385, 350, 30, data.get('months', ''))  # عدد الأشهر
    add_text(450, 420, 350, 30, data.get('total', ''))  # الإجمالي

    # حفظ ملف PDF
    pdf_path = f"static/contract_{data.get('contract-number', 'unknown')}.pdf"
    pdf.output(pdf_path)
    return pdf_path

@app.route('/view-database', methods=['GET', 'POST'])
def view_database():
    conn = get_db_connection()
    
    # التحقق مما إذا كان هناك طلب بحث
    query = None
    contracts = []
    if request.method == 'POST':
        query = request.form.get('search', None)  # الحصول على قيمة البحث
        if query:
            contracts = conn.execute('''
                SELECT * FROM contracts
                WHERE 
                    apartment_number LIKE ? OR
                    client_name LIKE ? OR
                    contract_number LIKE ?
            ''', (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
    else:
        # عرض جميع العقود إذا لم يكن هناك بحث
        contracts = conn.execute('SELECT * FROM contracts').fetchall()
    
    conn.close()
    return render_template('view_database.html', contracts=contracts, query=query)



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

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()

    # حساب حالة العقد
    contract_status = get_contract_status(data.get('start-date'), data.get('end-contract'))
    data['contract-status'] = contract_status

    # حفظ البيانات في SQLite
    
     # فتح اتصال بقاعدة البيانات
    conn = get_db_connection()
    cursor = conn.cursor()

    # التحقق من وجود الشقة بناءً على رقم الشقة
    apartment_number = data.get('apartment-number', None)
    existing_contract = cursor.execute(
        'SELECT * FROM contracts WHERE apartment_number = ?',
        (apartment_number,)
    ).fetchone()

    if existing_contract:
        # تحديث بيانات الشقة إذا كانت موجودة
        cursor.execute('''
            UPDATE contracts
            SET
                date = ?,
                contract_number = ?,
                nationality = ?,
                id_number = ?,
                id_type = ?,
                job = ?,
                salary = ?,
                marital_status = ?,
                client_name = ?,
                end_date = ?,
                end_contract = ?,
                insurance_paid = ?,
                rent_fee = ?,
                maintenance_fee = ?,
                owner_signature = ?,
                phone = ?,
                start_date = ?,
                monthly_rent = ?,
                months = ?,
                total = ?,
                amount_paid = ?,
                amount_in_words = ?,
                contract_status = ?,
                jeddah_neighborhood = ?,
            transfer = ?
            WHERE apartment_number = ?
        ''', (
            data.get('date', None),
            data.get('contract-number', None),
            data.get('nationality', None),
            data.get('id-number', None),
            data.get('id-type', None),
            data.get('job', None),
            data.get('salary', None),
            data.get('marital-status', None),
            data.get('client-name', None),
            data.get('end-date', None),
            data.get('end-contract', None),
            data.get('insurance-paid', None),
            data.get('rent-fee', None),
            data.get('maintenance-fee', None),
            data.get('owner-signature', None),
            data.get('phone', None),
            data.get('start-date', None),
            data.get('monthly-rent', None),
            data.get('months', None),
            data.get('total', None),
            data.get('amount-paid', None),
            data.get('amount-in-words', None),
            contract_status,
            data.get('jeddah-neighborhood', None),  # إضافة جدة حي
        data.get('transfer', None),  # إضافة نوع التحويل
            apartment_number
        ))
    else:
        # إضافة بيانات جديدة إذا لم تكن الشقة موجودة
        cursor.execute('''
            INSERT INTO contracts (
                date, contract_number, nationality, id_number, id_type, job, salary,
                marital_status, apartment_number, client_name, end_date, end_contract,
                insurance_paid, rent_fee, maintenance_fee, owner_signature, phone,
                start_date, monthly_rent, months, total, amount_paid, amount_in_words,
                contract_status, jeddah_neighborhood, transfer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('date', None),
            data.get('contract-number', None),
            data.get('nationality', None),
            data.get('id-number', None),
            data.get('id-type', None),
            data.get('job', None),
            data.get('salary', None),
            data.get('marital-status', None),
            data.get('apartment-number', None),
            data.get('client-name', None),
            data.get('end-date', None),
            data.get('end-contract', None),
            data.get('insurance-paid', None),
            data.get('rent-fee', None),
            data.get('maintenance-fee', None),
            data.get('owner-signature', None),
            data.get('phone', None),
            data.get('start-date', None),
            data.get('monthly-rent', None),
            data.get('months', None),
            data.get('total', None),
            data.get('amount-paid', None),
            data.get('amount-in-words', None),
            contract_status,
            data.get('jeddah-neighborhood', None),  # إضافة جدة حي
        data.get('transfer', None)  # إضافة نوع التحويل
        ))

    conn.commit()
    conn.close()

    # توليد ملف PDF
    pdf_path = generate_pdf(data)
    return send_file(pdf_path, as_attachment=True, download_name="contract.pdf")

if __name__ == '__main__':
    app.run(debug=True)
