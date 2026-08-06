import arabic_reshaper
from bidi.algorithm import get_display

from kivy.graphics import Color, Rectangle
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from database import Database

RTL_MARK = "\u200f"


def display_persian(text):
    """Shape Persian/Arabic text correctly for Kivy labels."""
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(str(text))
    return get_display(reshaped_text)


class StudentRow(ButtonBehavior, BoxLayout):
    """Selectable, Excel-style student table row."""

    student_id = NumericProperty(0)
    selected = BooleanProperty(False)
    status = StringProperty("")
    remaining_sessions = NumericProperty(0)

    normal_color = ListProperty([1, 1, 1, 1])
    selected_color = ListProperty([0.78, 0.68, 0.95, 1])
    unpaid_color = ListProperty([1.00, 0.78, 0.78, 1])
    warning_color = ListProperty([1.00, 0.86, 0.62, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 42
        self.spacing = 1

        with self.canvas.before:
            self._background_color = Color(*self.normal_color)
            self._background_rectangle = Rectangle(pos=self.pos, size=self.size)

        self.bind(
            pos=self._update_background,
            size=self._update_background,
            selected=self._refresh_color,
            status=self._refresh_color,
            remaining_sessions=self._refresh_color,
        )

    def _update_background(self, *_):
        self._background_rectangle.pos = self.pos
        self._background_rectangle.size = self.size

    def _refresh_color(self, *_):
        if self.selected:
            color = self.selected_color
        elif self.status.lower() == "unpaid":
            color = self.unpaid_color
        elif 0 < self.remaining_sessions <= 3:
            color = self.warning_color
        else:
            color = self.normal_color

        self._background_color.rgba = color


class StudentListScreen(Screen):
    student_list = ObjectProperty(None)
    student_count = ObjectProperty(None)
    name_input = ObjectProperty(None)
    phone_input = ObjectProperty(None)
    notes_input = ObjectProperty(None)

    sort_column = StringProperty("name")
    sort_reverse = BooleanProperty(False)

    def on_enter(self):
        self.selected_student_id = None
        self.current_selected_row = None
        self.load_students()
        self.clear_form()

    def load_students(self):
        if not self.student_list:
            return

        self.student_list.clear_widgets()

        db = Database()
        self.students = db.get_student_summaries()
        self._normalize_student_data()
        self._sort_students_in_memory()

        if self.student_count:
            self.student_count.text = f"Students: {len(self.students)}"

        for student in self.students:
            self.student_list.add_widget(self._build_student_row(student))

    def _normalize_student_data(self):
        """
        Supports both the current database.py and an enhanced database.py.

        Preferred keys:
            payment_date
            sessions_paid
            sessions_used
            remaining_sessions
            paid_status
        """
        for student in self.students:
            paid_info = str(student.get("paid_info") or "-")
            status = str(student.get("paid_status") or student.get("status") or "Unpaid")

            payment_date = student.get("payment_date")
            sessions_paid = student.get("sessions_paid")
            sessions_used = student.get("sessions_used")
            remaining = student.get("remaining_sessions")

            if paid_info != "-" and "/" in paid_info:
                left, right = paid_info.split("/", 1)
                payment_date = payment_date or left.strip()
                if sessions_paid is None:
                    try:
                        sessions_paid = int(right.strip())
                    except ValueError:
                        sessions_paid = 0

            payment_date = payment_date or "-"
            sessions_paid = int(sessions_paid or 0)
            sessions_used = int(sessions_used or 0)

            if remaining is None:
                remaining = max(sessions_paid - sessions_used, 0)

            if status.lower() in {"red", "expired"}:
                status = "Unpaid"
            elif status.lower() not in {"paid", "unpaid"}:
                status = "Paid" if remaining > 0 else "Unpaid"

            student["payment_date"] = payment_date
            student["sessions_paid"] = sessions_paid
            student["sessions_used"] = sessions_used
            student["remaining_sessions"] = int(remaining)
            student["paid_status"] = status

    def sort_students(self, column):
        """Use from KV header buttons, e.g. root.sort_students("name")."""
        valid_columns = {
            "id",
            "name",
            "phone",
            "paid_status",
            "payment_date",
            "remaining_sessions",
        }
        if column not in valid_columns:
            return

        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False

        self.load_students()

    def _sort_students_in_memory(self):
        def sort_key(student):
            value = student.get(self.sort_column)
            if self.sort_column in {"id", "remaining_sessions"}:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return 0
            return str(value or "").casefold()

        self.students.sort(key=sort_key, reverse=self.sort_reverse)

    def _build_student_row(self, student):
        row = StudentRow(
            student_id=student["id"],
            status=student["paid_status"],
            remaining_sessions=student["remaining_sessions"],
        )

        row.bind(
            on_release=lambda instance, sid=student["id"]: self.select_student(
                sid, instance
            )
        )

        row.add_widget(self._cell(str(student["id"]), 0.08, "center"))
        row.add_widget(
            self._cell(display_persian(student["name"]), 0.25, "right")
        )
        row.add_widget(self._cell(student.get("phone") or "-", 0.17, "left"))
        row.add_widget(self._cell(student["paid_status"], 0.12, "center"))
        row.add_widget(self._cell(student["payment_date"], 0.18, "center"))
        row.add_widget(
            self._cell(str(student["remaining_sessions"]), 0.20, "center")
        )

        return row

    @staticmethod
    def _cell(text, size_hint_x, halign="left"):
        label = Label(
            text=str(text),
            font_name="Persian",
            font_size=14,
            color=(0.15, 0.12, 0.20, 1),
            size_hint_x=size_hint_x,
            halign=halign,
            valign="middle",
            padding=(8, 0),
        )
        label.bind(size=lambda instance, value: setattr(instance, "text_size", value))
        return label

    def select_student(self, student_id, row=None):
        if self.current_selected_row:
            self.current_selected_row.selected = False

        if row:
            row.selected = True
            self.current_selected_row = row

        student = Database().get_student(student_id)
        if not student:
            return

        _, name, phone, notes = student
        self.selected_student_id = student_id
        self.name_input.text = RTL_MARK + (name or "")
        self.phone_input.text = phone or ""
        self.notes_input.text = RTL_MARK + (notes or "")

    def clear_form(self):
        self.selected_student_id = None

        if getattr(self, "current_selected_row", None):
            self.current_selected_row.selected = False
            self.current_selected_row = None

        if self.name_input:
            self.name_input.text = ""
        if self.phone_input:
            self.phone_input.text = ""
        if self.notes_input:
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

        Database().update_student(
            student_id=self.selected_student_id,
            name=name,
            phone=phone,
            notes=notes,
        )
        self.load_students()
        self.clear_form()

    def delete_student(self):
        if not getattr(self, "selected_student_id", None):
            return

        Database().delete_student(self.selected_student_id)
        self.load_students()
        self.clear_form()
