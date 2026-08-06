import csv
from datetime import date, datetime
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from database import Database

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"


def display_persian(text):
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))


class AttendanceStudentRow(ButtonBehavior, BoxLayout):
    student_id = NumericProperty(0)
    student_name = StringProperty("")
    present = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 46
        self.spacing = 0

        with self.canvas.before:
            self._bg_color = Color(0.98, 0.97, 1.00, 1)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        with self.canvas.after:
            Color(0.83, 0.79, 0.88, 1)
            self._border = Line(points=[], width=0.7)

        self.checkbox = CheckBox(active=self.present, size_hint_x=0.12)
        self.checkbox.bind(active=self._checkbox_changed)
        self.add_widget(self.checkbox)

        name_label = Label(
            text=display_persian(self.student_name),
            font_name="Persian",
            font_size=15,
            color=(0.18, 0.10, 0.25, 1),
            size_hint_x=0.63,
            halign="right",
            valign="middle",
            padding=(10, 0),
        )
        name_label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        self.add_widget(name_label)

        self.status_label = Label(
            text="Present" if self.present else "Absent",
            font_name="Persian",
            font_size=14,
            color=(0.18, 0.10, 0.25, 1),
            size_hint_x=0.25,
            halign="center",
            valign="middle",
        )
        self.status_label.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        self.add_widget(self.status_label)

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            present=self._refresh_state,
        )
        self._refresh_state()

    def _update_canvas(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._border.points = [
            self.x, self.y, self.right, self.y, self.right,
            self.top, self.x, self.top, self.x, self.y
        ]

    def _checkbox_changed(self, _, active):
        self.present = active

    def _refresh_state(self, *_):
        if self.checkbox.active != self.present:
            self.checkbox.active = self.present

        if self.present:
            self._bg_color.rgba = (0.86, 0.96, 0.87, 1)
            self.status_label.text = "Present"
        else:
            self._bg_color.rgba = (0.98, 0.97, 1.00, 1)
            self.status_label.text = "Absent"

    def on_release(self):
        self.present = not self.present


class AttendanceScreen(Screen):
    attendance_list = ObjectProperty(None)
    selected_date_input = ObjectProperty(None)
    present_count_label = ObjectProperty(None)
    absent_count_label = ObjectProperty(None)
    total_count_label = ObjectProperty(None)
    export_message = ObjectProperty(None)

    def on_enter(self):
        Clock.schedule_once(self._initial_load, 0)

    def _initial_load(self, *_):
        if not self.selected_date_input or not self.attendance_list:
            return
        if not self.selected_date_input.text.strip():
            self.selected_date_input.text = date.today().isoformat()
        self.load_attendance()

    def _validated_date(self):
        value = self.selected_date_input.text.strip()
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            value = date.today().isoformat()
            self.selected_date_input.text = value
        return value

    def load_attendance(self):
        if not self.attendance_list:
            return

        attended_on = self._validated_date()
        db = Database()
        students = db.get_students()
        present_ids = db.get_attendance_for_date(attended_on)

        self.attendance_list.clear_widgets()

        for student_id, name, phone, notes in students:
            row = AttendanceStudentRow(
                student_id=student_id,
                student_name=name,
                present=student_id in present_ids,
            )
            row.bind(present=lambda *_: self.update_counts())
            self.attendance_list.add_widget(row)

        self.update_counts()

    def save_attendance(self):
        attended_on = self._validated_date()
        present_ids = [
            row.student_id
            for row in self.attendance_list.children
            if isinstance(row, AttendanceStudentRow) and row.present
        ]
        Database().save_attendance_for_date(attended_on, present_ids)
        self.export_message.text = f"Attendance saved for {attended_on}"
        self.load_attendance()

    def select_all(self):
        for row in self.attendance_list.children:
            if isinstance(row, AttendanceStudentRow):
                row.present = True
        self.update_counts()

    def clear_all(self):
        for row in self.attendance_list.children:
            if isinstance(row, AttendanceStudentRow):
                row.present = False
        self.update_counts()

    def use_today(self):
        self.selected_date_input.text = date.today().isoformat()
        self.load_attendance()

    def update_counts(self):
        rows = [
            row for row in self.attendance_list.children
            if isinstance(row, AttendanceStudentRow)
        ]
        present = sum(1 for row in rows if row.present)
        absent = len(rows) - present

        self.present_count_label.text = f"Present: {present}"
        self.absent_count_label.text = f"Absent: {absent}"
        self.total_count_label.text = f"Students: {len(rows)}"

    def export_attendance(self):
        attended_on = self._validated_date()
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        output = EXPORT_DIR / f"attendance_{attended_on}.csv"

        rows = Database().get_attendance_export_rows(attended_on)
        with output.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["date", "student_id", "name", "phone", "status"],
            )
            writer.writeheader()
            writer.writerows(rows)

        self.export_message.text = f"Saved: {output.name}"

    def export_student_summary(self):
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = EXPORT_DIR / f"student_summary_{timestamp}.csv"

        rows = Database().get_student_summaries()
        with output.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "id",
                    "name",
                    "phone",
                    "payment_date",
                    "sessions_purchased",
                    "sessions_used",
                    "remaining_sessions",
                    "status",
                ],
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)

        self.export_message.text = f"Saved: {output.name}"

    def backup_database(self):
        output = Database().backup_database()
        self.export_message.text = f"Backup: {output.name}"
