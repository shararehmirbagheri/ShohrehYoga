from pathlib import Path

main_content = r'''from datetime import date
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display

from kivy.app import App
from kivy.core.text import LabelBase
from kivy.lang import Builder
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from database import Database

BASE_DIR = Path(__file__).resolve().parent
FONT_FILE = BASE_DIR / "fonts" / "Vazirmatn-Regular.ttf"
KV_FILE = BASE_DIR / "kv" / "main.kv"
RTL_MARK = "\u200f"

if not FONT_FILE.exists():
    raise FileNotFoundError(f"Font file not found: {FONT_FILE}")

LabelBase.register(name="Persian", fn_regular=str(FONT_FILE))


def display_persian(text):
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)


def format_dates(dates):
    if not dates:
        return "-"
    if len(dates) <= 4:
        return ", ".join(dates)
    return ", ".join(dates[:4]) + " ..."


class HomeScreen(Screen):
    pass


class StudentListScreen(Screen):
    student_list = ObjectProperty(None)
    student_count = ObjectProperty(None)

    def on_enter(self):
        self.load_students()

    def load_students(self):
        self.student_list.clear_widgets()
        db = Database()
        students = db.get_student_summaries()
        self.student_count.text = f"Students: {len(students)}"

        for student in students:
            row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            row.add_widget(Label(text=display_persian(student["name"]), font_name="Persian", size_hint_x=0.22))
            row.add_widget(Label(text=student["phone"] or "-", font_name="Persian", size_hint_x=0.18))
            row.add_widget(Label(text=str(student["sessions"]), font_name="Persian", size_hint_x=0.10))
            row.add_widget(Label(text=format_dates(student["dates"]), font_name="Persian", size_hint_x=0.30))
            row.add_widget(Label(text=student["status"], font_name="Persian", color=(1, 0, 0, 1) if student["status"] == "Red" else (0, 0.8, 0, 1), size_hint_x=0.12))
            row.add_widget(Label(text=student["paid_info"], font_name="Persian", size_hint_x=0.18))
            self.student_list.add_widget(row)

    def open_add_student(self):
        self.open_student_popup()

    def open_student_popup(self, student_id=None, current_name="", current_phone="", current_notes=""):
        is_editing = student_id is not None
        layout = BoxLayout(orientation="vertical", padding=15, spacing=10)
        title_label = Label(text="Edit Student" if is_editing else "Add New Student", font_name="Persian", font_size=22, size_hint_y=None, height=45)

        name_input = TextInput(
            text=current_name,
            hint_text="نام دانش‌آموز",
            font_name="Persian",
            font_size=20,
            multiline=False,
            size_hint_y=None,
            height=50,
            halign="right",
            base_direction="rtl",
            text_language="fa",
            padding=[12, 12, 12, 12]
        )

        phone_input = TextInput(
            text=current_phone,
            hint_text="Phone number",
            font_name="Persian",
            font_size=18,
            halign="left",
            base_direction="ltr",
            input_filter="int",
            multiline=False,
            size_hint_y=None,
            height=50,
            padding=[12, 12, 12, 12]
        )

        notes_input = TextInput(
            text=current_notes,
            hint_text="Notes",
            font_name="Persian",
            font_size=18,
            halign="right",
            base_direction="rtl",
            text_language="fa",
            multiline=True,
            size_hint_y=None,
            height=90,
            padding=[12, 12, 12, 12]
        )

        message_label = Label(text="", font_name="Persian", size_hint_y=None, height=30)
        button_row = BoxLayout(spacing=10, size_hint_y=None, height=50)
        cancel_button = Button(text="Cancel", font_name="Persian")
        save_button = Button(text="Save", font_name="Persian")
        button_row.add_widget(cancel_button)

        delete_button = None
        if is_editing:
            delete_button = Button(text="Delete", font_name="Persian", background_normal="", background_color=(0.75, 0.15, 0.15, 1))
            button_row.add_widget(delete_button)

        button_row.add_widget(save_button)
        layout.add_widget(title_label)
        layout.add_widget(name_input)
        layout.add_widget(phone_input)
        layout.add_widget(notes_input)
        layout.add_widget(message_label)
        layout.add_widget(button_row)

        popup = Popup(title="", content=layout, size_hint=(0.88, 0.75), auto_dismiss=False)

        def save_student(_instance):
            name = name_input.text.lstrip(RTL_MARK).strip()
            phone = phone_input.text.lstrip(RTL_MARK).strip()
            notes = notes_input.text.lstrip(RTL_MARK).strip()
            if not name:
                message_label.text = "Please enter a student name."
                return
            db = Database()
            if is_editing:
                db.update_student(student_id=student_id, name=name, phone=phone, notes=notes)
            else:
                db.add_student(name=name, phone=phone, notes=notes)
            popup.dismiss()
            self.load_students()

        def delete_student(_instance):
            db = Database()
            db.delete_student(student_id)
            popup.dismiss()
            self.load_students()

        save_button.bind(on_release=save_student)
        cancel_button.bind(on_release=lambda _instance: popup.dismiss())
        if delete_button:
            delete_button.bind(on_release=delete_student)
        popup.open()


class AttendanceScreen(Screen):
    attendance_list = ObjectProperty(None)

    def on_enter(self):
        self.load_attendance()

    def load_attendance(self):
        self.attendance_list.clear_widgets()
        db = Database()
        records = db.get_attendance_records()
        if not records:
            self.attendance_list.add_widget(Label(text="No attendance records yet.", font_name="Persian", size_hint_y=None, height=40))
            return
        for record in records:
            row = BoxLayout(size_hint_y=None, height=40, spacing=10)
            row.add_widget(Label(text=display_persian(record[1]), font_name="Persian", size_hint_x=0.50))
            row.add_widget(Label(text=record[2], font_name="Persian", size_hint_x=0.50))
            self.attendance_list.add_widget(row)

    def open_mark_attendance(self):
        db = Database()
        students = db.get_students()
        if not students:
            return
        spinner = Spinner(text="Select student", values=[f"{sid}:{name}" for sid, name in students], size_hint_y=None, height=50)
        layout = BoxLayout(orientation="vertical", padding=15, spacing=10)
        layout.add_widget(Label(text="Mark Attendance", font_name="Persian", font_size=22, size_hint_y=None, height=45))
        layout.add_widget(spinner)
        button_row = BoxLayout(spacing=10, size_hint_y=None, height=50)
        cancel_button = Button(text="Cancel", font_name="Persian")
        save_button = Button(text="Save", font_name="Persian")
        button_row.add_widget(cancel_button)
        button_row.add_widget(save_button)
        layout.add_widget(button_row)
        popup = Popup(title="", content=layout, size_hint=(0.88, 0.45), auto_dismiss=False)

        def save_attendance(_instance):
            if ":" not in spinner.text:
                return
            student_id = int(spinner.text.split(":", 1)[0])
            db.add_attendance(student_id)
            popup.dismiss()
            self.load_attendance()
            App.get_running_app().root.get_screen("students").load_students()

        save_button.bind(on_release=save_attendance)
        cancel_button.bind(on_release=lambda _instance: popup.dismiss())
        popup.open()

    def open_record_payment(self):
        db = Database()
        students = db.get_students()
        if not students:
            return
        spinner = Spinner(text="Select student", values=[f"{sid}:{name}" for sid, name in students], size_hint_y=None, height=50)
        sessions_input = TextInput(text="12", input_filter="int", font_name="Persian", halign="right", padding=[12, 12, 12, 12], multiline=False, size_hint_y=None, height=50)
        layout = BoxLayout(orientation="vertical", padding=15, spacing=10)
        layout.add_widget(Label(text="Record Payment", font_name="Persian", font_size=22, size_hint_y=None, height=45))
        layout.add_widget(spinner)
        layout.add_widget(sessions_input)
        button_row = BoxLayout(spacing=10, size_hint_y=None, height=50)
        cancel_button = Button(text="Cancel", font_name="Persian")
        save_button = Button(text="Save", font_name="Persian")
        button_row.add_widget(cancel_button)
        button_row.add_widget(save_button)
        layout.add_widget(button_row)
        popup = Popup(title="", content=layout, size_hint=(0.88, 0.55), auto_dismiss=False)

        def save_payment(_instance):
            if ":" not in spinner.text:
                return
            student_id = int(spinner.text.split(":", 1)[0])
            sessions = int(sessions_input.text.strip() or 0)
            if sessions <= 0:
                return
            db.add_payment(student_id, sessions)
            popup.dismiss()
            self.load_attendance()
            App.get_running_app().root.get_screen("students").load_students()

        save_button.bind(on_release=save_payment)
        cancel_button.bind(on_release=lambda _instance: popup.dismiss())
        popup.open()


class YogaApp(App):
    def build(self):
        return Builder.load_file(str(KV_FILE))


if __name__ == "__main__":
    YogaApp().run()
'''

