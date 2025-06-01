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
        return "العقد غير موجود."

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
    qr_image_path = "static/qr_temp.png"
    qr.make_image(fill="black", back_color="white").save(qr_image_path)

    pdf.image(qr_image_path, x=50, y=530, w=100)

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

    apartment_number = data.get('apartment-number', 'unknown')
    contract_date = data.get('date', 'unknown')
    pdf_path = f"static/{apartment_number}_{contract_date}.pdf"
    pdf.output(pdf_path)
    return pdf_path
@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()
    contract_status = get_contract_status(data.get('start-date'), data.get('end-contract'))
    data['contract-status'] = contract_status

    apartment_number = data.get('apartment-number')
    jeddah_neighborhood = data.get('jeddah-neighborhood')

    conn = get_db_connection()
    cursor = conn.cursor()

    # التحقق مما إذا كان هناك عقد موجود لنفس رقم الشقة والحي
    existing_contract = cursor.execute(
        'SELECT id, contract_number FROM contracts WHERE apartment_number = ? AND jeddah_neighborhood = ?',
        (apartment_number, jeddah_neighborhood)
    ).fetchone()

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
    pdf_path = generate_pdf(data)
    return send_file(pdf_path, as_attachment=True, download_name=pdf_path.split('/')[-1])


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
                WHERE client_name LIKE ? 
                OR apartment_number LIKE ? 
                OR jeddah_neighborhood LIKE ? 
                OR contract_status LIKE ?
            ''', (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
        else:
            contracts = conn.execute('SELECT * FROM contracts').fetchall()

    conn.close()
    return render_template('view_database.html', contracts=contracts, get_contract_status=get_contract_status)

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

@app.route('/delete-contract', methods=['POST'])
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
    
@app.route('/apartments')
def apartments():
    # أرقام شقق العمارتين
    al_rawabi_apartments = [
        "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
        "111", "112", "113", "114", "201", "202A", "202B", "202C", "203", "204", "205", "206",
        "207", "208", "209", "210A", "210B", "210C", "211", "212", "213", "214",
        "301", "302", "303", "304", "305", "306", "307", "308", "309", "310",
        "311", "312", "313", "314", "401A", "401B", "401C", "403", "404", "405", "406",
        "407", "408", "409", "410", "411A", "411B", "411C", "412A", "412B", "412C", "413", "414", "415", 
        "416", "417", "418", "501A", "501C", "52B", "53A", "53B", "53C", "54A", "54B",
        "54C", "55B", "511A", "511B", "511C", "57A", "57B", "57C", "58A", "58B",
        "601", "602", "603", "604", "605", "606", "607", "608", "609", "610", "611", "612",
        "613", "614", "615", "616", "617", "618",
        "58C", "Shop", "2", "3", "4", "5", "6"
    ]

    bin_malik_4_apartments = [
        "1", "2", "3", "4", "5", "6", "7", "8", "9", 
        "10", "11", "12", "13", "14", "15", "16", "17",
        "21", "22", "23", "24", "25", "26", "27",
        "31", "32", "33", "34", "35", "36",
        "41", "42", "43", "44", "45", "46",
        "51", "52", "53", "54", "55", "56",
        "61", "62", "63", "64", 
        "102", "104", "106", "108", "110", "112",
        "202", "204", "206", "208", "210", "212", "213", "214",
    ]

    # جلب بيانات العقود من قاعدة البيانات
    conn = get_db_connection()
    cursor = conn.cursor()
    contracts = cursor.execute("SELECT apartment_number, start_date, end_contract, contract_status, jeddah_neighborhood FROM contracts").fetchall()
    conn.close()

    # تصنيف الشقق حسب العمارة
    al_rawabi_status = {apt: {"status": "غير متاح", "end_contract": "غير مسجل"} for apt in al_rawabi_apartments}
    bin_malik_4_status = {apt: {"status": "غير متاح", "end_contract": "غير مسجل"} for apt in bin_malik_4_apartments}

    for contract in contracts:
        apt_number = contract["apartment_number"]
        status = contract["contract_status"].strip() if contract["contract_status"] else "غير متاح"
        end_contract = contract["end_contract"] if contract["end_contract"] else "غير مسجل"
        neighborhood = contract["jeddah_neighborhood"].strip() if contract["jeddah_neighborhood"] else ""

        # التأكد من أن الشقة تذهب إلى العمارة الصحيحة
        if apt_number in al_rawabi_apartments and neighborhood == "الروابي":
            al_rawabi_status[apt_number] = {"status": status, "end_contract": end_contract}
        elif apt_number in bin_malik_4_apartments and neighborhood == "بني مالك 4":
            bin_malik_4_status[apt_number] = {"status": status, "end_contract": end_contract}

    return render_template("apartments.html", al_rawabi=al_rawabi_status, bin_malik_4=bin_malik_4_status)


if __name__ == '__main__':
    app.run(debug=True) 

#####################################################

"""from flask import Flask, request, render_template, redirect, url_for, send_file
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import qrcode
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import os

DATABASE_URL =  "postgresql://contractdatabase_user:ZKKp9WJUbg2Nt6X9BZeeR2rfLIJq9hjy@dpg-cuq699l6l47c73bj6leg-a.oregon-postgres.render.com/contractdatabase"
app = Flask(__name__)
app.config[
    'SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Contract(db.Model):
    __tablename__ = 'contracts'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(50))
    contract_number = db.Column(db.String(50))
    nationality = db.Column(db.String(100))
    id_number = db.Column(db.String(50))
    id_type = db.Column(db.String(50))
    job = db.Column(db.String(100))
    salary = db.Column(db.String(50))
    marital_status = db.Column(db.String(50))
    apartment_number = db.Column(db.String(50))
    client_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.String(50))
    end_contract = db.Column(db.String(50))
    contract_status = db.Column(db.String(50))
    jeddah_neighborhood = db.Column(db.String(100))
    transfer = db.Column(db.String(50))
    end_date = db.Column(db.String(50))
    insurance_paid = db.Column(db.String(50))
    rent_fee = db.Column(db.String(50))
    maintenance_fee = db.Column(db.String(50))
    owner_signature = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    monthly_rent = db.Column(db.String(50))
    months = db.Column(db.String(50))
    total = db.Column(db.String(50))
    amount_paid = db.Column(db.String(50))
    amount_in_words = db.Column(db.String(200))


with app.app_context():
    db.create_all()


def prepare_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)


def get_contract_status(start_date, end_contract):
    if not start_date or not end_contract:
        return "غير معروف"
    try:
        today = datetime.now().date()
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_contract, '%Y-%m-%d').date()
        if today < start:
            return "لم يبدأ"
        elif start <= today <= end:
            return "فعال"
        return "منتهي"
    except ValueError:
        return "غير معروف"


def generate_pdf(data):
    pdf = FPDF(unit='mm', format=(914.4, 685.8))
    pdf.add_page()

    static_dir = os.path.join(app.root_path, 'static')
    contract_image = os.path.join(static_dir, 'contract.png')
    if not os.path.exists(contract_image):
        raise FileNotFoundError(f"Contract template image not found at {contract_image}")

    pdf.image(contract_image, x=0, y=0, w=914.4, h=685.8)
    pdf.add_font('Amiri', '', os.path.join(static_dir, 'Amiri-Regular.ttf'), uni=True)

    pdf.set_font('Amiri', '', 50)
    pdf.set_text_color(255, 0, 0)
    contract_number = data.get('contract-number', '').zfill(4)
    pdf.set_xy(300, 130)
    pdf.cell(100, 30, contract_number, align='R')

    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Amiri', '', 35)

    def add_text(x, y, text, width=100, height=30, align='C'):
        prepared_text = prepare_arabic_text(text)
        pdf.set_xy(x, y)
        pdf.cell(width, height, prepared_text, align=align)


    fields = [
        (650, 125, data.get('date', '')),
        (50, 180, data.get('nationality', '')),
        (50, 215, data.get('id-number', '')),
        (50, 250, data.get('job', '')),
        (450, 250, data.get('end-date', '')),
        (200, 280, data.get('salary', '')),
        (50, 280, data.get('marital-status', '')),
        (50, 350, data.get('jeddah-neighborhood', '')),
        (450, 180, data.get('client-name', '')),
        (450, 215, data.get('id-type', '')),
        (50, 320, data.get('end-contract', '')),
        (50, 385, data.get('apartment-number', '')),
        (50, 420, data.get('insurance-paid', '')),
        (450, 550, data.get('rent-fee', '')),
        (600, 600, data.get('maintenance-fee', '')),
        (620, 450, data.get('amount-paid', '')),
        (120, 450, data.get('amount-in-words', '')),
        (690, 635, data.get('owner-signature', '')),
        (450, 280, data.get('phone', '')),
        (450, 320, data.get('start-date', '')),
        (450, 350, data.get('monthly-rent', '')),
        (450, 385, data.get('months', '')),
        (450, 420, data.get('total', ''))
    ]

    coordinates = [
        (650, 125), (50, 180), (50, 215), (50, 250), (450, 250),
        (200, 280), (50, 280), (50, 350), (450, 180), (450, 215),
        (50, 320), (50, 385), (50, 420), (450, 550), (600, 600),
        (620, 450), (120, 450), (690, 635), (450, 280), (450, 320),
        (450, 350), (450, 385), (450, 420)
    ]

    for (x, y), value in zip(coordinates, [fields[i][2] for i in range(len(fields))]):
        add_text(x, y, value)

    pdf_path = os.path.join(static_dir, f"{data.get('apartment-number', 'unknown')}_{data.get('date', 'unknown')}.pdf")
    pdf.output(pdf_path)
    return pdf_path


@app.route('/test-db')
def test_db():
    try:
        test = Contract.query.first()
        return "Database connection successful!"
    except Exception as e:
        return f"Database connection failed: {str(e)}"
    
    
@app.route('/')
def index():
    return render_template('index.html')  # Create this template


@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.form.to_dict()
        contract_status = get_contract_status(data.get('start-date'), data.get('end-contract'))         

        existing_contract = Contract.query.filter_by(
            apartment_number=data.get('apartment-number'),
            jeddah_neighborhood=data.get('jeddah-neighborhood')
        ).first()

        if existing_contract:
            # Update existing contract
            for field in ['date', 'nationality', 'id-number', 'id-type', 'job',
                          'salary', 'marital-status', 'client-name', 'start-date',
                          'end-contract', 'transfer', 'end-date', 'insurance-paid',
                          'rent-fee', 'maintenance-fee', 'owner-signature', 'phone',
                          'monthly-rent', 'months', 'total', 'amount-paid', 'amount-in-words']:
                setattr(existing_contract, field.replace('-', '_'), data.get(field))

            existing_contract.contract_status = contract_status
            contract_number = existing_contract.contract_number
        else:
            # Create new contract
            new_contract = Contract(
                **{k.replace('-', '_'): v for k, v in data.items()},
                contract_status=contract_status
            )
            db.session.add(new_contract)
            db.session.commit()
            new_contract.contract_number = str(new_contract.id).zfill(4)
            db.session.commit()
            contract_number = new_contract.contract_number

        data['contract-number'] = contract_number

        pdf_path = generate_pdf(data)
        return send_file(pdf_path, as_attachment=True)

    except Exception as e:
        db.session.rollback()
        return f"An error occurred: {str(e)}", 500


if __name__ == '__main__':
    app.run(debug=True)"""



#postgresql://contractdatabase_user:ZKKp9WJUbg2Nt6X9BZeeR2rfLIJq9hjy@dpg-cuq699l6l47c73bj6leg-a.oregon-postgres.render.com/contractdatabase