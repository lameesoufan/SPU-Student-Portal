#!/usr/bin/env python
"""List all students in StudentReference database."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from accounts.models import StudentReference

students = StudentReference.objects.all()
print(f"\n📋 Total students in database: {students.count()}\n")

if students.count() > 0:
    print("=" * 80)
    for student in students:
        print(f"University ID: {student.university_id}")
        print(f"Full Name:     {student.full_name}")
        print(f"Email:         {student.email}")
        print(f"Password:      {student.password}")
        print(f"Department:    {student.department}")
        print("-" * 80)
else:
    print("❌ No students found in database!")
