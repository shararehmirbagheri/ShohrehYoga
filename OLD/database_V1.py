import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "data" / "yoga.db"


class Database:

    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            notes TEXT
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendances(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            sessions_paid INTEGER NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
        """)

        self.conn.commit()

    def add_student(self, name, phone="", notes=""):
        self.cursor.execute(
            """
            INSERT INTO students(name, phone, notes)
            VALUES (?, ?, ?)
            """,
            (name, phone, notes)
        )

        self.conn.commit()

    def get_students(self):
        self.cursor.execute("""
        SELECT id, name, phone, notes
        FROM students
        ORDER BY name
        """)

        return self.cursor.fetchall()

    def student_count(self):
        self.cursor.execute("""
        SELECT COUNT(*)
        FROM students
        """)

        return self.cursor.fetchone()[0]

    def add_attendance(self, student_id, attended_on=None):
        from datetime import date
        attended_on = attended_on or date.today().isoformat()
        self.cursor.execute(
            """
            INSERT INTO attendances(student_id, date)
            VALUES (?, ?)
            """,
            (student_id, attended_on)
        )
        self.conn.commit()

    def attendance_exists(self, student_id, attended_on):
        self.cursor.execute(
            """
            SELECT 1
            FROM attendances
            WHERE student_id = ? AND date = ?
            """,
            (student_id, attended_on)
        )
        return self.cursor.fetchone() is not None

    def get_attendance_records(self):
        self.cursor.execute("""
        SELECT a.id, s.name, a.date
        FROM attendances a
        JOIN students s ON s.id = a.student_id
        ORDER BY a.date DESC
        """)
        return self.cursor.fetchall()

    def add_payment(self, student_id, sessions_paid, payment_date=None):
        from datetime import date
        payment_date = payment_date or date.today().isoformat()
        self.cursor.execute(
            """
            INSERT INTO payments(student_id, payment_date, sessions_paid)
            VALUES (?, ?, ?)
            """,
            (student_id, payment_date, sessions_paid)
        )
        self.conn.commit()

    def get_latest_payment(self, student_id):
        self.cursor.execute(
            """
            SELECT payment_date, sessions_paid
            FROM payments
            WHERE student_id = ?
            ORDER BY payment_date DESC
            LIMIT 1
            """,
            (student_id,)
        )
        return self.cursor.fetchone()

    def get_attendance_count_since(self, student_id, from_date=None):
        if from_date:
            self.cursor.execute(
                """
                SELECT COUNT(*)
                FROM attendances
                WHERE student_id = ? AND date >= ?
                """,
                (student_id, from_date)
            )
        else:
            self.cursor.execute(
                """
                SELECT COUNT(*)
                FROM attendances
                WHERE student_id = ?
                """,
                (student_id,)
            )
        return self.cursor.fetchone()[0]

    def get_student_summaries(self):
        self.cursor.execute("""
        SELECT id, name, phone, notes
        FROM students
        ORDER BY name
        """)
        students = self.cursor.fetchall()

        summaries = []
        for student_id, name, phone, notes in students:
            self.cursor.execute(
                """
                SELECT date
                FROM attendances
                WHERE student_id = ?
                ORDER BY date DESC
                """,
                (student_id,)
            )
            dates = [row[0] for row in self.cursor.fetchall()]
            sessions = len(dates)

            latest_payment = self.get_latest_payment(student_id)
            if latest_payment:
                payment_date, sessions_paid = latest_payment
                used_sessions = self.get_attendance_count_since(student_id, payment_date)
                status = "Red" if used_sessions >= sessions_paid else "Paid"
                paid_info = f"{payment_date} / {sessions_paid}"
            else:
                status = "Unpaid"
                paid_info = "-"

            summaries.append({
                "id": student_id,
                "name": name,
                "phone": phone,
                "notes": notes,
                "sessions": sessions,
                "dates": dates,
                "status": status,
                "paid_info": paid_info,
            })

        return summaries

    def get_student(self, student_id):
        self.cursor.execute(
            """
            SELECT id, name, phone, notes
            FROM students
            WHERE id = ?
            """,
            (student_id,)
        )

        return self.cursor.fetchone()

    def update_student(self, student_id, name, phone="", notes=""):
        self.cursor.execute(
            """
            UPDATE students
            SET name=?, phone=?, notes=?
            WHERE id=?
            """,
            (name, phone, notes, student_id)
        )

        self.conn.commit()

    def delete_student(self, student_id):
        self.cursor.execute(
            """
            DELETE FROM students
            WHERE id=?
            """,
            (student_id,)
        )
        self.cursor.execute(
            """
            DELETE FROM attendances
            WHERE student_id=?
            """,
            (student_id,)
        )
        self.cursor.execute(
            """
            DELETE FROM payments
            WHERE student_id=?
            """,
            (student_id,)
        )

        self.conn.commit()