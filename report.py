"""التقرير الشهري: حالة كل شقة في صفحة A4، وبعدها تفاصيل اللي يحتاج متابعة.
يستخدم بس دوال FPDF الموجودة في fpdf و fpdf2 الاثنين، عشان يشتغل أياً كان المثبت في السيرفر."""
import os
import tempfile

import arabic_reshaper
from bidi.algorithm import get_display
from fpdf import FPDF

MONTHS_AR = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر',
             'أكتوبر', 'نوفمبر', 'ديسمبر']

# نفس ألوان الموقع: (لون التعبئة، لون الكتابة)
COLORS = {
    'active': ((21, 128, 61), (255, 255, 255)),
    'due': ((245, 158, 11), (31, 35, 40)),
    'not-started': ((29, 78, 216), (255, 255, 255)),
    'expired': ((200, 30, 30), (255, 255, 255)),
    'empty': ((236, 233, 228), (90, 90, 90)),
    'unknown': ((107, 114, 128), (255, 255, 255)),
}
BRONZE = (160, 112, 63)
INK = (31, 35, 40)
MUTED = (95, 99, 104)
LINE = (220, 214, 206)

PAGE_W, PAGE_H = 210, 297
MARGIN = 10
RIGHT = PAGE_W - MARGIN
CONTENT_W = PAGE_W - 2 * MARGIN


def ar(text):
    return get_display(arabic_reshaper.reshape(str(text)))


def money(value):
    return f'{value:,.0f}'


