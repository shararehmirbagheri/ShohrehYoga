from datetime import date, datetime

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


def display_persian(text):
    """Render Persian/Arabic text correctly in Kivy labels."""
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

        self.checkbox = CheckBox(
            active=self.present,
            size_hint_x=0.12,
        )
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
        name_label.bind(
            size=lambda widget, size: setattr(widget, "text_size", size)
        )
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
        self.status_label.bind(
            size=lambda widget, size: setattr(widget, "text_size", size)
        )
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
    total_count_label = ObjectProperty(None)

    def on_kv_post(self, base_widget):
        """
        Run after the KV ids are connected.

        This fixes the blank attendance list caused by load_attendance()
        running before attendance_list and selected_date_input exist.
        """
        Clock.schedule_once(self._initial_load, 0)

    def on_enter(self):
        Clock.schedule_once(self._initial_load, 0)

    def _initial_load(self, *_):
        if not self.selected_date_input or not self.attendance_list:
            return

        if not self.selected_date_input.text.strip():
            self.selected_date_input.text = date.today().isoformat()

        self.load_attendance()

    def _validated_date(self):
        if not self.selected_date_input:
            return date.today().isoformat()

        value = self.selected_date_input.text.strip()

        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            value = date.today().isoformat()
            self.selected_date_input.text = value

        return value

    @staticmethod
    def _get_students(db):
        """
        Return all students using either the existing Database API
        or a direct SQLite fallback.
        """
        try:
            students = db.get_students()
            if students:
                return students
        except Exception:
            pass

        db.cursor.execute(
            """
            SELECT id, name, phone, notes
            FROM students
            ORDER BY name
            """
        )
        return db.cursor.fetchall()

    @staticmethod
    def _get_present_ids(db, attended_on):
        """
        Read saved attendance even when database.py does not yet contain
        get_attendance_for_date().
        """
        if hasattr(db, "get_attendance_for_date"):
            try:
                return set(db.get_attendance_for_date(attended_on))
            except Exception:
                pass

        db.cursor.execute(
            """
            SELECT student_id
            FROM attendances
            WHERE date = ?
            """,
            (attended_on,),
        )
        return {row[0] for row in db.cursor.fetchall()}

    @staticmethod
    def _save_present_ids(db, attended_on, present_student_ids):
        """
        Replace attendance for the selected date.

        Checked students are present. Unchecked students are absent.
        """
        if hasattr(db, "save_attendance_for_date"):
            try:
                db.save_attendance_for_date(attended_on, present_student_ids)
                return
            except Exception:
                pass

        db.cursor.execute(
            "DELETE FROM attendances WHERE date = ?",
            (attended_on,),
        )

        rows = [
            (int(student_id), attended_on)
            for student_id in sorted(set(present_student_ids))
        ]

        if rows:
            db.cursor.executemany(
                """
                INSERT INTO attendances(student_id, date)
                VALUES (?, ?)
                """,
                rows,
            )

        db.conn.commit()

    def load_attendance(self):
        if not self.attendance_list or not self.selected_date_input:
            Clock.schedule_once(lambda *_: self.load_attendance(), 0.1)
            return

        attended_on = self._validated_date()
        db = Database()

        students = self._get_students(db)
        present_ids = self._get_present_ids(db, attended_on)

        self.attendance_list.clear_widgets()

        for student in students:
            student_id = int(student[0])
            student_name = student[1] or ""

            row = AttendanceStudentRow(
                student_id=student_id,
                student_name=student_name,
                present=student_id in present_ids,
            )
            row.bind(present=lambda *_: self.update_counts())
            self.attendance_list.add_widget(row)

        self.update_counts()

    def save_attendance(self):
        if not self.attendance_list:
            return

        attended_on = self._validated_date()

        present_ids = [
            row.student_id
            for row in self.attendance_list.children
            if isinstance(row, AttendanceStudentRow) and row.present
        ]

        db = Database()
        self._save_present_ids(db, attended_on, present_ids)

        # Reload to confirm the saved state.
        self.load_attendance()

    def select_all(self):
        if not self.attendance_list:
            return

        for row in self.attendance_list.children:
            if isinstance(row, AttendanceStudentRow):
                row.present = True

        self.update_counts()

    def clear_all(self):
        if not self.attendance_list:
            return

        for row in self.attendance_list.children:
            if isinstance(row, AttendanceStudentRow):
                row.present = False

        self.update_counts()

    def use_today(self):
        if not self.selected_date_input:
            return

        self.selected_date_input.text = date.today().isoformat()
        self.load_attendance()

    def update_counts(self):
        if not self.attendance_list:
            return

        rows = [
            row
            for row in self.attendance_list.children
            if isinstance(row, AttendanceStudentRow)
        ]

        present_count = sum(1 for row in rows if row.present)

        if self.present_count_label:
            self.present_count_label.text = f"Present: {present_count}"

        if self.total_count_label:
            self.total_count_label.text = f"Students: {len(rows)}"
