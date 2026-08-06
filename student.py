import arabic_reshaper
from bidi.algorithm import get_display

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
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
from kivy.uix.textinput import TextInput

from database import Database
from jalali_calendar import (
    gregorian_iso_to_jalali_display,
    open_jalali_date_picker,
)


def display_persian(text):
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))


class PersianTextInput(TextInput):
    logical_text = StringProperty("")

    def set_logical_text(self, value):
        self.logical_text = str(value or "")
        self._render()

    def get_logical_text(self):
        return self.logical_text

    def insert_text(self, substring, from_undo=False):
        if self.readonly:
            return
        self.logical_text += str(substring)
        self._render()

    def do_backspace(self, from_undo=False, mode="bkspc"):
        if self.readonly or not self.logical_text:
            return
        self.logical_text = self.logical_text[:-1]
        self._render()

    def _render(self):
        self.text = display_persian(self.logical_text)
        self.cursor = (len(self.text), 0)


class StudentRow(ButtonBehavior, BoxLayout):
    student_id = NumericProperty(0)
    selected = BooleanProperty(False)
    receipt = StringProperty("No")
    remaining_sessions = NumericProperty(0)
    row_index = NumericProperty(0)

    selected_color = ListProperty([0.82, 0.74, 0.96, 1])
    danger_color = ListProperty([1.00, 0.78, 0.78, 1])
    warning_color = ListProperty([1.00, 0.90, 0.55, 1])
    even_color = ListProperty([1.00, 1.00, 1.00, 1])
    odd_color = ListProperty([0.97, 0.95, 0.99, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 42
        self.spacing = 0

        with self.canvas.before:
            self._bg_color = Color(*self.even_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            Color(0.80, 0.76, 0.86, 1)
            self._border = Line(points=[], width=0.7)

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            selected=self._refresh_color,
            receipt=self._refresh_color,
            remaining_sessions=self._refresh_color,
            row_index=self._refresh_color,
        )
        self._refresh_color()

    def _update_canvas(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border.points = [
            self.x, self.y, self.right, self.y, self.right,
            self.top, self.x, self.top, self.x, self.y
        ]

    def _refresh_color(self, *_):
        if self.selected:
            color = self.selected_color
        elif self.receipt == "No" or self.remaining_sessions <= 0:
            color = self.danger_color
        elif self.remaining_sessions <= 3:
            color = self.warning_color
        else:
            color = self.even_color if self.row_index % 2 == 0 else self.odd_color
        self._bg_color.rgba = color


class StudentListScreen(Screen):
    student_list = ObjectProperty(None)
    student_count = ObjectProperty(None)
    name_input = ObjectProperty(None)
    phone_input = ObjectProperty(None)
    notes_input = ObjectProperty(None)
    receipt_input = ObjectProperty(None)
    first_session_input = ObjectProperty(None)
    sessions_paid_input = ObjectProperty(None)
    used_value = ObjectProperty(None)
    remaining_value = ObjectProperty(None)
    search_input = ObjectProperty(None)

    sort_column = StringProperty("name")
    sort_reverse = BooleanProperty(False)
    filter_status = StringProperty("All")

    def on_enter(self):
        self.clear_form()
        Clock.schedule_once(lambda *_: self.load_students(), 0)

    def schedule_search(self, *_):
        Clock.unschedule(self._run_search)
        Clock.schedule_once(self._run_search, 0.15)

    def _run_search(self, *_):
        self.load_students()

    def load_students(self):
        if not self.student_list:
            return

        students = Database().get_student_summaries()

        if self.search_input and hasattr(self.search_input, "get_logical_text"):
            query = self.search_input.get_logical_text().strip().casefold()
        else:
            query = (self.search_input.text if self.search_input else "").strip().casefold()

        if query:
            students = [
                row for row in students
                if query in str(row["id"]).casefold()
                or query in str(row["name"]).casefold()
                or query in str(row["phone"]).casefold()
            ]

        if self.filter_status == "Receipt Yes":
            students = [row for row in students if row["receipt"] == "Yes"]
        elif self.filter_status == "Receipt No":
            students = [row for row in students if row["receipt"] == "No"]
        elif self.filter_status == "Renew Soon":
            students = [
                row for row in students
                if 0 < row["remaining_sessions"] <= 3
            ]
        elif self.filter_status == "Zero or Negative":
            students = [
                row for row in students
                if row["remaining_sessions"] <= 0
            ]

        students.sort(key=self._sort_key, reverse=self.sort_reverse)
        self.students = students

        self.student_list.clear_widgets()
        self.student_count.text = f"Students: {len(students)}"

        for index, student in enumerate(students):
            self.student_list.add_widget(self._build_row(student, index))

    def _sort_key(self, row):
        value = row.get(self.sort_column)
        if self.sort_column in {
            "id", "sessions_paid", "sessions_used", "remaining_sessions"
        }:
            return int(value or 0)
        return str(value or "").casefold()

    def sort_students(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.load_students()

    def set_filter(self, status):
        self.filter_status = status
        self.load_students()

    def _build_row(self, student, index):
        row = StudentRow(
            student_id=student["id"],
            receipt=student["receipt"],
            remaining_sessions=student["remaining_sessions"],
            row_index=index,
        )
        row.bind(
            on_release=lambda instance, sid=student["id"]:
            self.select_student(sid, instance)
        )

        first_date = (
            gregorian_iso_to_jalali_display(student["first_session_date"])
            if student["first_session_date"]
            else "*"
        )

        values = (
            str(student["id"]),
            display_persian(student["name"]),
            student["receipt"],
            first_date,
            str(student["sessions_paid"]),
            str(student["sessions_used"]),
            str(student["remaining_sessions"]),
            student["phone"] or "-",
            display_persian(student["notes"]) if student["notes"] else "-",
        )
        widths = (0.05, 0.20, 0.08, 0.14, 0.08, 0.08, 0.09, 0.12, 0.16)
        aligns = (
            "center",
            "right",
            "center",
            "center",
            "center",
            "center",
            "center",
            "left",
            "right",
        )

        for value, width, align in zip(values, widths, aligns):
            label = Label(
                text=value,
                font_name="Persian",
                font_size=14,
                color=(0.16, 0.10, 0.23, 1),
                size_hint_x=width,
                halign=align,
                valign="middle",
                padding=(7, 0),
            )
            label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
            row.add_widget(label)

        return row

    def select_student(self, student_id, row=None):
        if getattr(self, "current_selected_row", None):
            self.current_selected_row.selected = False

        if row:
            row.selected = True
            self.current_selected_row = row

        summary = Database().get_student_summary(student_id)
        if not summary:
            return

        self.selected_student_id = student_id
        self.name_input.set_logical_text(summary["name"])
        self.phone_input.text = summary["phone"]
        self.notes_input.set_logical_text(summary["notes"])
        self.receipt_input.text = summary["receipt"]

        first_iso = summary["first_session_date"] or ""
        self.first_session_input.iso_date = first_iso
        self.first_session_input.text = (
            gregorian_iso_to_jalali_display(first_iso)
            if first_iso
            else ""
        )

        self.sessions_paid_input.text = str(summary["sessions_paid"] or "")
        self.used_value.text = str(summary["sessions_used"])
        self.remaining_value.text = str(summary["remaining_sessions"])

    def clear_form(self):
        self.selected_student_id = None

        if getattr(self, "current_selected_row", None):
            self.current_selected_row.selected = False
            self.current_selected_row = None

        if self.name_input:
            self.name_input.set_logical_text("")
        if self.phone_input:
            self.phone_input.text = ""
        if self.notes_input:
            self.notes_input.set_logical_text("")
        if self.receipt_input:
            self.receipt_input.text = "No"
        if self.first_session_input:
            self.first_session_input.text = ""
            self.first_session_input.iso_date = ""
        if self.sessions_paid_input:
            self.sessions_paid_input.text = ""
        if self.used_value:
            self.used_value.text = "0"
        if self.remaining_value:
            self.remaining_value.text = "0"

    def open_first_session_calendar(self):
        current_iso = getattr(self.first_session_input, "iso_date", "")

        def apply_date(gregorian_iso, jalali_display):
            self.first_session_input.iso_date = gregorian_iso
            self.first_session_input.text = jalali_display

        open_jalali_date_picker(
            current_gregorian_iso=current_iso,
            on_select=apply_date,
            title="انتخاب تاریخ جلسه اول",
        )

    def _save_payment(self, db, student_id):
        sessions_paid = int(self.sessions_paid_input.text.strip() or 0)
        first_session_date = getattr(self.first_session_input, "iso_date", "")
        db.save_payment(student_id, first_session_date, sessions_paid)

    def add_student(self):
        name = self.name_input.get_logical_text().strip()
        if not name:
            return

        first_session_date = getattr(self.first_session_input, "iso_date", "")
        db = Database()
        student_id = db.add_student(
            name=name,
            phone=self.phone_input.text.strip(),
            notes=self.notes_input.get_logical_text().strip(),
            receipt=self.receipt_input.text,
            first_session_date=first_session_date,
        )
        self._save_payment(db, student_id)
        self.clear_form()
        self.load_students()

    def update_student(self):
        if not getattr(self, "selected_student_id", None):
            return

        name = self.name_input.get_logical_text().strip()
        if not name:
            return

        first_session_date = getattr(self.first_session_input, "iso_date", "")
        db = Database()
        db.update_student(
            student_id=self.selected_student_id,
            name=name,
            phone=self.phone_input.text.strip(),
            notes=self.notes_input.get_logical_text().strip(),
            receipt=self.receipt_input.text,
            first_session_date=first_session_date,
        )
        self._save_payment(db, self.selected_student_id)
        self.clear_form()
        self.load_students()

    def delete_student(self):
        if not getattr(self, "selected_student_id", None):
            return

        Database().delete_student(self.selected_student_id)
        self.clear_form()
        self.load_students()