class MonthlyReport:
    def __init__(self, static_dir, footer_text):
        self.static_dir = static_dir
        self.footer_text = footer_text
        self.pdf = FPDF('P', 'mm', 'A4')
        self.pdf.set_auto_page_break(False)
        self.pdf.add_font('Amiri', '', os.path.join(static_dir, 'Amiri-Regular.ttf'), uni=True)
        self.pdf.add_font('Amiri', 'B', os.path.join(static_dir, 'Amiri Bold.ttf'), uni=True)
        self.y = MARGIN

    # ---------- أدوات الرسم ----------
    def font(self, size, bold=False, color=INK):
        self.pdf.set_font('Amiri', 'B' if bold else '', size)
        self.pdf.set_text_color(*color)

    def text(self, x, y, w, h, value, align='R', size=10, bold=False, color=INK, fill=None):
        self.font(size, bold, color)
        if fill:
            self.pdf.set_fill_color(*fill)
        self.pdf.set_xy(x, y)
        self.pdf.cell(w, h, ar(value), border=0, align=align, fill=bool(fill))

    def fit(self, value, w, size, bold=False):
        """يصغّر الخط لين يدخل النص في العرض"""
        while size > 5:
            self.font(size, bold)
            if self.pdf.get_string_width(ar(value)) <= w:
                break
            size -= 0.5
        return size

    def hline(self, y, color=LINE, width=0.3):
        self.pdf.set_draw_color(*color)
        self.pdf.set_line_width(width)
        self.pdf.line(MARGIN, y, RIGHT, y)

    def new_page(self):
        self.pdf.add_page()
        # التذييل ينكتب أول ما تنفتح الصفحة (رقم الصفحة بس، ما نحتاج العدد الكلي)
        self.text(MARGIN, PAGE_H - 9, CONTENT_W, 5, f'{self.footer_text} - صفحة {self.pdf.page_no()}',
                  align='C', size=8, color=MUTED)
        self.y = MARGIN

    # ---------- الصفحة الأولى ----------
    def header(self, title, subtitle):
        logo = os.path.join(self.static_dir, 'logo-report.png')
        if os.path.exists(logo):
            self.pdf.image(logo, x=MARGIN, y=self.y, h=13)
        self.text(MARGIN + 46, self.y, CONTENT_W - 46, 8, title, size=17, bold=True)
        self.text(MARGIN + 46, self.y + 8, CONTENT_W - 46, 6, subtitle, size=10, color=MUTED)
        self.y += 17
        self.hline(self.y, BRONZE, 0.8)
        self.y += 4

    def stat_boxes(self, boxes):
        gap = 3
        w = (CONTENT_W - gap * (len(boxes) - 1)) / len(boxes)
        x = RIGHT - w
        for label, value, note in boxes:
            self.pdf.set_draw_color(*LINE)
            self.pdf.set_fill_color(250, 248, 245)
            self.pdf.set_line_width(0.3)
            self.pdf.rect(x, self.y, w, 19, 'DF')
            self.text(x + 2, self.y + 1.5, w - 4, 5, label, size=8.5, color=MUTED)
            size = self.fit(value, w - 4, 15, bold=True)
            self.text(x + 2, self.y + 6.5, w - 4, 7, value, size=size, bold=True)
            if note:
                self.text(x + 2, self.y + 13, w - 4, 5, note, size=7.5, color=MUTED)
            x -= w + gap
        self.y += 23

    def building_grid(self, building, labels):
        counts = building['counts']
        parts = '، '.join(f"{labels[k]} {counts[k]}" for k in COLORS if counts.get(k))
        self.text(MARGIN, self.y, CONTENT_W, 6, f"{building['name']} ({len(building['units'])} وحدة)", size=12, bold=True)
        self.text(MARGIN, self.y + 6, CONTENT_W, 5, parts, size=8.5, color=MUTED)
        self.y += 12

        cols = 12
        gap = 1.2
        w = (CONTENT_W - gap * (cols - 1)) / cols
        h = 10.6
        for i, unit in enumerate(building['units']):
            row, col = divmod(i, cols)
            x = RIGHT - w - col * (w + gap)
            y = self.y + row * (h + gap)
            fill, ink = COLORS[unit['key']]
            self.pdf.set_fill_color(*fill)
            self.pdf.set_draw_color(*(LINE if unit['key'] == 'empty' else fill))
            self.pdf.set_line_width(0.25)
            self.pdf.rect(x, y, w, h, 'DF')
            num_size = self.fit(unit['display'], w - 1.5, 10.5, bold=True)
            self.text(x + 0.5, y + 1.0, w - 1, 4.8, unit['display'], align='C', size=num_size, bold=True, color=ink)
            label_size = self.fit(unit['short'], w - 1, 7)
            self.text(x + 0.5, y + 5.8, w - 1, 3.8, unit['short'], align='C', size=label_size, color=ink)
        rows = (len(building['units']) + cols - 1) // cols
        self.y += rows * (h + gap) + 3

    def legend(self, labels):
        x = RIGHT
        for key, (fill, _) in COLORS.items():
            label = labels[key]
            self.font(8)
            tw = self.pdf.get_string_width(ar(label)) + 1
            self.pdf.set_fill_color(*fill)
            self.pdf.set_draw_color(*LINE)
            self.pdf.rect(x - 4, self.y + 1.2, 3.5, 3.5, 'DF')
            self.text(x - 4 - tw - 1, self.y, tw + 1, 6, label, size=8, color=MUTED)
            x -= 4 + tw + 6
        self.y += 8

    # ---------- جداول التفاصيل ----------
    def section_title(self, title, note=''):
        if self.y > PAGE_H - 40:
            self.new_page()
        self.text(MARGIN, self.y, CONTENT_W, 7, title, size=13, bold=True)
        self.y += 7
        if note:
            self.text(MARGIN, self.y, CONTENT_W, 5, note, size=8.5, color=MUTED)
            self.y += 5
        self.y += 1

    def table(self, columns, rows, empty_text='ما فيه شي.'):
        """columns: [(العنوان، العرض، المحاذاة)] من اليمين لليسار"""
        if not rows:
            self.text(MARGIN, self.y, CONTENT_W, 6, empty_text, size=9.5, color=MUTED)
            self.y += 10
            return
        row_h = 6.2

        def head():
            x = RIGHT
            self.pdf.set_fill_color(61, 61, 61)
            self.pdf.rect(MARGIN, self.y, CONTENT_W, row_h, 'F')
            for title, w, _ in columns:
                x -= w
                self.text(x + 1, self.y + 0.3, w - 2, row_h - 0.6, title, align='R', size=8.5, bold=True, color=(255, 255, 255))
            self.y += row_h

        head()
        for n, row in enumerate(rows):
            if self.y + row_h > PAGE_H - 14:
                self.new_page()
                head()
            if n % 2:
                self.pdf.set_fill_color(247, 245, 242)
                self.pdf.rect(MARGIN, self.y, CONTENT_W, row_h, 'F')
            x = RIGHT
            for (title, w, align), value in zip(columns, row):
                x -= w
                value = '' if value is None else str(value)
                size = self.fit(value, w - 2, 8.5)
                self.text(x + 1, self.y + 0.3, w - 2, row_h - 0.6, value, align=align, size=size)
            self.y += row_h
        self.hline(self.y)
        self.y += 6

    def output_bytes(self):
        fd, path = tempfile.mkstemp(suffix='.pdf')
        os.close(fd)
        try:
            self.pdf.output(path)
            with open(path, 'rb') as f:
                return f.read()
        finally:
            os.remove(path)


