from flask import Flask, request, render_template, jsonify, redirect, url_for, send_file
import csv
from fpdf import FPDF
import arabic_reshaper
from bidi.algorithm import get_display

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
                'الإيجار الشهري', 'عدد الأشهر', 'الإجمالي', 'المبلغ المدفوع', 'المبلغ كتابةً'
            ])
    except FileExistsError:
        pass

init_csv()

# توليد ملف PDF
def generate_pdf(data):
    pdf = FPDF(unit='mm', format=(914.4, 685.8))  # أبعاد صفحة PDF مماثلة للصورة
    pdf.add_page()
    pdf.image('static/contract.jpg', x=0, y=0, w=914.4, h=685.8)  # إدراج الصورة الخلفية
    pdf.add_font('Amiri', '', 'static/Amiri-Regular.ttf', uni=True)  # إضافة خط عربي
    pdf.set_font('Amiri', '', 28)  # حجم الخط العربي

    # استخدام اسم العميل لحفظ الملف
    client_name = data.get('client-name', 'contract')  # إذا لم يتم إدخال اسم العميل، يستخدم "contract" كاسم افتراضي
    sanitized_client_name = client_name.replace(' ', '_')  # استبدال المسافات بـ "_"
    pdf_path = f"static/{sanitized_client_name}.pdf"  # اسم الملف النهائي

    # كتابة القيم في أماكنها المناسبة بناءً على الإحداثيات
    pdf.set_xy(650, 125)  # التاريخ
    pdf.cell(120, 30, prepare_arabic_text(data.get('date', '')), border=0, align='C')

    pdf.set_xy(100, 125)  # رقم العقد
    pdf.cell(100, 30, prepare_arabic_text(data.get('contract-number', '')), border=0, align='C')

    pdf.set_xy(50, 180)  # الجنسية
    pdf.cell(300, 30, prepare_arabic_text(data.get('nationality', '')), border=0, align='C')

    pdf.set_xy(450, 180)  # اسم العميل
    pdf.cell(350, 30, prepare_arabic_text(data.get('client-name', '')), border=0, align='C')

    pdf.set_xy(450, 215)  # نوع الإثبات
    pdf.cell(350, 30, prepare_arabic_text(data.get('id-type', '')), border=0, align='C')

    pdf.set_xy(50, 215)  # رقم الإثبات
    pdf.cell(300, 30, prepare_arabic_text(data.get('id-number', '')), border=0, align='C')

    pdf.set_xy(50, 250)  # العمل
    pdf.cell(300, 30, prepare_arabic_text(data.get('job', '')), border=0, align='C')

    pdf.set_xy(450, 250)  # تاريخ الانتهاء
    pdf.cell(350, 30, prepare_arabic_text(data.get('end-date', '')), border=0, align='C')

    pdf.set_xy(200, 280)  # الراتب
    pdf.cell(150, 30, prepare_arabic_text(data.get('salary', '')), border=0, align='C')

    pdf.set_xy(50, 280)  # الحالة الاجتماعية
    pdf.cell(100, 30, prepare_arabic_text(data.get('marital-status', '')), border=0, align='C')

    pdf.set_xy(50, 350)  # جدة حي
    pdf.cell(300, 30, prepare_arabic_text(data.get('jeddah-neighborhood', '')), border=0, align='C')

    pdf.set_xy(50, 320)  # نهاية العقد
    pdf.cell(300, 30, prepare_arabic_text(data.get('end-contract', '')), border=0, align='C')

    pdf.set_xy(50, 380)  # شقة رقم
    pdf.cell(300, 30, prepare_arabic_text(data.get('apartment-number', '')), border=0, align='C')

    pdf.set_xy(50, 420)  # التأمين المدفوع
    pdf.cell(300, 30, prepare_arabic_text(data.get('insurance-paid', '')), border=0, align='C')

    pdf.set_xy(480, 540)  # أجرة
    pdf.cell(100, 30, prepare_arabic_text(data.get('rent-fee', '')), border=0, align='C')

    pdf.set_xy(630, 590)  # نفقة
    pdf.cell(150, 30, prepare_arabic_text(data.get('maintenance-fee', '')), border=0, align='C')

    pdf.set_xy(690, 630)  # توقيع المالك
    pdf.cell(150, 30, prepare_arabic_text(data.get('owner-signature', '')), border=0, align='C')

    pdf.set_xy(450, 280)  # الجوال
    pdf.cell(350, 30, prepare_arabic_text(data.get('phone', '')), border=0, align='C')

    pdf.set_xy(450, 320)  # بداية العقد
    pdf.cell(350, 30, prepare_arabic_text(data.get('start-date', '')), border=0, align='C')

    pdf.set_xy(450, 350)  # الإيجار الشهري
    pdf.cell(350, 30, prepare_arabic_text(data.get('monthly-rent', '')), border=0, align='C')

    pdf.set_xy(450, 380)  # عدد الأشهر
    pdf.cell(350, 30, prepare_arabic_text(data.get('months', '')), border=0, align='C')

    pdf.set_xy(450, 420)  # الإجمالي
    pdf.cell(350, 30, prepare_arabic_text(data.get('total', '')), border=0, align='C')

    pdf.set_xy(620, 460)  # المبلغ المدفوع
    pdf.cell(150, 30, prepare_arabic_text(data.get('amount-paid', '')), border=0, align='C')

    pdf.set_xy(120, 460)  # مبلغا وقدره
    pdf.cell(450, 30, prepare_arabic_text(data.get('amount-in-words', '')), border=0, align='C')

    pdf.output(pdf_path)
    return pdf_path, sanitized_client_name  # إضافة اسم العميل في الإرجاع

@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()

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
            data.get('amount-in-words')
        ])

    # توليد ملف PDF
    pdf_path, client_name = generate_pdf(data)
    return send_file(pdf_path, as_attachment=True, download_name=f"{client_name}.pdf")

if __name__ == '__main__':
    app.run(debug=True)
