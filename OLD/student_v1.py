import arabic_reshaper
from bidi.algorithm import get_display

from kivy.properties import BooleanProperty, ObjectProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from database import Database

RTL_MARK = "\u200f"


def display_persian(text):
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)


class StudentRow(ButtonBehavior, BoxLayout):
    student_id = None
    selected = BooleanProperty(False)


class StudentListScreen(Screen):
    student_list = ObjectProperty(None)
    student_count = ObjectProperty(None)
    name_input = ObjectProperty(None)
    phone_input = ObjectProperty(None)
    notes_input = ObjectProperty(None)

    def on_enter(self):
        self.selected_student_id = None
        self.load_students()
        self.clear_form()

    def load_students(self):
        self.student_list.clear_widgets()

        db = Database()
        self.students = db.get_student_summaries()
        self.student_count.text = f"Students: {len(self.students)}"

        for student in self.students:
            row = StudentRow(size_hint_y=None, height=42, spacing=8)
            row.student_id = student["id"]
            row.bind(on_release=lambda inst, sid=student["id"], row=row: self.select_student(sid, row))
            row.add_widget(Label(text=str(student["id"]), font_name="Persian", size_hint_x=0.10, halign="center", valign="middle"))
            row.add_widget(Label(text=display_persian(student["name"]), font_name="Persian", size_hint_x=0.35, halign="right", valign="middle"))
            row.add_widget(Label(text=student["phone"] or "-", font_name="Persian", size_hint_x=0.25, halign="left", valign="middle"))
            row.add_widget(Label(text=student["paid_info"], font_name="Persian", size_hint_x=0.30, halign="left", valign="middle"))
            self.student_list.add_widget(row)

    def select_student(self, student_id, row=None):
        if getattr(self, "current_selected_row", None):
            self.current_selected_row.selected = False
        if row:
            row.selected = True
            self.current_selected_row = row

        student = Database().get_student(student_id)
        if not student:
            return
        _, name, phone, notes = student
        self.selected_student_id = student_id
        self.name_input.text = RTL_MARK + name
        self.phone_input.text = phone
        self.notes_input.text = RTL_MARK + notes

    def clear_form(self):
        self.selected_student_id = None
        self.name_input.text = ""
        self.phone_input.text = ""
        self.notes_input.text = ""

    def add_student(self):
        name = self.name_input.text.lstrip(RTL_MARK).strip()
        phone = self.phone_input.text.strip()
        notes = self.notes_input.text.lstrip(RTL_MARK).strip()
        if not name:
            return
        Database().add_student(name=name, phone=phone, notes=notes)
        self.load_students()
        self.clear_form()

    def update_student(self):
        if not getattr(self, "selected_student_id", None):
            return
        name = self.name_input.text.lstrip(RTL_MARK).strip()
        phone = self.phone_input.text.strip()
        notes = self.notes_input.text.lstrip(RTL_MARK).strip()
        if not name:
            return
        Database().update_student(student_id=self.selected_student_id, name=name, phone=phone, notes=notes)
        self.load_students()
        self.clear_form()

    def delete_student(self):
        if not getattr(self, "selected_student_id", None):
            return
        Database().delete_student(self.selected_student_id)
        self.load_students()
        self.clear_form()
