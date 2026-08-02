#!/usr/bin/env python
"""Add a student manually to StudentReference for testing."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from accounts.models import StudentReference, User

# بيانات الطالب من Excel
university_id = '43100'
full_name = 'Ahmad Al-Rashid'
email = 'marmichael015@gmail.com'
department = 'software_engineering'
password = university_id  # استخدام الرقم الجامعي كـ password

try:
    # البحث عن admin/dean لـ uploaded_by
    admin_user = User.objects.filter(role__in=['dean', 'admin']).first()
    
    # إنشاء أو تحديث الطالب
    student, created = StudentReference.objects.update_or_create(
        university_id=university_id,
        defaults={
            'full_name': full_name,
            'email': email,
            'department': department,
            'password': password,
            'uploaded_by': admin_user,
        }
    )
    
    if created:
        print(f"✅ Student CREATED successfully!")
    else:
        print(f"✅ Student UPDATED successfully!")
    
    print(f"\n📋 Student Details:")
    print(f"   University ID: {student.university_id}")
    print(f"   Full Name: {student.full_name}")
    print(f"   Email: {student.email}")
    print(f"   Department: {student.department}")
    print(f"   Password: {student.password}")
    print(f"\n🔐 Login Credentials:")
    print(f"   Username: {student.university_id}")
    print(f"   Password: {student.password}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
