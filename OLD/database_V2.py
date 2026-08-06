import sqlite3
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "data" / "yoga.db"


class Database:
    """SQLite access layer for Shohreh Yoga Manager."""

    def __init__(self):
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON")
        self.create_tables()

    def close(self):
        self.conn.close()

    def create_tables(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                notes TEXT
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendances(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                payment_date TEXT NOT NULL,
                sessions_paid INTEGER NOT NULL CHECK(sessions_paid >= 0),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            )
            """
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Students
    # ------------------------------------------------------------------
    def add_student(self, name, phone="", notes=""):
        self.cursor.execute(
            "INSERT INTO students(name, phone, notes) VALUES (?, ?, ?)",
            (name, phone, notes),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_students(self):
        self.cursor.execute(
            "SELECT id, name, phone, notes FROM students ORDER BY name"
        )
        return [tuple(row) for row in self.cursor.fetchall()]

    def get_student(self, student_id):
        self.cursor.execute(
            "SELECT id, name, phone, notes FROM students WHERE id = ?",
            (student_id,),
        )
        row = self.cursor.fetchone()
        return tuple(row) if row else None

    def student_count(self):
        self.cursor.execute("SELECT COUNT(*) FROM students")
        return self.cursor.fetchone()[0]

    def update_student(self, student_id, name, phone="", notes=""):
        self.cursor.execute(
            """
            UPDATE students
            SET name = ?, phone = ?, notes = ?
            WHERE id = ?
            """,
            (name, phone, notes, student_id),
        )
        self.conn.commit()

    def delete_student(self, student_id):
        self.cursor.execute("DELETE FROM attendances WHERE student_id = ?", (student_id,))
        self.cursor.execute("DELETE FROM payments WHERE student_id = ?", (student_id,))
        self.cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Attendance
    # ------------------------------------------------------------------
    def add_attendance(self, student_id, attended_on=None):
        attended_on = attended_on or date.today().isoformat()
        self.cursor.execute(
            "INSERT INTO attendances(student_id, date) VALUES (?, ?)",
            (student_id, attended_on),
        )
        self.conn.commit()

    def attendance_exists(self, student_id, attended_on):
        self.cursor.execute(
            """
            SELECT 1
            FROM attendances
            WHERE student_id = ? AND date = ?
            """,
            (student_id, attended_on),
        )
        return self.cursor.fetchone() is not None

    def get_attendance_records(self):
        self.cursor.execute(
            """
            SELECT a.id, s.name, a.date
            FROM attendances a
            JOIN students s ON s.id = a.student_id
            ORDER BY a.date DESC, s.name
            """
        )
        return [tuple(row) for row in self.cursor.fetchall()]

    def get_attendance_count_since(self, student_id, from_date=None):
        if from_date:
            self.cursor.execute(
                """
                SELECT COUNT(*)
                FROM attendances
                WHERE student_id = ? AND date >= ?
                """,
                (student_id, from_date),
            )
        else:
            self.cursor.execute(
                "SELECT COUNT(*) FROM attendances WHERE student_id = ?",
                (student_id,),
            )
        return self.cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------
    def add_payment(self, student_id, sessions_paid, payment_date=None):
        payment_date = payment_date or date.today().isoformat()
        self.cursor.execute(
            """
            INSERT INTO payments(student_id, payment_date, sessions_paid)
            VALUES (?, ?, ?)
            """,
            (student_id, payment_date, int(sessions_paid)),
        )
        self.conn.commit()

    def get_latest_payment(self, student_id):
        self.cursor.execute(
            """
            SELECT id, payment_date, sessions_paid
            FROM payments
            WHERE student_id = ?
            ORDER BY payment_date DESC, id DESC
            LIMIT 1
            """,
            (student_id,),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def save_payment_status(
        self,
        student_id,
        paid_status,
        payment_date=None,
        sessions_paid=0,
    ):
        """
        Save the payment state shown on the student screen.

        Paid:
            Update the latest payment if one exists; otherwise insert one.
        Unpaid:
            Remove payment records so the student is explicitly unpaid.
        """
        if str(paid_status).strip().lower() != "paid":
            self.cursor.execute(
                "DELETE FROM payments WHERE student_id = ?",
                (student_id,),
            )
            self.conn.commit()
            return

        payment_date = payment_date or date.today().isoformat()
        sessions_paid = int(sessions_paid)
        if sessions_paid <= 0:
            raise ValueError("Sessions purchased must be greater than zero.")

        latest = self.get_latest_payment(student_id)
        if latest:
            self.cursor.execute(
                """
                UPDATE payments
                SET payment_date = ?, sessions_paid = ?
                WHERE id = ?
                """,
                (payment_date, sessions_paid, latest["id"]),
            )
        else:
            self.cursor.execute(
                """
                INSERT INTO payments(student_id, payment_date, sessions_paid)
                VALUES (?, ?, ?)
                """,
                (student_id, payment_date, sessions_paid),
            )
        self.conn.commit()

    def get_student_summaries(self):
        self.cursor.execute(
            "SELECT id, name, phone, notes FROM students ORDER BY name"
        )
        students = self.cursor.fetchall()

        summaries = []
        for row in students:
            student_id = row["id"]
            latest_payment = self.get_latest_payment(student_id)

            if latest_payment:
                payment_date = latest_payment["payment_date"]
                sessions_paid = int(latest_payment["sessions_paid"])
                sessions_used = self.get_attendance_count_since(
                    student_id, payment_date
                )
                remaining_sessions = max(sessions_paid - sessions_used, 0)
                paid_status = "Paid" if remaining_sessions > 0 else "Unpaid"
            else:
                payment_date = "-"
                sessions_paid = 0
                sessions_used = 0
                remaining_sessions = 0
                paid_status = "Unpaid"

            summaries.append(
                {
                    "id": student_id,
                    "name": row["name"],
                    "phone": row["phone"] or "",
                    "notes": row["notes"] or "",
                    "paid_status": paid_status,
                    "payment_date": payment_date,
                    "sessions_paid": sessions_paid,
                    "sessions_used": sessions_used,
                    "remaining_sessions": remaining_sessions,
                    # Kept for compatibility with older screens.
                    "status": paid_status,
                    "paid_info": (
                        f"{payment_date} / {sessions_paid}"
                        if latest_payment
                        else "-"
                    ),
                }
            )

        return summaries
