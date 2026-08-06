import csv
import calendar
from datetime import date, datetime
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen

from database import Database
from jalali_calendar import (
    gregorian_iso_to_jalali_display,
    open_jalali_date_picker,
)

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
    report_from_input = ObjectProperty(None)
    report_to_input = ObjectProperty(None)

    sort_column = StringProperty("name")
    sort_reverse = BooleanProperty(False)

    def on_enter(self):
        Clock.schedule_once(self._initial_load, 0)

    def _initial_load(self, *_):
        if not self.selected_date_input or not self.attendance_list:
            return
        if not getattr(self.selected_date_input, "iso_date", ""):
            today_iso = date.today().isoformat()
            self.selected_date_input.iso_date = today_iso
            self.selected_date_input.text = gregorian_iso_to_jalali_display(
                today_iso
            )
        self.load_attendance()

        # Default report range: first day of the current month through today.
        today = date.today()
        first_day = today.replace(day=1)

        if self.report_from_input and not getattr(self.report_from_input, "iso_date", ""):
            self.report_from_input.iso_date = first_day.isoformat()
            self.report_from_input.text = gregorian_iso_to_jalali_display(
                first_day.isoformat()
            )

        if self.report_to_input and not getattr(self.report_to_input, "iso_date", ""):
            self.report_to_input.iso_date = today.isoformat()
            self.report_to_input.text = gregorian_iso_to_jalali_display(
                today.isoformat()
            )

    def _validated_date(self):
        iso_value = getattr(self.selected_date_input, "iso_date", "")
        try:
            datetime.strptime(iso_value, "%Y-%m-%d")
            return iso_value
        except (TypeError, ValueError):
            iso_value = date.today().isoformat()
            self.selected_date_input.iso_date = iso_value
            self.selected_date_input.text = gregorian_iso_to_jalali_display(
                iso_value
            )
            return iso_value

    # ------------------------------------------------------------------
    # Persian/Jalali calendar picker
    # ------------------------------------------------------------------
    def open_calendar(self):
        current_iso = self._validated_date()

        def apply_date(gregorian_iso, jalali_display):
            # Store Gregorian ISO internally; show Jalali to the user.
            self.selected_date_input.iso_date = gregorian_iso
            self.selected_date_input.text = jalali_display
            self.load_attendance()

        open_jalali_date_picker(
            current_gregorian_iso=current_iso,
            on_select=apply_date,
            title="انتخاب تاریخ حضور",
        )

    # ------------------------------------------------------------------
    # Loading and sorting
    # ------------------------------------------------------------------
    def load_attendance(self):
        if not self.attendance_list:
            return

        attended_on = self._validated_date()
        db = Database()
        students = db.get_students()
        present_ids = db.get_attendance_for_date(attended_on)

        records = [
            {
                "student_id": student_id,
                "name": name,
                "present": student_id in present_ids,
            }
            for student_id, name, phone, notes in students
        ]
        records.sort(key=self._sort_key, reverse=self.sort_reverse)

        self.attendance_list.clear_widgets()

        for record in records:
            row = AttendanceStudentRow(
                student_id=record["student_id"],
                student_name=record["name"],
                present=record["present"],
            )
            row.bind(present=lambda *_: self.update_counts())
            self.attendance_list.add_widget(row)

        self.update_counts()

    def _sort_key(self, record):
        if self.sort_column == "present":
            return 1 if record["present"] else 0
        if self.sort_column == "status":
            return "Present" if record["present"] else "Absent"
        return str(record["name"] or "").casefold()

    def sort_attendance(self, column):
        if column not in {"present", "name", "status"}:
            return

        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False

        self.load_attendance()

    # ------------------------------------------------------------------
    # Attendance actions
    # ------------------------------------------------------------------
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

        # Refresh calculated Used/Remaining values immediately.
        if self.manager and self.manager.has_screen("students"):
            self.manager.get_screen("students").load_students()

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
        today_iso = date.today().isoformat()
        self.selected_date_input.iso_date = today_iso
        self.selected_date_input.text = gregorian_iso_to_jalali_display(
            today_iso
        )
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

    # ------------------------------------------------------------------
    # Date-range reports
    # ------------------------------------------------------------------
    def _validated_report_range(self):
        start_date = getattr(self.report_from_input, "iso_date", "")
        end_date = getattr(self.report_to_input, "iso_date", "")

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            today = date.today()
            start = today.replace(day=1)
            end = today

        if start > end:
            start, end = end, start

        self.report_from_input.iso_date = start.isoformat()
        self.report_from_input.text = gregorian_iso_to_jalali_display(
            start.isoformat()
        )
        self.report_to_input.iso_date = end.isoformat()
        self.report_to_input.text = gregorian_iso_to_jalali_display(
            end.isoformat()
        )

        return start.isoformat(), end.isoformat()

    def open_report_from_calendar(self):
        current_iso = getattr(self.report_from_input, "iso_date", "") or date.today().isoformat()

        def apply_date(gregorian_iso, jalali_display):
            self.report_from_input.iso_date = gregorian_iso
            self.report_from_input.text = jalali_display

        open_jalali_date_picker(
            current_gregorian_iso=current_iso,
            on_select=apply_date,
            title="انتخاب تاریخ شروع گزارش",
        )

    def open_report_to_calendar(self):
        current_iso = getattr(self.report_to_input, "iso_date", "") or date.today().isoformat()

        def apply_date(gregorian_iso, jalali_display):
            self.report_to_input.iso_date = gregorian_iso
            self.report_to_input.text = jalali_display

        open_jalali_date_picker(
            current_gregorian_iso=current_iso,
            on_select=apply_date,
            title="انتخاب تاریخ پایان گزارش",
        )

    def view_range_report(self):
        start_date, end_date = self._validated_report_range()
        rows = Database().get_attendance_summary_between(start_date, end_date)

        content = BoxLayout(
            orientation="vertical",
            spacing=8,
            padding=10,
        )

        title = Label(
            text=(
                f"Attendance Report\\n"
                f"{gregorian_iso_to_jalali_display(start_date)}  -  "
                f"{gregorian_iso_to_jalali_display(end_date)}"
            ),
            font_name="Persian",
            font_size=19,
            bold=True,
            color=(0.20, 0.10, 0.28, 1),
            size_hint_y=None,
            height=62,
            halign="center",
            valign="middle",
        )
        title.bind(size=lambda widget, size: setattr(widget, "text_size", size))
        content.add_widget(title)

        header = BoxLayout(size_hint_y=None, height=42, spacing=1)
        for text, width in (
            ("ID", 0.08),
            ("Student Name", 0.34),
            ("Present Count", 0.18),
            ("Attendance Dates", 0.40),
        ):
            label = Label(
                text=text,
                font_name="Persian",
                bold=True,
                color=(1, 1, 1, 1),
                size_hint_x=width,
            )
            with label.canvas.before:
                Color(0.42, 0.16, 0.72, 1)
                label._bg = Rectangle(pos=label.pos, size=label.size)
            label.bind(
                pos=lambda widget, value: setattr(widget._bg, "pos", value),
                size=lambda widget, value: setattr(widget._bg, "size", value),
            )
            header.add_widget(label)
        content.add_widget(header)

        rows_layout = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=1,
        )
        rows_layout.bind(minimum_height=rows_layout.setter("height"))

        for index, row in enumerate(rows):
            line = BoxLayout(size_hint_y=None, height=44, spacing=1)
            values = (
                (str(row["id"]), 0.08, "center"),
                (display_persian(row["name"]), 0.34, "right"),
                (str(row["present_count"]), 0.18, "center"),
                (
                    ", ".join(
                        gregorian_iso_to_jalali_display(item.strip())
                        for item in row["attendance_dates"].split(",")
                        if item.strip()
                    ) or "-",
                    0.40,
                    "left",
                ),
            )

            for value, width, alignment in values:
                label = Label(
                    text=value,
                    font_name="Persian",
                    font_size=13,
                    color=(0.16, 0.10, 0.23, 1),
                    size_hint_x=width,
                    halign=alignment,
                    valign="middle",
                    padding=(7, 0),
                )
                label.bind(
                    size=lambda widget, size: setattr(widget, "text_size", size)
                )
                with label.canvas.before:
                    if index % 2 == 0:
                        Color(1, 1, 1, 1)
                    else:
                        Color(0.97, 0.95, 0.99, 1)
                    label._bg = Rectangle(pos=label.pos, size=label.size)
                label.bind(
                    pos=lambda widget, value: setattr(widget._bg, "pos", value),
                    size=lambda widget, value: setattr(widget._bg, "size", value),
                )
                line.add_widget(label)

            rows_layout.add_widget(line)

        scroll = ScrollView(do_scroll_x=False)
        scroll.add_widget(rows_layout)
        content.add_widget(scroll)

        close_button = Button(
            text="Close",
            font_name="Persian",
            size_hint_y=None,
            height=46,
            background_normal="",
            background_color=(0.50, 0.20, 0.82, 1),
            color=(1, 1, 1, 1),
        )
        content.add_widget(close_button)

        popup = Popup(
            title="Attendance Report",
            title_font="Persian",
            content=content,
            size_hint=(0.94, 0.88),
            auto_dismiss=False,
        )
        close_button.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def export_range_report(self):
        start_date, end_date = self._validated_report_range()
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)

        summary_output = EXPORT_DIR / (
            f"attendance_summary_{start_date}_to_{end_date}.csv"
        )
        detail_output = EXPORT_DIR / (
            f"attendance_detail_{start_date}_to_{end_date}.csv"
        )

        db = Database()
        summary_rows = db.get_attendance_summary_between(start_date, end_date)
        detail_rows = db.get_attendance_details_between(start_date, end_date)

        with summary_output.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "id",
                    "name",
                    "phone",
                    "present_count",
                    "attendance_dates",
                ],
            )
            writer.writeheader()
            writer.writerows(summary_rows)

        with detail_output.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "date",
                    "student_id",
                    "name",
                    "phone",
                ],
            )
            writer.writeheader()
            writer.writerows(detail_rows)

        self.export_message.text = (
            f"Saved: {summary_output.name} and {detail_output.name}"
        )

    # ------------------------------------------------------------------
    # Export and backup
    # ------------------------------------------------------------------
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
                    "receipt",
                    "first_session_date",
                    "sessions_paid",
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
