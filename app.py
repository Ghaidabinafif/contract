from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import qrcode
from datetime import datetime
import sqlite3

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
    conn.close()

# استدعاء دالة إنشاء قاعدة البيانات عند بدء تشغيل التطبيق
init_db()

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

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()
    contract_status = get_contract_status(data.get('start-date'), data.get('end-contract'))
    data['contract-status'] = contract_status

    # توليد رقم العقد تلقائيًا
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id) FROM contracts")
    last_contract_id = cursor.fetchone()[0]

    # التأكد من أن last_contract_id ليس None
    if last_contract_id is None:
        new_contract_number = "0001"
    else:
        new_contract_number = str(last_contract_id + 1).zfill(4)

    data['contract-number'] = new_contract_number

    apartment_number = data.get('apartment-number')
    jeddah_neighborhood = data.get('jeddah-neighborhood')

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
            data.get('date'), new_contract_number, data.get('nationality'),
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
            data.get('date'), new_contract_number, data.get('nationality'),
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

    return redirect(url_for('view_database'))

@app.route('/delete-contract', methods=['POST'])
def delete_contract():
    contract_id = request.form.get('contract_id')

    if not contract_id:
        return "لم يتم تحديد العقد المطلوب حذفه.", 400

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM contracts WHERE id = ?', (contract_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('view_database'))

@app.route('/view-database', methods=['GET', 'POST'])
def view_database():
    conn = get_db_connection()
    if request.method == 'POST':
        search_query = request.form.get('search-query')
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
    return render_template('view_database.html', contracts=contracts)

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/check-password', methods=['POST'])
def check_password():
    password = request.form.get('password')
    if password == PASSWORD:
        return redirect(url_for('view_database'))
    return "كلمة المرور غير صحيحة! حاول مرة أخرى."

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