import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "data" / "yoga.db"


class Database:
    def __init__(self):
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self._migrate_students_table()

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
        self.conn.commit()

    def _migrate_students_table(self):
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
    def _normalize_receipt(value):
        return "Yes" if str(value).strip().lower() in {
            "yes", "y", "1", "true", "دارد"
        } else "No"

    @staticmethod
    def _validate_iso_date(value):
        if not value:
            return ""
        datetime.strptime(value, "%Y-%m-%d")
        return value

    def add_student(
        self,
        name,
        phone="",
        notes="",
        receipt="No",
        first_session_date="",
    ):
        first_session_date = self._validate_iso_date(first_session_date)
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
            self._normalize_receipt(receipt),
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
        first_session_date = self._validate_iso_date(first_session_date)
        self.cursor.execute("""
        UPDATE students
        SET name=?, phone=?, notes=?, receipt=?, first_session_date=?
        WHERE id=?
        """, (
            name,
            phone,
            notes,
            self._normalize_receipt(receipt),
            first_session_date or None,
            student_id,
        ))
        self.conn.commit()

    def delete_student(self, student_id):
        self.cursor.execute("DELETE FROM students WHERE id=?", (student_id,))
        self.conn.commit()

    def student_count(self):
        self.cursor.execute("SELECT COUNT(*) FROM students")
        return self.cursor.fetchone()[0]

    def add_attendance(self, student_id, attended_on=None):
        attended_on = attended_on or date.today().isoformat()
        self.cursor.execute("""
        INSERT OR IGNORE INTO attendances(student_id, date)
        VALUES (?, ?)
        """, (student_id, attended_on))
        self.conn.commit()

    def get_attendance_for_date(self, attended_on):
        self.cursor.execute(
            "SELECT student_id FROM attendances WHERE date=?",
            (attended_on,),
        )
        return {row[0] for row in self.cursor.fetchall()}

    def save_attendance_for_date(self, attended_on, present_student_ids):
        self.cursor.execute("DELETE FROM attendances WHERE date=?", (attended_on,))
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
            SELECT COUNT(*) FROM attendances
            WHERE student_id=? AND date>=?
            """, (student_id, from_date))
        else:
            self.cursor.execute(
                "SELECT COUNT(*) FROM attendances WHERE student_id=?",
                (student_id,),
            )
        return self.cursor.fetchone()[0]

    def get_attendance_export_rows(self, attended_on):
        present_ids = self.get_attendance_for_date(attended_on)
        return [
            {
                "date": attended_on,
                "student_id": student_id,
                "name": name,
                "phone": phone or "",
                "status": "Present" if student_id in present_ids else "Absent",
            }
            for student_id, name, phone, notes in self.get_students()
        ]

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
        self._validate_iso_date(payment_date)
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

    def get_student_summary(self, student_id):
        details = self.get_student_details(student_id)
        if not details:
            return None

        payment = self.get_latest_payment(student_id)
        first_session_date = details["first_session_date"] or ""
        sessions_paid = int(payment["sessions_paid"]) if payment else 0
        payment_date = payment["payment_date"] if payment else ""

        # Imported spreadsheet count + all new attendance recorded in the app.
        baseline_used = int(details["baseline_used_sessions"] or 0)
        new_used = self.get_attendance_count_since(
            student_id,
            first_session_date or payment_date or None,
        )
        sessions_used = baseline_used + new_used
        remaining = sessions_paid - sessions_used
        receipt = self._normalize_receipt(details["receipt"])

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
            "first_session_date": first_session_date,
            "payment_date": payment_date,
            "sessions_paid": sessions_paid,
            "sessions_purchased": sessions_paid,
            "sessions_used": sessions_used,
            "remaining_sessions": remaining,
            "status": status,
        }

    def get_student_summaries(self):
        return [
            self.get_student_summary(student_id)
            for student_id, _, _, _ in self.get_students()
        ]

    def get_attendance_details_between(self, start_date, end_date):
        """
        Return every recorded Present attendance between two ISO dates.
        Only Present students are stored in the attendances table.
        """
        self.cursor.execute(
            """
            SELECT
                a.date,
                s.id AS student_id,
                s.name,
                s.phone
            FROM attendances a
            JOIN students s ON s.id = a.student_id
            WHERE a.date BETWEEN ? AND ?
            ORDER BY a.date, s.name
            """,
            (start_date, end_date),
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def get_attendance_summary_between(self, start_date, end_date):
        """
        Return one row per student with Present count and attendance dates
        for the selected date range.
        """
        self.cursor.execute(
            """
            SELECT
                s.id,
                s.name,
                s.phone,
                COUNT(a.id) AS present_count,
                GROUP_CONCAT(a.date, ', ') AS attendance_dates
            FROM students s
            LEFT JOIN attendances a
                ON a.student_id = s.id
               AND a.date BETWEEN ? AND ?
            GROUP BY s.id, s.name, s.phone
            ORDER BY s.name
            """,
            (start_date, end_date),
        )

        rows = []
        for row in self.cursor.fetchall():
            rows.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "phone": row["phone"] or "",
                    "present_count": int(row["present_count"] or 0),
                    "attendance_dates": row["attendance_dates"] or "",
                }
            )
        return rows

    def backup_database(self, destination_folder=None):
        destination = Path(destination_folder or (BASE_DIR / "backups"))
        destination.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = destination / f"yoga_backup_{timestamp}.db"
        self.conn.commit()
        shutil.copy2(DB_FILE, backup_file)
        return backup_file
