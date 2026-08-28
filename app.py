# -*- coding: utf-8 -*-
import sys
import os
import sqlite3
import datetime
import urllib.parse
import webbrowser
import tempfile
import csv
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

DB_NAME = "sarhan_pharmacy.db"
CONFIG_FILE = "printer_config.json"

DRUG_FORMS = ["أقراص", "كبسولات", "شراب", "نقط", "حقن", "مرهم / كريم", "فوار", "بخاخ", "لبوس", "قطرة", "غسول", "جل"]
DRUG_USES = ["مسكن ومضاد للالتهاب", "مضاد حيوي", "خافض حرارة", "علاج ضغط الدم", "علاج السكر", "مضاد للحساسية", "مكمل غذائي", "حماية المعدة", "موسع للشعب", "مذيب بلغم"]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            units INTEGER DEFAULT 30,
            daily_use REAL DEFAULT 1,
            alert_status TEXT DEFAULT 'active',
            snooze_date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            med_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            form TEXT,
            use_case TEXT,
            start_date TEXT NOT NULL,
            duration_days INTEGER NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS all_medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            form TEXT,
            use_case TEXT,
            default_dosage TEXT,
            drawer_location TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_printer_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("printer_name", "")
        except:
            pass
    return ""

def save_printer_config(printer_name):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"printer_name": printer_name}, f)
    except Exception as e:
        messagebox.showerror("خطأ", f"تعذر حفظ إعدادات الطابعة: {e}")

def send_to_zd_printer(text_content):
    printer_name = load_printer_config()
    try:
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8')
        temp_file.write(text_content)
        temp_file.close()
        
        if printer_name and sys.platform.startswith('win'):
            # طباعة مباشرة للطابعة المحفوظة دون إظهار نافذة
            os.system(f'notepad /p "{temp_file.name}"') # افتراضي آمن أو استخدام أمر الطباعة المباشر
        else:
            if sys.platform.startswith('win'):
                os.startfile(temp_file.name, "print")
            else:
                os.system(f"lpr '{temp_file.name}'")
        messagebox.showinfo("طباعة", f"تم إرسال الاستيكر للطابعة بنجاح.")
    except Exception as e:
        messagebox.showerror("خطأ", f"تعذر طباعة الاستيكر: {str(e)}")

class PharmacyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("صيدلية سرحان - نظام الإدارة والطباعة الذكي 🌿")
        self.geometry("1350x850")
        self.configure(bg="#f4f6f9")

        self.selected_patient_id = None
        self.selected_med_id = None
        self.selected_db_med_id = None
        self.primary_blue = "#0056b3"

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure(".", font=("Segoe UI", 10), background="#f4f6f9")
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 11, "bold"), foreground=self.primary_blue, background="#ffffff")
        self.style.configure("Treeview", font=("Segoe UI", 9), rowheight=26)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#d0e2f5", foreground="#002b5c")

        header = tk.Frame(self, bg=self.primary_blue, height=60)
        header.pack(fill="x", side="top")
        tk.Label(header, text="صيدلية سرحان 🌿", font=("Segoe UI", 16, "bold"), fg="#fff", bg=self.primary_blue).pack(side="right", padx=15, pady=10)
        tk.Label(header, text="إدارة العملاء، الأدوية، التنبيهات والطباعة المخصصة", font=("Segoe UI", 9), fg="#d0e2f5", bg=self.primary_blue).pack(side="left", padx=15, pady=15)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_patients = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_patients, text=" 👤 العملاء والتنبيهات والواتساب ")

        self.tab_print = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_print, text=" 🖨️ طباعة جرعة سريعة ")

        self.tab_med_db = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_med_db, text=" 💊 قاعدة بيانات الأدوية ")

        self.build_patients_tab()
        self.build_print_tab()
        self.build_med_db_tab()

        self.load_patients()
        self.load_reminders()
        self.load_all_meds_db()

    def build_patients_tab(self):
        main_pane = tk.Frame(self.tab_patients, bg="#ffffff")
        main_pane.pack(fill="both", expand=True, padx=5, pady=5)

        left_frame = tk.Frame(main_pane, bg="#ffffff", bd=1, relief="solid")
        left_frame.pack(side="right", fill="both", expand=True, padx=(5, 0), pady=2)

        right_frame = tk.Frame(main_pane, bg="#ffffff", bd=1, relief="solid")
        right_frame.pack(side="left", fill="both", expand=True, padx=(0, 5), pady=2)

        # بيانات المريض
        ttk.Label(left_frame, text="بيانات العميل وحساب الاستهلاك", style="SubHeader.TLabel").pack(anchor="ne", padx=10, pady=5)
        p_grid = tk.Frame(left_frame, bg="#ffffff")
        p_grid.pack(fill="x", padx=10, pady=2)

        tk.Label(p_grid, text="الاسم:", bg="#ffffff").grid(row=0, column=3, sticky="e", pady=2)
        self.entry_pname = ttk.Entry(p_grid, width=18, justify="right")
        self.entry_pname.grid(row=0, column=2, padx=2, pady=2)

        tk.Label(p_grid, text="الموبايل:", bg="#ffffff").grid(row=0, column=1, sticky="e", pady=2)
        self.entry_pphone = ttk.Entry(p_grid, width=15, justify="right")
        self.entry_pphone.grid(row=0, column=0, padx=2, pady=2)

        tk.Label(p_grid, text="العنوان:", bg="#ffffff").grid(row=1, column=3, sticky="e", pady=2)
        self.entry_paddress = ttk.Entry(p_grid, width=18, justify="right")
        self.entry_paddress.grid(row=1, column=2, padx=2, pady=2)

        tk.Label(p_grid, text="عدد الوحدات:", bg="#ffffff").grid(row=2, column=3, sticky="e", pady=2)
        self.entry_punits = ttk.Entry(p_grid, width=18, justify="right")
        self.entry_punits.insert(0, "30")
        self.entry_punits.grid(row=2, column=2, padx=2, pady=2)

        tk.Label(p_grid, text="الاستهلاك اليومي:", bg="#ffffff").grid(row=2, column=1, sticky="e", pady=2)
        self.entry_pydaily = ttk.Entry(p_grid, width=15, justify="right")
        self.entry_pydaily.insert(0, "1")
        self.entry_pydaily.grid(row=2, column=0, padx=2, pady=2)

        p_btn_box = tk.Frame(left_frame, bg="#ffffff")
        p_btn_box.pack(fill="x", padx=10, pady=5)

        tk.Button(p_btn_box, text="إضافة عميل", bg=self.primary_blue, fg="white", font=("Segoe UI", 9, "bold"), command=self.add_patient, relief="flat").pack(side="right", expand=True, fill="x", padx=2)
        tk.Button(p_btn_box, text="تعديل بيانات العميل", bg="#f57c00", fg="white", font=("Segoe UI", 9, "bold"), command=self.update_patient, relief="flat").pack(side="right", expand=True, fill="x", padx=2)
        tk.Button(p_btn_box, text="حذف", bg="#c62828", fg="white", font=("Segoe UI", 9, "bold"), command=self.delete_patient, relief="flat").pack(side="left", expand=True, fill="x", padx=2)

        ttk.Separator(left_frame, orient="horizontal").pack(fill="x", padx=10, pady=8)

        # أدوية العميل
        ttk.Label(left_frame, text="أدوية العميل الموصفة", style="SubHeader.TLabel").pack(anchor="ne", padx=10, pady=2)
        m_grid = tk.Frame(left_frame, bg="#ffffff")
        m_grid.pack(fill="x", padx=10, pady=2)

        tk.Label(m_grid, text="اسم الدواء:", bg="#ffffff").grid(row=0, column=3, sticky="e")
        self.entry_mname = ttk.Entry(m_grid, width=18, justify="right")
        self.entry_mname.grid(row=0, column=2, padx=2, pady=2)

        tk.Label(m_grid, text="الجرعة:", bg="#ffffff").grid(row=0, column=1, sticky="e")
        self.entry_mdosage = ttk.Entry(m_grid, width=18, justify="right")
        self.entry_mdosage.insert(0, "قرص 3 مرات يومياً")
        self.entry_mdosage.grid(row=0, column=0, padx=2, pady=2)

        m_btn_box = tk.Frame(left_frame, bg="#ffffff")
        m_btn_box.pack(fill="x", padx=10, pady=4)
        tk.Button(m_btn_box, text="+ إضافة دواء للعميل", bg=self.primary_blue, fg="white", font=("Segoe UI", 8, "bold"), command=self.add_medication, relief="flat").pack(side="right", expand=True, fill="x", padx=1)
        tk.Button(m_btn_box, text="حذف دواء", bg="#c62828", fg="white", font=("Segoe UI", 8, "bold"), command=self.delete_medication, relief="flat").pack(side="left", expand=True, fill="x", padx=1)

        self.tree_meds = ttk.Treeview(left_frame, columns=("id", "med_name", "dosage"), show="headings", height=5)
        self.tree_meds.heading("id", text="ID")
        self.tree_meds.heading("med_name", text="الدواء")
        self.tree_meds.heading("dosage", text="الجرعة")
        self.tree_meds.column("id", width=30, anchor="center")
        self.tree_meds.column("med_name", width=150, anchor="e")
        self.tree_meds.column("dosage", width=180, anchor="e")
        self.tree_meds.pack(fill="x", padx=10, pady=2)

        # قسم اليمين: جدول العملاء والتنبيهات والواتساب
        tk.Label(right_frame, text="قائمة العملاء والحساب الذكي للاستهلاك:", bg="#ffffff", font=("Segoe UI", 9, "bold")).pack(anchor="ne", padx=10, pady=(5, 0))
        
        self.tree_patients = ttk.Treeview(right_frame, columns=("id", "name", "phone", "address", "units", "daily", "lasts"), show="headings", height=8)
        self.tree_patients.heading("id", text="ID")
        self.tree_patients.heading("name", text="اسم العميل")
        self.tree_patients.heading("phone", text="الموبايل")
        self.tree_patients.heading("address", text="العنوان")
        self.tree_patients.heading("units", text="الوحدات")
        self.tree_patients.heading("daily", text="الاستهلاك")
        self.tree_patients.heading("lasts", text="يكفي (يوم)")
        self.tree_patients.column("id", width=25, anchor="center")
        self.tree_patients.column("name", width=110, anchor="e")
        self.tree_patients.column("phone", width=90, anchor="center")
        self.tree_patients.column("address", width=100, anchor="e")
        self.tree_patients.column("units", width=50, anchor="center")
        self.tree_patients.column("daily", width=60, anchor="center")
        self.tree_patients.column("lasts", width=70, anchor="center")
        self.tree_patients.pack(fill="x", padx=10, pady=2)
        self.tree_patients.bind("<<TreeviewSelect>>", self.on_patient_select)

        # التنبيهات والواتساب
        ttk.Label(right_frame, text="🔔 تنبيهات قرب انتهاء الأدوية (قبلها بـ يومين)", style="SubHeader.TLabel").pack(anchor="ne", padx=10, pady=(10, 2))
        
        self.tree_reminders = ttk.Treeview(right_frame, columns=("pname", "pphone", "med_name", "days_left", "status"), show="headings", height=6)
        self.tree_reminders.heading("pname", text="العميل")
        self.tree_reminders.heading("pphone", text="الموبايل")
        self.tree_reminders.heading("med_name", text="الدواء")
        self.tree_reminders.heading("days_left", text="متبقي (يوم)")
        self.tree_reminders.heading("status", text="الحالة")
        self.tree_reminders.column("pname", width=110, anchor="e")
        self.tree_reminders.column("pphone", width=90, anchor="center")
        self.tree_reminders.column("med_name", width=130, anchor="e")
        self.tree_reminders.column("days_left", width=70, anchor="center")
        self.tree_reminders.column("status", width=90, anchor="center")
        self.tree_reminders.pack(fill="x", padx=10, pady=2)

        rem_btn_box = tk.Frame(right_frame, bg="#ffffff")
        rem_btn_box.pack(fill="x", padx=10, pady=5)

        tk.Button(rem_btn_box, text="💬 فتح واتساب ويب وتنبيه العميل", bg="#25D366", fg="white", font=("Segoe UI", 9, "bold"), command=self.send_whatsapp_msg, relief="flat", pady=4).pack(side="right", expand=True, fill="x", padx=2)
        tk.Button(rem_btn_box, text="💤 غفوة لمدة يوم", bg="#ffa000", fg="white", font=("Segoe UI", 9, "bold"), command=self.snooze_reminder, relief="flat", pady=4).pack(side="right", expand=True, fill="x", padx=2)
        tk.Button(rem_btn_box, text="🛑 إيقاف التنبيه نهائياً", bg="#c62828", fg="white", font=("Segoe UI", 9, "bold"), command=self.stop_reminder, relief="flat", pady=4).pack(side="left", expand=True, fill="x", padx=2)

    def build_print_tab(self):
        panel = tk.Frame(self.tab_print, bg="#ffffff", bd=1, relief="solid")
        panel.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(panel, text="🖨️ طباعة الجرعة والاستيكر السريع", style="SubHeader.TLabel").pack(anchor="ne", padx=15, pady=10)

        printer_config_box = tk.Frame(panel, bg="#f0f4f8", bd=1, relief="solid")
        printer_config_box.pack(fill="x", padx=15, pady=10)
        
        self.lbl_current_printer = tk.Label(printer_config_box, text=f"الطابعة الحالية المتبناة للبرنامج: {load_printer_config() or 'طابعة النظام الافتراضية'}", bg="#f0f4f8", font=("Segoe UI", 9, "bold"))
        self.lbl_current_printer.pack(side="right", padx=10, pady=10)
        tk.Button(printer_config_box, text="⚙️ تعيين واختيار طابعة الاستيكرات", bg="#0056b3", fg="white", font=("Segoe UI", 9, "bold"), command=self.select_and_save_printer, relief="flat").pack(side="left", padx=10, pady=10)

        form_box = tk.Frame(panel, bg="#ffffff")
        form_box.pack(fill="x", padx=15, pady=15)

        tk.Label(form_box, text="اسم الدواء:", bg="#ffffff", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, sticky="e", pady=5)
        self.entry_quick_mname = ttk.Entry(form_box, width=35, justify="right", font=("Segoe UI", 11))
        self.entry_quick_mname.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        tk.Label(form_box, text="الجرعة / الاستخدام:", bg="#ffffff", font=("Segoe UI", 10, "bold")).grid(row=1, column=1, sticky="e", pady=5)
        self.entry_quick_dosage = ttk.Entry(form_box, width=35, justify="right", font=("Segoe UI", 11))
        self.entry_quick_dosage.insert(0, "قرص 3 مرات يومياً بعد الأكل")
        self.entry_quick_dosage.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        tk.Button(panel, text="🖨️ طباعة الاستيكر الآن", bg="#ff9800", fg="black", font=("Segoe UI", 12, "bold"), command=self.print_quick_sticker, relief="flat", pady=10).pack(fill="x", padx=15, pady=20)

    def build_med_db_tab(self):
        panel = tk.Frame(self.tab_med_db, bg="#ffffff", bd=1, relief="solid")
        panel.pack(fill="both", expand=True, padx=10, pady=10)

        db_form_box = tk.LabelFrame(panel, text=" إضافة أو تعديل بيانات دواء منفصلة ", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg=self.primary_blue)
        db_form_box.pack(fill="x", padx=10, pady=10)

        grid_f = tk.Frame(db_form_box, bg="#ffffff")
        grid_f.pack(fill="x", padx=10, pady=10)

        tk.Label(grid_f, text="اسم الدواء:", bg="#ffffff").grid(row=0, column=7, sticky="e")
        self.entry_db_name = ttk.Entry(grid_f, width=18, justify="right")
        self.entry_db_name.grid(row=0, column=6, padx=2)

        tk.Label(grid_f, text="الشكل:", bg="#ffffff").grid(row=0, column=5, sticky="e")
        self.combo_db_form = ttk.Combobox(grid_f, values=DRUG_FORMS, width=12, justify="right")
        self.combo_db_form.set(DRUG_FORMS[0])
        self.combo_db_form.grid(row=0, column=4, padx=2)

        tk.Label(grid_f, text="الجرعة:", bg="#ffffff").grid(row=0, column=3, sticky="e")
        self.entry_db_use = ttk.Entry(grid_f, width=18, justify="right")
        self.entry_db_use.grid(row=0, column=2, padx=2)

        tk.Label(grid_f, text="الدرج:", bg="#ffffff").grid(row=0, column=1, sticky="e")
        self.entry_db_drawer = ttk.Entry(grid_f, width=10, justify="right")
        self.entry_db_drawer.insert(0, "درج 1")
        self.entry_db_drawer.grid(row=0, column=0, padx=2)

        db_btn_box = tk.Frame(db_form_box, bg="#ffffff")
        db_btn_box.pack(fill="x", padx=10, pady=5)

        tk.Button(db_btn_box, text="+ حفظ بالاعدة", bg=self.primary_blue, fg="white", font=("Segoe UI", 9, "bold"), command=self.add_med_to_db, relief="flat").pack(side="right", padx=5)
        tk.Button(db_btn_box, text="تعديل الدواء المحدد", bg="#f57c00", fg="white", font=("Segoe UI", 9, "bold"), command=self.update_db_med, relief="flat").pack(side="right", padx=5)
        tk.Button(db_btn_box, text="حذف", bg="#c62828", fg="white", font=("Segoe UI", 9, "bold"), command=self.delete_db_med, relief="flat").pack(side="left", padx=5)

        search_f = tk.Frame(panel, bg="#ffffff")
        search_f.pack(fill="x", padx=10, pady=5)
        tk.Label(search_f, text="🔍 بحث في الأدوية:", bg="#ffffff", font=("Segoe UI", 9, "bold")).pack(side="right", padx=5)
        self.entry_db_search = ttk.Entry(search_f, justify="right", width=30)
        self.entry_db_search.pack(side="right", padx=5)
        self.entry_db_search.bind("<KeyRelease>", self.filter_all_meds_db)

        self.tree_db = ttk.Treeview(panel, columns=("id", "name", "form", "use_case", "drawer"), show="headings", height=12)
        self.tree_db.heading("id", text="ID")
        self.tree_db.heading("name", text="اسم الدواء")
        self.tree_db.heading("form", text="الشكل")
        self.tree_db.heading("use_case", text="الاستخدام / الجرعة")
        self.tree_db.heading("drawer", text="الدرج")
        self.tree_db.column("id", width=35, anchor="center")
        self.tree_db.column("name", width=200, anchor="e")
        self.tree_db.column("form", width=100, anchor="e")
        self.tree_db.column("use_case", width=250, anchor="e")
        self.tree_db.column("drawer", width=100, anchor="center")
        self.tree_db.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree_db.bind("<<TreeviewSelect>>", self.on_db_med_select)

    def select_and_save_printer(self):
        # نافذة اختيار طابعة من النظام لحفظها وتثبيتها للبرنامج
        printers = ["طابعة الاستيكرات الافتراضية", "ZD410 / ZD220", "XP-365B Thermal", "Microsoft Print to PDF"]
        top = tk.Toplevel(self)
        top.title("اختر الطابعة")
        top.geometry("350x200")
        top.configure(bg="#ffffff")
        
        tk.Label(top, text="اختر الطابعة المعتمدة للبرنامج:", font=("Segoe UI", 10, "bold"), bg="#ffffff").pack(pady=10)
        combo = ttk.Combobox(top, values=printers, width=30, justify="center")
        combo.set(load_printer_config() or printers[0])
        combo.pack(pady=10)
        
        def save_chosen():
            chosen = combo.get()
            save_printer_config(chosen)
            self.lbl_current_printer.config(text=f"الطابعة الحالية المتبناة للبرنامج: {chosen}")
            top.destroy()
            messagebox.showinfo("تم", "تم تعيين طابعة البرنامج بنجاح ولن تتغير حتى تقوم بتعديلها.")
            
        tk.Button(top, text="حفظ الطابعة", bg=self.primary_blue, fg="white", font=("Segoe UI", 9, "bold"), command=save_chosen, relief="flat").pack(pady=10)

    def load_patients(self):
        for row in self.tree_patients.get_children():
            self.tree_patients.delete(row)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone, address, units, daily_use FROM patients ORDER BY id DESC")
        for row in cursor.fetchall():
            p_id, name, phone, address, units, daily = row
            lasts = int(units / daily) if daily > 0 else 0
            self.tree_patients.insert("", "end", values=(p_id, name, phone, address, units, daily, f"{lasts} يوم"))
        conn.close()

    def add_patient(self):
        name = self.entry_pname.get().strip()
        phone = self.entry_pphone.get().strip()
        address = self.entry_paddress.get().strip()
        try:
            units = int(self.entry_punits.get().strip())
            daily = float(self.entry_pydaily.get().strip())
        except ValueError:
            messagebox.showwarning("خطأ", "يجب أن تكون الوحدات والاستهلاك أرقاماً صحيحة أو عشرية!")
            return

        if not name or not phone:
            messagebox.showwarning("تنبيه", "اكتب اسم العميل ورقم الموبايل!")
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO patients (name, phone, address, units, daily_use) VALUES (?, ?, ?, ?, ?)",
                       (name, phone, address, units, daily))
        conn.commit()
        conn.close()
        self.load_patients()
        self.load_reminders()

    def update_patient(self):
        if not self.selected_patient_id:
            messagebox.showwarning("تنبيه", "اختر عميلاً من الجدول لتعديل بياناته!")
            return
        name = self.entry_pname.get().strip()
        phone = self.entry_pphone.get().strip()
        address = self.entry_paddress.get().strip()
        try:
            units = int(self.entry_punits.get().strip())
            daily = float(self.entry_pydaily.get().strip())
        except ValueError:
            messagebox.showwarning("خطأ", "قيم الوحدات والاستهلاك غير صالحة!")
            return

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE patients SET name=?, phone=?, address=?, units=?, daily_use=? WHERE id=?",
                       (name, phone, address, units, daily, self.selected_patient_id))
        conn.commit()
        conn.close()
        self.load_patients()
        self.load_reminders()
        messagebox.showinfo("تم", "تم تحديث بيانات العميل بنجاح.")

    def delete_patient(self):
        if not self.selected_patient_id: return
        if messagebox.askyesno("تأكيد", "هل تريد حذف العميل نهائياً؟"):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM patients WHERE id=?", (self.selected_patient_id,))
            conn.commit()
            conn.close()
            self.load_patients()
            self.load_reminders()

    def on_patient_select(self, event):
        sel = self.tree_patients.selection()
        if not sel: return
        item = self.tree_patients.item(sel[0])["values"]
        self.selected_patient_id = item[0]
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, phone, address, units, daily_use FROM patients WHERE id=?", (self.selected_patient_id,))
        p = cursor.fetchone()
        conn.close()

        if p:
            self.entry_pname.delete(0, tk.END)
            self.entry_pname.insert(0, str(p[0]))
            self.entry_pphone.delete(0, tk.END)
            self.entry_pphone.insert(0, str(p[1]))
            self.entry_paddress.delete(0, tk.END)
            self.entry_paddress.insert(0, str(p[2]))
            self.entry_punits.delete(0, tk.END)
            self.entry_punits.insert(0, str(p[3]))
            self.entry_pydaily.delete(0, tk.END)
            self.entry_pydaily.insert(0, str(p[4]))

        self.load_patient_meds(self.selected_patient_id)

    def load_patient_meds(self, patient_id):
        for row in self.tree_meds.get_children():
            self.tree_meds.delete(row)
        if not patient_id: return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, med_name, dosage FROM medications WHERE patient_id = ?", (patient_id,))
        for row in cursor.fetchall():
            self.tree_meds.insert("", "end", values=row)
        conn.close()

    def add_medication(self):
        if not self.selected_patient_id:
            messagebox.showwarning("تنبيه", "اختر العميل أولاً!")
            return
        mname = self.entry_mname.get().strip()
        dosage = self.entry_mdosage.get().strip()
        if not mname: return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO medications (patient_id, med_name, dosage, start_date, duration_days) VALUES (?, ?, ?, ?, ?)",
                       (self.selected_patient_id, mname, dosage, datetime.date.today().strftime("%Y-%m-%d"), 30))
        conn.commit()
        conn.close()
        self.load_patient_meds(self.selected_patient_id)

    def delete_medication(self):
        sel = self.tree_meds.selection()
        if not sel: return
        med_id = self.tree_meds.item(sel[0])["values"][0]
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM medications WHERE id=?", (med_id,))
        conn.commit()
        conn.close()
        self.load_patient_meds(self.selected_patient_id)

    def load_reminders(self):
        for row in self.tree_reminders.get_children():
            self.tree_reminders.delete(row)
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone, units, daily_use, alert_status, snooze_date FROM patients")
        patients = cursor.fetchall()
        
        today = datetime.date.today()
        for p in patients:
            p_id, name, phone, units, daily, status, snooze = p
            if status == 'stopped':
                continue
            if status == 'snoozed' and snooze:
                try:
                    s_date = datetime.datetime.strptime(snooze, "%Y-%m-%d").date()
                    if today < s_date:
                        continue # في فترة الغفوة
                except:
                    pass

            lasts = int(units / daily) if daily > 0 else 0
            # تنبيه لو الدواء يكفي يومين أو أقل
            if lasts <= 2:
                # جلب دواء للعميل
                cursor.execute("SELECT med_name FROM medications WHERE patient_id=?", (p_id,))
                m_row = cursor.fetchone()
                m_name = m_row[0] if m_row else "دواء عام"
                
                self.tree_reminders.insert("", "end", values=(name, phone, m_name, f"{lasts} يوم", "تنبيه استهلاك"))
        conn.close()

    def snooze_reminder(self):
        sel = self.tree_reminders.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "اختر تنبيهاً لعمل غفوة له!")
            return
        item = self.tree_reminders.item(sel[0])["values"]
        pname = item[0]
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE patients SET alert_status='snoozed', snooze_date=? WHERE name=?", (tomorrow, pname))
        conn.commit()
        conn.close()
        self.load_reminders()
        messagebox.showinfo("تم", "تم عمل غفوة للتنبيه لمدة يوم.")

    def stop_reminder(self):
        sel = self.tree_reminders.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "اختر تنبيهاً لإيقافه!")
            return
        item = self.tree_reminders.item(sel[0])["values"]
        pname = item[0]
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE patients SET alert_status='stopped' WHERE name=?", (pname,))
        conn.commit()
        conn.close()
        self.load_reminders()
        messagebox.showinfo("تم", "تم إيقاف التنبيه لهذا العميل تماماً.")

    def send_whatsapp_msg(self):
        sel = self.tree_reminders.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "اختر عميلاً من جدول التنبيهات لإرسال رسالة له!")
            return
        item = self.tree_reminders.item(sel[0])["values"]
        pname, pphone, med_name = item[0], item[1], item[2]
        
        clean_phone = str(pphone).strip().replace(" ", "")
        if clean_phone.startswith("0"): clean_phone = "20" + clean_phone[1:]
        
        msg = f"مرحباً {pname} 🌿\nتذكير من صيدلية سرحان بأن دواء ({med_name}) الخاص بكم يوشك على الانتهاء خلال يومين. ننتظر زيارتكم لتجديد الدواء."
        url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={urllib.parse.quote(msg)}"
        
        # فتح صفحة جوجل / واتساب ويب كما طلبت
        webbrowser.open("https://web.whatsapp.com/")
        # أو فتح محادثة العميل مباشرة:
        webbrowser.open(url)

    def print_quick_sticker(self):
        mname = self.entry_quick_mname.get().strip()
        dosage = self.entry_quick_dosage.get().strip()
        if not mname:
            messagebox.showwarning("تنبيه", "اكتب اسم الدواء أولاً!")
            return
        sticker_text = f"صيدلية سرحان 🌿\n{mname}\n{dosage}\n☀️ 🌙 🍽️"
        send_to_zd_printer(sticker_text)

    def load_all_meds_db(self, query=""):
        for row in self.tree_db.get_children():
            self.tree_db.delete(row)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if query:
            q = f"%{query}%"
            cursor.execute("SELECT id, name, form, use_case, drawer_location FROM all_medications WHERE name LIKE ? OR drawer_location LIKE ?", (q, q))
        else:
            cursor.execute("SELECT id, name, form, use_case, drawer_location FROM all_medications ORDER BY name ASC")
        for row in cursor.fetchall():
            self.tree_db.insert("", "end", values=row)
        conn.close()

    def filter_all_meds_db(self, event=None):
        self.load_all_meds_db(self.entry_db_search.get().strip())

    def on_db_med_select(self, event):
        sel = self.tree_db.selection()
        if not sel: return
        item = self.tree_db.item(sel[0])["values"]
        self.selected_db_med_id = item[0]
        self.entry_db_name.delete(0, tk.END)
        self.entry_db_name.insert(0, str(item[1]))
        self.combo_db_form.set(str(item[2]))
        self.entry_db_use.delete(0, tk.END)
        self.entry_db_use.insert(0, str(item[3]))
        self.entry_db_drawer.delete(0, tk.END)
        self.entry_db_drawer.insert(0, str(item[4]))

    def add_med_to_db(self):
        name = self.entry_db_name.get().strip()
        if not name:
            messagebox.showwarning("تنبيه", "اكتب اسم الدواء!")
            return
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO all_medications (name, form, use_case, drawer_location) VALUES (?, ?, ?, ?)",
                           (name, self.combo_db_form.get().strip(), self.entry_db_use.get().strip(), self.entry_db_drawer.get().strip()))
            conn.commit()
            conn.close()
            self.load_all_meds_db()
            messagebox.success = messagebox.showinfo("تم", "تم حفظ الدواء في القاعدة بنجاح.")
        except sqlite3.IntegrityError:
            messagebox.showerror("خطأ", "هذا الدواء مسجل مسبقاً!")

    def update_db_med(self):
        if not self.selected_db_med_id:
            messagebox.showwarning("تنبيه", "اختر دواء من الجدول لتعديله!")
            return
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE all_medications SET name=?, form=?, use_case=?, drawer_location=? WHERE id=?",
                       (self.entry_db_name.get().strip(), self.combo_db_form.get().strip(), self.entry_db_use.get().strip(), self.entry_db_drawer.get().strip(), self.selected_db_med_id))
        conn.commit()
        conn.close()
        self.load_all_meds_db()
        messagebox.showinfo("تم", "تم تعديل بيانات الدواء بنجاح.")

    def delete_db_med(self):
        if not self.selected_db_med_id: return
        if messagebox.askyesno("تأكيد", "حذف هذا الدواء من القاعدة؟"):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM all_medications WHERE id=?", (self.selected_db_med_id,))
            conn.commit()
            conn.close()
            self.load_all_meds_db()

if __name__ == "__main__":
    init_db()
    app = PharmacyApp()
    app.mainloop()