def build_monthly_report(data, static_dir):
    """data جاي من app.report_data()"""
    labels = data['labels']
    today = data['today']
    month_title = f"{MONTHS_AR[today.month - 1]} {today.year}"
    generated = f"أملاك عبدالقادر عفيف - التقرير الشهري - {today.strftime('%d/%m/%Y')}"
    r = MonthlyReport(static_dir, generated)

    # الصفحة الأولى: الملخص وحالة كل شقة
    r.new_page()
    r.header(f'التقرير الشهري - {month_title}', f"حالة الشقق بتاريخ {today.strftime('%d/%m/%Y')}")
    t = data['totals']
    r.stat_boxes([
        ('الشقق المؤجرة', f"{t['rented']} من {t['units']}", f"نسبة الإشغال {t['occupancy']}%"),
        ('إيجارات العقود السارية', f"{money(t['rent'])} ريال", f"{t['rented']} عقد"),
        ('المدفوع', f"{money(t['paid'])} ريال", ''),
        ('المتبقي على المستأجرين', f"{money(t['remaining'])} ريال", f"{t['due_count']} عقد عليه مبلغ"),
    ])
    for b in data['buildings']:
        r.building_grid(b, labels)
    r.legend(labels)

    # الصفحة الثانية: اللي يحتاج متابعة
    r.new_page()
    r.header('يحتاج متابعة', f'التقرير الشهري - {month_title}')
    follow_cols = [('الشقة', 18, 'R'), ('العمارة', 22, 'R'), ('المستأجر', 56, 'R'), ('الجوال', 28, 'C'),
                   ('نهاية العقد', 24, 'C'), ('ملاحظة', 42, 'R')]
    r.section_title(f"عقود منتهية ({len(data['expired'])})", 'خلص عقدها وما تجدد')
    r.table(follow_cols, [[u['display'], u['building'], u['client_name'], u['phone'], u['end_dmy'], u['days_text']]
                          for u in data['expired']])
    r.section_title(f"عليها مبالغ ({len(data['due'])})", 'المدفوع أقل من مبلغ الإيجار')
    r.table(follow_cols, [[u['display'], u['building'], u['client_name'], u['phone'], u['end_dmy'],
                           f"باقي {money(u['remaining'])} ريال"] for u in data['due']])
    r.section_title(f"تنتهي خلال 7 أيام ({len(data['ending_soon'])})", 'عقود سارية قربت تخلص')
    r.table(follow_cols, [[u['display'], u['building'], u['client_name'], u['phone'], u['end_dmy'], u['days_text']]
                          for u in data['ending_soon']])
    if data['unmatched']:
        r.section_title(f"عقود برقم شقة مو موجود في القائمة ({len(data['unmatched'])})",
                        'ما تطلع على مربعات الشقق: يحتاج تتأكد من رقم الشقة')
        r.table(follow_cols, [[c['apartment_number'], c['jeddah_neighborhood'], c['client_name'], c['phone'],
                               c['end_dmy'], c['state_label']] for c in data['unmatched']])

    # تفاصيل كل العقود الحالية
    r.section_title(f"كل الشقق المؤجرة ({len(data['rented_rows'])})")
    r.table([('الشقة', 16, 'R'), ('العمارة', 20, 'R'), ('المستأجر', 50, 'R'), ('من', 20, 'C'), ('إلى', 20, 'C'),
             ('الإيجار', 18, 'C'), ('المدفوع', 18, 'C'), ('الحالة', 28, 'R')],
            [[u['display'], u['building'], u['client_name'], u['start_dmy'], u['end_dmy'], money(u['rent']),
              money(u['paid']), u['label']] for u in data['rented_rows']])
    return r.output_bytes(), f"afif-monthly-report-{today.strftime('%Y-%m')}.pdf"