kv_content = r'''ScreenManager:
    HomeScreen:
        name: "home"
    StudentListScreen:
        name: "students"
    AttendanceScreen:
        name: "attendance"

<HomeScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: 15
        spacing: 15

        Label:
            text: "Shohreh Yoga Attendance"
            font_name: "Persian"
            font_size: 32
            size_hint_y: None
            height: 70
            bold: True

        Button:
            text: "Student List"
            font_name: "Persian"
            font_size: 20
            size_hint_y: None
            height: 60
            background_normal: ""
            background_color: (.45, .25, .70, 1)
            on_release: root.manager.current = "students"

        Button:
            text: "Attendance List"
            font_name: "Persian"
            font_size: 20
            size_hint_y: None
            height: 60
            background_normal: ""
            background_color: (.20, .60, .35, 1)
            on_release: root.manager.current = "attendance"

<StudentListScreen>:
    student_list: student_list
    student_count: student_count

    BoxLayout:
        orientation: "vertical"
        padding: 15
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: 60
            spacing: 10

            Button:
                text: "Back"
                font_name: "Persian"
                size_hint_x: 0.3
                on_release: root.manager.current = "home"

            Button:
                text: "Add Student"
                font_name: "Persian"
                size_hint_x: 0.7
                on_release: root.open_add_student()

        Label:
            id: student_count
            text: "Students: 0"
            font_name: "Persian"
            font_size: 18
            size_hint_y: None
            height: 30

        BoxLayout:
            size_hint_y: None
            height: 40
            spacing: 6

            Label:
                text: "Name"
                font_name: "Persian"
                font_size: 16
                size_hint_x: 0.22
            Label:
                text: "Phone"
                font_name: "Persian"
                font_size: 16
                size_hint_x: 0.18
            Label:
                text: "Sessions"
                font_name: "Persian"
                font_size: 16
                size_hint_x: 0.10
            Label:
                text: "Dates"
                font_name: "Persian"
                font_size: 16
                size_hint_x: 0.30
            Label:
                text: "Status"
                font_name: "Persian"
                font_size: 16
                size_hint_x: 0.12
            Label:
                text: "Paid"
                font_name: "Persian"
                font_size: 16
                size_hint_x: 0.18

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                id: student_list

<AttendanceScreen>:
    attendance_list: attendance_list

    BoxLayout:
        orientation: "vertical"
        padding: 15
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: 60
            spacing: 10

            Button:
                text: "Back"
                font_name: "Persian"
                size_hint_x: 0.30
                on_release: root.manager.current = "home"

            Button:
                text: "Mark Attendance"
                font_name: "Persian"
                size_hint_x: 0.35
                on_release: root.open_mark_attendance()

            Button:
                text: "Record Payment"
                font_name: "Persian"
                size_hint_x: 0.35
                on_release: root.open_record_payment()

        BoxLayout:
            size_hint_y: None
            height: 40
            spacing: 6

            Label:
                text: "Student"
                font_name: "Persian"
                font_size: 16
                size_hint_x: 0.50
            Label:
                text: "Date"
                font_name: "Persian"
                font_size: 16
                size_hint_x: 0.50

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                id: attendance_list
'''

Path('main.py').write_text(main_content, encoding='utf-8')
Path('kv').mkdir(exist_ok=True)
Path('kv/main.kv').write_text(kv_content, encoding='utf-8')
print('rewrite complete')
