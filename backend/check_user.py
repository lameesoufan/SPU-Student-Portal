#!/usr/bin/env python
"""Check if student exists in User table."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from accounts.models import User

username = '428100'
try:
    user = User.objects.get(username=username)
    print(f"✅ User found: {user.username}")
    print(f"   Email: {user.email}")
    print(f"   Role: {user.role}")
    print(f"   First Name: {user.first_name}")
    print(f"   Last Name: {user.last_name}")
    print(f"   Department: {user.department}")
except User.DoesNotExist:
    print(f"❌ User '{username}' NOT FOUND in User table")
    print(f"\nTotal students: {User.objects.filter(role='student').count()}")
    print("\nFirst 5 students:")
    for u in User.objects.filter(role='student')[:5]:
        print(f"  - {u.username}: {u.first_name} {u.last_name} ({u.email})")
