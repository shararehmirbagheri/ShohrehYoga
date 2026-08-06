from database import Database

db = Database()

for student in db.get_students():
    print(student[1])

print()
print("Total:", db.student_count())