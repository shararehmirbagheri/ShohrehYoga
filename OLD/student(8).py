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
    """Small RTL-aware Persian editor for names and notes."""

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
    status = StringProperty("Unpaid")
    remaining_sessions = NumericProperty(0)
    row_index = NumericProperty(0)

    selected_color = ListProperty([0.82, 0.74, 0.96, 1])
    danger_color = ListProperty([1.00, 0.78, 0.78, 1])
    warning_color = ListProperty([1.00, 0.88, 0.65, 1])
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
            status=self._refresh_color,
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
        elif self.status in {"Unpaid", "Expired"}:
            color = self.danger_color
        elif self.status == "Renew Soon":
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
    payment_date_input = ObjectProperty(None)
    purchased_input = ObjectProperty(None)
    used_value = ObjectProperty(None)
    remaining_value = ObjectProperty(None)
    status_value = ObjectProperty(None)
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

        if self.filter_status != "All":
            students = [
                row for row in students
                if row["status"] == self.filter_status
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
            "id", "sessions_purchased", "sessions_used", "remaining_sessions"
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
            status=student["status"],
            remaining_sessions=student["remaining_sessions"],
            row_index=index,
        )
        row.bind(
            on_release=lambda instance, sid=student["id"]:
            self.select_student(sid, instance)
        )

        values = (
            str(student["id"]),
            display_persian(student["name"]),
            student["phone"] or "-",
            str(student["sessions_purchased"]),
            str(student["sessions_used"]),
            str(student["remaining_sessions"]),
            student["status"],
        )
        widths = (0.07, 0.25, 0.17, 0.13, 0.11, 0.13, 0.14)
        aligns = ("center", "right", "left", "center", "center", "center", "center")

        for value, width, align in zip(values, widths, aligns):
            label = Label(
                text=value,
                font_name="Persian",
                font_size=14,
                color=(0.16, 0.10, 0.23, 1),
                size_hint_x=width,
                halign=align,
                valign="middle",
                padding=(8, 0),
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
        payment_iso = "" if summary["payment_date"] == "-" else summary["payment_date"]
        self.payment_date_input.iso_date = payment_iso
        self.payment_date_input.text = (
            gregorian_iso_to_jalali_display(payment_iso)
            if payment_iso
            else ""
        )
        self.purchased_input.text = str(summary["sessions_purchased"] or "")
        self._show_calculated(summary)

    def _show_calculated(self, summary):
        self.used_value.text = str(summary["sessions_used"])
        self.remaining_value.text = str(summary["remaining_sessions"])
        self.status_value.text = summary["status"]

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
        if self.payment_date_input:
            self.payment_date_input.text = ""
            self.payment_date_input.iso_date = ""
        if self.purchased_input:
            self.purchased_input.text = ""
        if self.used_value:
            self.used_value.text = "0"
        if self.remaining_value:
            self.remaining_value.text = "0"
        if self.status_value:
            self.status_value.text = "Unpaid"

    def open_payment_calendar(self):
        current_iso = getattr(self.payment_date_input, "iso_date", "")

        def apply_date(gregorian_iso, jalali_display):
            self.payment_date_input.iso_date = gregorian_iso
            self.payment_date_input.text = jalali_display

        open_jalali_date_picker(
            current_gregorian_iso=current_iso,
            on_select=apply_date,
            title="انتخاب تاریخ پرداخت",
        )

    def _save_payment(self, db, student_id):
        purchased = int(self.purchased_input.text.strip() or 0)
        payment_date = getattr(self.payment_date_input, "iso_date", "")
        db.save_payment(student_id, payment_date, purchased)

    def add_student(self):
        name = self.name_input.get_logical_text().strip()
        if not name:
            return

        db = Database()
        student_id = db.add_student(
            name=name,
            phone=self.phone_input.text.strip(),
            notes=self.notes_input.get_logical_text().strip(),
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

        db = Database()
        db.update_student(
            self.selected_student_id,
            name,
            self.phone_input.text.strip(),
            self.notes_input.get_logical_text().strip(),
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
