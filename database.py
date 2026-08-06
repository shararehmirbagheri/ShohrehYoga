import shutil
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "data" / "yoga.db"

CLASS_HELD = "Class Held"
CANCELED_CLASS = "Canceled Class"
EXTRA_CLASS = "Extra Class"
NO_CLASS = "No Class"


class Database:
    def __init__(self):
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.migrate()

    def close(self):
        self.conn.close()

    def create_tables(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            notes TEXT,
            receipt TEXT NOT NULL DEFAULT 'No',
            first_session_date TEXT,
            baseline_used_sessions INTEGER NOT NULL DEFAULT 0
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendances(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            UNIQUE(student_id, date),
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            sessions_paid INTEGER NOT NULL CHECK(sessions_paid >= 0),
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_days(
            date TEXT PRIMARY KEY,
            status TEXT NOT NULL
        )
        """)
        self.conn.commit()

    def migrate(self):
        self.cursor.execute("PRAGMA table_info(students)")
        columns = {row["name"] for row in self.cursor.fetchall()}

        if "receipt" not in columns:
            self.cursor.execute(
                "ALTER TABLE students ADD COLUMN receipt TEXT NOT NULL DEFAULT 'No'"
            )
        if "first_session_date" not in columns:
            self.cursor.execute(
                "ALTER TABLE students ADD COLUMN first_session_date TEXT"
            )
        if "baseline_used_sessions" not in columns:
            self.cursor.execute(
                "ALTER TABLE students ADD COLUMN baseline_used_sessions INTEGER NOT NULL DEFAULT 0"
            )
        self.conn.commit()

    @staticmethod
    def validate_iso(value):
        datetime.strptime(value, "%Y-%m-%d")
        return value

    @staticmethod
    def normalize_receipt(value):
        return "Yes" if str(value).strip().lower() in {
            "yes", "y", "1", "true", "دارد"
        } else "No"

    # ---------------- Students ----------------
    def add_student(
        self,
        name,
        phone="",
        notes="",
        receipt="No",
        first_session_date="",
    ):
        if first_session_date:
            self.validate_iso(first_session_date)

        self.cursor.execute("""
        INSERT INTO students(
            name, phone, notes, receipt, first_session_date,
            baseline_used_sessions
        )
        VALUES (?, ?, ?, ?, ?, 0)
        """, (
            name,
            phone,
            notes,
            self.normalize_receipt(receipt),
            first_session_date or None,
        ))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_students(self):
        self.cursor.execute(
            "SELECT id, name, phone, notes FROM students ORDER BY name"
        )
        return [tuple(row) for row in self.cursor.fetchall()]

    def get_student(self, student_id):
        self.cursor.execute(
            "SELECT id, name, phone, notes FROM students WHERE id=?",
            (student_id,),
        )
        row = self.cursor.fetchone()
        return tuple(row) if row else None

    def get_student_details(self, student_id):
        self.cursor.execute("""
        SELECT id, name, phone, notes, receipt, first_session_date,
               baseline_used_sessions
        FROM students
        WHERE id=?
        """, (student_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_student(
        self,
        student_id,
        name,
        phone="",
        notes="",
        receipt="No",
        first_session_date="",
    ):
        if first_session_date:
            self.validate_iso(first_session_date)

        self.cursor.execute("""
        UPDATE students
        SET name=?, phone=?, notes=?, receipt=?, first_session_date=?
        WHERE id=?
        """, (
            name,
            phone,
            notes,
            self.normalize_receipt(receipt),
            first_session_date or None,
            student_id,
        ))
        self.conn.commit()

    def delete_student(self, student_id):
        self.cursor.execute("DELETE FROM students WHERE id=?", (student_id,))
        self.conn.commit()

    # ---------------- Payments ----------------
    def get_latest_payment(self, student_id):
        self.cursor.execute("""
        SELECT id, payment_date, sessions_paid
        FROM payments
        WHERE student_id=?
        ORDER BY payment_date DESC, id DESC
        LIMIT 1
        """, (student_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def save_payment(self, student_id, payment_date, sessions_paid):
        sessions_paid = int(sessions_paid or 0)

        if sessions_paid <= 0:
            self.cursor.execute(
                "DELETE FROM payments WHERE student_id=?",
                (student_id,),
            )
            self.conn.commit()
            return

        payment_date = payment_date or date.today().isoformat()
        self.validate_iso(payment_date)
        latest = self.get_latest_payment(student_id)

        if latest:
            self.cursor.execute("""
            UPDATE payments
            SET payment_date=?, sessions_paid=?
            WHERE id=?
            """, (payment_date, sessions_paid, latest["id"]))
        else:
            self.cursor.execute("""
            INSERT INTO payments(student_id, payment_date, sessions_paid)
            VALUES (?, ?, ?)
            """, (student_id, payment_date, sessions_paid))
        self.conn.commit()

    # ---------------- Class-day status ----------------
    @staticmethod
    def default_class_status(iso_date):
        selected = datetime.strptime(iso_date, "%Y-%m-%d").date()
        # Python weekday: Monday 0 ... Thursday 3, Friday 4.
        return NO_CLASS if selected.weekday() in (3, 4) else CLASS_HELD

    def get_class_status(self, iso_date):
        self.cursor.execute(
            "SELECT status FROM class_days WHERE date=?",
            (iso_date,),
        )
        row = self.cursor.fetchone()
        return row["status"] if row else self.default_class_status(iso_date)

    def save_class_status(self, iso_date, status):
        if status not in {
            CLASS_HELD, CANCELED_CLASS, EXTRA_CLASS, NO_CLASS
        }:
            raise ValueError(f"Invalid class status: {status}")

        self.cursor.execute("""
        INSERT INTO class_days(date, status)
        VALUES (?, ?)
        ON CONFLICT(date) DO UPDATE SET status=excluded.status
        """, (iso_date, status))

        if status in {CANCELED_CLASS, NO_CLASS}:
            self.cursor.execute(
                "DELETE FROM attendances WHERE date=?",
                (iso_date,),
            )
        self.conn.commit()

    # ---------------- Attendance ----------------
    def get_attendance_for_date(self, attended_on):
        self.cursor.execute(
            "SELECT student_id FROM attendances WHERE date=?",
            (attended_on,),
        )
        return {row[0] for row in self.cursor.fetchall()}

    def save_attendance_for_date(
        self,
        attended_on,
        present_student_ids,
        class_status=CLASS_HELD,
    ):
        self.save_class_status(attended_on, class_status)

        if class_status in {CANCELED_CLASS, NO_CLASS}:
            return

        self.cursor.execute(
            "DELETE FROM attendances WHERE date=?",
            (attended_on,),
        )
        rows = [
            (int(student_id), attended_on)
            for student_id in sorted(set(present_student_ids))
        ]
        if rows:
            self.cursor.executemany("""
            INSERT INTO attendances(student_id, date)
            VALUES (?, ?)
            """, rows)
        self.conn.commit()

    def get_attendance_count_since(self, student_id, from_date=None):
        if from_date:
            self.cursor.execute("""
            SELECT COUNT(*)
            FROM attendances a
            LEFT JOIN class_days c ON c.date=a.date
            WHERE a.student_id=?
              AND a.date>=?
              AND COALESCE(c.status, 'Class Held')
                  NOT IN ('Canceled Class', 'No Class')
            """, (student_id, from_date))
        else:
            self.cursor.execute("""
            SELECT COUNT(*)
            FROM attendances a
            LEFT JOIN class_days c ON c.date=a.date
            WHERE a.student_id=?
              AND COALESCE(c.status, 'Class Held')
                  NOT IN ('Canceled Class', 'No Class')
            """, (student_id,))
        return self.cursor.fetchone()[0]

    def get_attendance_export_rows(self, attended_on):
        present_ids = self.get_attendance_for_date(attended_on)
        class_status = self.get_class_status(attended_on)
        return [
            {
                "date": attended_on,
                "student_id": student_id,
                "name": name,
                "phone": phone or "",
                "class_status": class_status,
                "status": (
                    "Canceled"
                    if class_status == CANCELED_CLASS
                    else "No Class"
                    if class_status == NO_CLASS
                    else "Present"
                    if student_id in present_ids
                    else "Absent"
                ),
            }
            for student_id, name, phone, notes in self.get_students()
        ]

    # ---------------- Calculated student summary ----------------
    def get_student_summary(self, student_id):
        details = self.get_student_details(student_id)
        if not details:
            return None

        payment = self.get_latest_payment(student_id)
        first_session = details["first_session_date"] or ""
        paid = int(payment["sessions_paid"]) if payment else 0
        payment_date = payment["payment_date"] if payment else ""

        baseline = int(details["baseline_used_sessions"] or 0)
        new_used = self.get_attendance_count_since(
            student_id,
            first_session or payment_date or None,
        )
        used = baseline + new_used
        remaining = paid - used
        receipt = self.normalize_receipt(details["receipt"])

        if receipt == "No":
            status = "No Receipt"
        elif remaining <= 0:
            status = "Expired"
        elif remaining <= 3:
            status = "Renew Soon"
        else:
            status = "Active"

        return {
            "id": details["id"],
            "name": details["name"],
            "phone": details["phone"] or "",
            "notes": details["notes"] or "",
            "receipt": receipt,
            "first_session_date": first_session,
            "payment_date": payment_date,
            "sessions_paid": paid,
            "sessions_purchased": paid,
            "sessions_used": used,
            "remaining_sessions": remaining,
            "status": status,
        }

    def get_student_summaries(self):
        return [
            self.get_student_summary(student_id)
            for student_id, _, _, _ in self.get_students()
        ]

    # ---------------- Reports ----------------
    def get_report_dates(self, start_date, end_date):
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        dates = []
        current = start
        while current <= end:
            iso_date = current.isoformat()
            status = self.get_class_status(iso_date)

            # Sat-Wed default class days are included.
            # Canceled scheduled days remain visible as gray columns.
            # Thu/Fri are excluded unless explicitly marked Extra Class.
            if status in {CLASS_HELD, CANCELED_CLASS, EXTRA_CLASS}:
                dates.append({
                    "date": iso_date,
                    "status": status,
                })
            current += timedelta(days=1)

        return dates

    def get_attendance_matrix(self, start_date, end_date):
        report_dates = self.get_report_dates(start_date, end_date)
        students = self.get_student_summaries()

        attendance_by_date = {
            item["date"]: self.get_attendance_for_date(item["date"])
            for item in report_dates
        }

        rows = []
        for student in students:
            attendance = {}
            for item in report_dates:
                iso_date = item["date"]
                if item["status"] == CANCELED_CLASS:
                    attendance[iso_date] = "Canceled"
                else:
                    attendance[iso_date] = (
                        "Present"
                        if student["id"] in attendance_by_date[iso_date]
                        else "Absent"
                    )

            row = dict(student)
            row["attendance"] = attendance
            rows.append(row)

        return report_dates, rows

    def backup_database(self, destination_folder=None):
        destination = Path(destination_folder or (BASE_DIR / "backups"))
        destination.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = destination / f"yoga_backup_{timestamp}.db"
        self.conn.commit()
        shutil.copy2(DB_FILE, backup_file)
        return backup_file
