import arabic_reshaper
from bidi.algorithm import get_display

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
from kivy.clock import Clock

from database import Database

RTL_MARK = "\u200f"
COLUMN_WIDTHS = (0.07, 0.24, 0.16, 0.11, 0.16, 0.13, 0.13)


def display_persian(text):
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))



class PersianTextInput(TextInput):
    """
    Simple RTL-aware Persian editor for Kivy on Windows.

    Kivy's normal TextInput often displays Persian letters in visual reverse
    order. This widget keeps the real logical text separately and renders a
    shaped RTL version for display.

    Editing is intentionally end-of-text based, which is reliable for names
    and short notes in this application.
    """

    logical_text = StringProperty("")

    def set_logical_text(self, value):
        self.logical_text = str(value or "")
        self._render_logical_text()

    def get_logical_text(self):
        return self.logical_text

    def insert_text(self, substring, from_undo=False):
        if self.readonly:
            return
        self.logical_text += str(substring)
        self._render_logical_text()

    def do_backspace(self, from_undo=False, mode="bkspc"):
        if self.readonly or not self.logical_text:
            return
        self.logical_text = self.logical_text[:-1]
        self._render_logical_text()

    def _render_logical_text(self):
        rendered = display_persian(self.logical_text)
        self.text = rendered
        self.cursor = (len(self._lines[-1]) if self._lines else 0, len(self._lines) - 1)

