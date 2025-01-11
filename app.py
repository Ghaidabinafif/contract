from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file
import csv
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display
import qrcode
from datetime import datetime

app = Flask(__name__)

PASSWORD = "asmaa"
csv_file = 'contracts.csv'

# دالة لمعالجة النصوص العربية
def prepare_arabic_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

# إنشاء ملف CSV إذا لم يكن موجودًا
def init_csv():
    try:
        with open(csv_file, 'x', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow([
                'التاريخ', 'رقم العقد', 'الجنسية', 'رقم الإثبات', 'نوع الإثبات',
                'الوظيفة', 'الراتب', 'الحالة الاجتماعية', 'رقم الشقة', 'اسم العميل',
                'تاريخ الانتهاء', 'نهاية العقد', 'التأمين المدفوع', 'أجرة',
                'نفقة الصيانة', 'توقيع المالك', 'رقم الجوال', 'تاريخ البداية',
                'الإيجار الشهري', 'عدد الأشهر', 'الإجمالي', 'المبلغ المدفوع', 'المبلغ كتابةً', 'حالة العقد'
            ])
    except FileExistsError:
        pass

init_csv()

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
    contract_number = request.args.get('contract_number')
    with open(csv_file, newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['رقم العقد'] == contract_number:
                # إعادة البيانات كـ JSON إذا تم طلبها
                if request.headers.get('Accept') == 'application/json':
                    return jsonify({
                        "contract_number": row['رقم العقد'],
                        "start_date": row['تاريخ البداية'],
                        "end_contract": row['نهاية العقد'],
                        "status": row['حالة العقد']
                    })
                # إعادة صفحة HTML إذا لم يُطلب JSON
                return render_template('contract_status.html', 
                                       contract_number=row['رقم العقد'],
                                       start_date=row['تاريخ البداية'],
                                       end_contract=row['نهاية العقد'],
                                       status=row['حالة العقد'])
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

    # إنشاء الباركود
    qr_data = f"رقم العقد: {data.get('contract-number', '')}\nبداية: {data.get('start-date', '')}\nنهاية: {data.get('end-contract', '')}\nالحالة: {data.get('contract-status', '')}"
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

    # حفظ البيانات في ملف CSV
    with open(csv_file, 'a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow([
            data.get('date'),
            data.get('contract-number'),
            data.get('nationality'),
            data.get('id-number'),
            data.get('id-type'),
            data.get('job'),
            data.get('salary'),
            data.get('marital-status'),
            data.get('apartment-number'),
            data.get('client-name'),
            data.get('end-date'),
            data.get('end-contract'),
            data.get('insurance-paid'),
            data.get('rent-fee'),
            data.get('maintenance-fee'),
            data.get('owner-signature'),
            data.get('phone'),
            data.get('start-date'),
            data.get('monthly-rent'),
            data.get('months'),
            data.get('total'),
            data.get('amount-paid'),
            data.get('amount-in-words'),
            contract_status
        ])

    # توليد ملف PDF
    pdf_path = generate_pdf(data)
    return send_file(pdf_path, as_attachment=True, download_name="contract.pdf")

if __name__ == '__main__':
    app.run(debug=True)
