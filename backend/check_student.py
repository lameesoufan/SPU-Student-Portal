#!/usr/bin/env python
"""Quick script to check if student exists in database."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from accounts.models import StudentReference

university_id = '428100'
try:
    student = StudentReference.objects.get(university_id=university_id)
    print(f"✅ Student found!")
    print(f"   University ID: {student.university_id}")
    print(f"   Full Name: {student.full_name}")
    print(f"   Email: {student.email}")
    print(f"   Password: {student.password}")
    print(f"   Department: {student.department}")
except StudentReference.DoesNotExist:
    print(f"❌ Student with ID '{university_id}' NOT FOUND in database")
    print(f"\nTotal students in database: {StudentReference.objects.count()}")
    if StudentReference.objects.count() > 0:
        print("\nFirst 5 students:")
        for s in StudentReference.objects.all()[:5]:
            print(f"  - {s.university_id}: {s.full_name}")