class StudentRow(ButtonBehavior, BoxLayout):
    student_id = NumericProperty(0)
    selected = BooleanProperty(False)
    paid_status = StringProperty("Unpaid")
    remaining_sessions = NumericProperty(0)
    row_index = NumericProperty(0)

    selected_color = ListProperty([0.82, 0.74, 0.96, 1])
    unpaid_color = ListProperty([1.00, 0.78, 0.78, 1])
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
            self._line_color = Color(0.80, 0.76, 0.86, 1)
            self._line = Line(points=[], width=0.7)

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            selected=self._refresh_color,
            paid_status=self._refresh_color,
            remaining_sessions=self._refresh_color,
            row_index=self._refresh_color,
        )
        self._refresh_color()

    def _update_canvas(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._line.points = [
            self.x,
            self.y,
            self.right,
            self.y,
            self.right,
            self.top,
            self.x,
            self.top,
            self.x,
            self.y,
        ]

    def _refresh_color(self, *_):
        if self.selected:
            color = self.selected_color
        elif self.paid_status.lower() != "paid":
            color = self.unpaid_color
        elif 0 < self.remaining_sessions <= 3:
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
    paid_status_input = ObjectProperty(None)
    payment_date_input = ObjectProperty(None)
    sessions_paid_input = ObjectProperty(None)
    search_input = ObjectProperty(None)

    sort_column = StringProperty("name")
    sort_reverse = BooleanProperty(False)
    filter_status = StringProperty("All")

    def on_enter(self):
        self.selected_student_id = None
        self.current_selected_row = None
        self.clear_form()
        self.load_students()

    def schedule_search(self, *_):
        """Debounce search typing so the table refreshes reliably."""
        Clock.unschedule(self._run_scheduled_search)
        Clock.schedule_once(self._run_scheduled_search, 0.15)

    def _run_scheduled_search(self, *_):
        self.load_students()

    @staticmethod
    def _normalize_search_text(value):
        return (
            str(value or "")
            .replace(RTL_MARK, "")
            .replace("\u200c", "")
            .strip()
            .casefold()
        )

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------
    def load_students(self):
        if not self.student_list:
            return

        query = ""
        if self.search_input:
            query = self._normalize_search_text(self.search_input.text)

        students = Database().get_student_summaries()

        if query:
            students = [
                item
                for item in students
                if query in self._normalize_search_text(item["name"])
                or query in self._normalize_search_text(item["phone"])
                or query in self._normalize_search_text(item["id"])
            ]

        if self.filter_status == "Paid":
            students = [item for item in students if item["paid_status"] == "Paid"]
        elif self.filter_status == "Unpaid":
            students = [item for item in students if item["paid_status"] != "Paid"]
        elif self.filter_status == "Near Renewal":
            students = [
                item
                for item in students
                if item["paid_status"] == "Paid"
                and 0 < item["remaining_sessions"] <= 3
            ]

        students.sort(key=self._sort_key, reverse=self.sort_reverse)
        self.students = students

        self.student_list.clear_widgets()
        self.student_count.text = f"Students: {len(students)}"

        for index, student in enumerate(students):
            self.student_list.add_widget(self._build_row(student, index))

    def _sort_key(self, student):
        value = student.get(self.sort_column)
        if self.sort_column in {
            "id",
            "sessions_paid",
            "remaining_sessions",
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
            paid_status=student["paid_status"],
            remaining_sessions=student["remaining_sessions"],
            row_index=index,
        )
        row.bind(
            on_release=lambda instance, sid=student["id"]: self.select_student(
                sid, instance
            )
        )

        values = (
            str(student["id"]),
            display_persian(student["name"]),
            student["phone"] or "-",
            student["paid_status"],
            student["payment_date"],
            str(student["sessions_paid"]),
            str(student["remaining_sessions"]),
        )
        alignments = ("center", "right", "left", "center", "center", "center", "center")

        for value, width, alignment in zip(values, COLUMN_WIDTHS, alignments):
            row.add_widget(self._cell(value, width, alignment))

        return row

    @staticmethod
    def _cell(text, width, alignment):
        label = Label(
            text=str(text),
            font_name="Persian",
            font_size=14,
            color=(0.16, 0.10, 0.23, 1),
            size_hint_x=width,
            halign=alignment,
            valign="middle",
            padding=(8, 0),
        )
        label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        return label

    # ------------------------------------------------------------------
    # Selection and form
    # ------------------------------------------------------------------
    def select_student(self, student_id, row=None):
        if self.current_selected_row:
            self.current_selected_row.selected = False

        if row:
            row.selected = True
            self.current_selected_row = row

        student = Database().get_student(student_id)
        if not student:
            return

        summary = next(
            (
                item
                for item in Database().get_student_summaries()
                if item["id"] == student_id
            ),
            None,
        )
        if not summary:
            return

        _, name, phone, notes = student
        self.selected_student_id = student_id
        self.name_input.set_logical_text(name or "")
        self.phone_input.text = phone or ""
        self.notes_input.set_logical_text(notes or "")
        self.paid_status_input.text = summary["paid_status"]
        self.payment_date_input.text = (
            "" if summary["payment_date"] == "-" else summary["payment_date"]
        )
        self.sessions_paid_input.text = str(summary["sessions_paid"] or "")

    def clear_form(self):
        self.selected_student_id = None

        if getattr(self, "current_selected_row", None):
            self.current_selected_row.selected = False
            self.current_selected_row = None

        for widget_name in ("name_input", "phone_input", "notes_input"):
            widget = getattr(self, widget_name, None)
            if not widget:
                continue
            if hasattr(widget, "set_logical_text"):
                widget.set_logical_text("")
            else:
                widget.text = ""

        if self.paid_status_input:
            self.paid_status_input.text = "Unpaid"
        if self.payment_date_input:
            self.payment_date_input.text = ""
        if self.sessions_paid_input:
            self.sessions_paid_input.text = ""

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
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
        if not self.selected_student_id:
            return

        name = self.name_input.get_logical_text().strip()
        if not name:
            return

        db = Database()
        db.update_student(
            student_id=self.selected_student_id,
            name=name,
            phone=self.phone_input.text.strip(),
            notes=self.notes_input.get_logical_text().strip(),
        )
        self._save_payment(db, self.selected_student_id)
        self.clear_form()
        self.load_students()

    def _save_payment(self, db, student_id):
        status = self.paid_status_input.text.strip() or "Unpaid"
        payment_date = self.payment_date_input.text.strip()
        sessions_text = self.sessions_paid_input.text.strip()

        if status == "Paid":
            sessions_paid = int(sessions_text or 12)
            db.save_payment_status(
                student_id=student_id,
                paid_status="Paid",
                payment_date=payment_date or None,
                sessions_paid=sessions_paid,
            )
        else:
            db.save_payment_status(
                student_id=student_id,
                paid_status="Unpaid",
            )

    def delete_student(self):
        if not self.selected_student_id:
            return
        Database().delete_student(self.selected_student_id)
        self.clear_form()
        self.load_students()
