from pathlib import Path

from datetime import date

from kivy.app import App
from kivy.core.text import LabelBase
from kivy.lang import Builder
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.behaviors import ButtonBehavior

from database import Database
from student import StudentListScreen, display_persian


BASE_DIR = Path(__file__).resolve().parent
FONT_FILE = BASE_DIR / "fonts" / "Vazirmatn-Regular.ttf"
KV_FILE = BASE_DIR / "kv" / "main.kv"
RTL_MARK = "\u200f"

if not FONT_FILE.exists():
    raise FileNotFoundError(f"Font file not found: {FONT_FILE}")

LabelBase.register(
    name="Persian",
    fn_regular=str(FONT_FILE)
)


class HomeScreen(Screen):
    pass


class ReportScreen(Screen):
    pass


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
            row = BoxLayout(size_hint_y=None, height=40, spacing=8)
            row.add_widget(Label(text=display_persian(record[1]), font_name="Persian", size_hint_x=0.40, halign="left", valign="middle"))
            row.add_widget(Label(text=record[2], font_name="Persian", size_hint_x=0.30, halign="center", valign="middle"))
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
        sessions_input = TextInput(text="12", input_filter="int", font_name="Persian", halign="right", padding=(12, 10), multiline=False, size_hint_y=None, height=50)
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

    def open_student_popup(
        self,
        student_id=None,
        current_name="",
        current_phone="",
        current_notes=""
    ):
        is_editing = student_id is not None

        layout = BoxLayout(
            orientation="vertical",
            padding=15,
            spacing=10
        )

        title_label = Label(
            text="Edit Student" if is_editing else "Add New Student",
            font_name="Persian",
            font_size=22,
            size_hint_y=None,
            height=45
        )

        name_input = TextInput(
            text=current_name,
            hint_text="Student name",
            font_name="Persian",
            font_size=20,
            halign="right",
            padding=(12, 10),
            multiline=False,
            size_hint_y=None,
            height=50
        )

        phone_input = TextInput(
            text=current_phone,
            hint_text="Phone number",
            font_name="Persian",
            font_size=18,
            halign="right",
            padding=(12, 10),
            multiline=False,
            size_hint_y=None,
            height=50
        )

        notes_input = TextInput(
            text=current_notes,
            hint_text="Notes",
            font_name="Persian",
            font_size=18,
            halign="right",
            padding=(12, 10),
            multiline=True,
            size_hint_y=None,
            height=90
        )

        # Ensure the input is treated as RTL when displaying Persian text
        for input_widget in (name_input, phone_input, notes_input):
            if input_widget.text:
                input_widget.text = RTL_MARK + input_widget.text

        message_label = Label(
            text="",
            font_name="Persian",
            size_hint_y=None,
            height=30
        )

        button_row = BoxLayout(
            spacing=10,
            size_hint_y=None,
            height=50
        )

        cancel_button = Button(
            text="Cancel",
            font_name="Persian"
        )

        save_button = Button(
            text="Save",
            font_name="Persian"
        )

        button_row.add_widget(cancel_button)

        delete_button = None

        if is_editing:
            delete_button = Button(
                text="Delete",
                font_name="Persian",
                background_normal="",
                background_color=(0.75, 0.15, 0.15, 1)
            )

            button_row.add_widget(delete_button)

        button_row.add_widget(save_button)

        layout.add_widget(title_label)
        layout.add_widget(name_input)
        layout.add_widget(phone_input)
        layout.add_widget(notes_input)
        layout.add_widget(message_label)
        layout.add_widget(button_row)

        popup = Popup(
            title="",
            content=layout,
            size_hint=(0.88, 0.75),
            auto_dismiss=False
        )

        def save_student(_instance):
            name = name_input.text.lstrip(RTL_MARK).strip()
            phone = phone_input.text.lstrip(RTL_MARK).strip()
            notes = notes_input.text.lstrip(RTL_MARK).strip()

            if not name:
                message_label.text = "Please enter a student name."
                return

            db = Database()

            if is_editing:
                db.update_student(
                    student_id=student_id,
                    name=name,
                    phone=phone,
                    notes=notes
                )
            else:
                db.add_student(
                    name=name,
                    phone=phone,
                    notes=notes
                )

            popup.dismiss()
            self.load_students()

        def delete_student(_instance):
            db = Database()
            db.delete_student(student_id)

            popup.dismiss()
            self.load_students()

        save_button.bind(on_release=save_student)
        cancel_button.bind(
            on_release=lambda _instance: popup.dismiss()
        )

        if delete_button:
            delete_button.bind(on_release=delete_student)

        popup.open()

from pathlib import Path
from kivy.core.text import LabelBase

BASE_DIR = Path(__file__).resolve().parent

LabelBase.register(
    name="Persian",
    fn_regular=str(BASE_DIR / "fonts" / "Vazirmatn-Regular.ttf"),
)
class YogaApp(App):
    def build(self):
        return Builder.load_file(str(KV_FILE))


if __name__ == "__main__":
    YogaApp().run()