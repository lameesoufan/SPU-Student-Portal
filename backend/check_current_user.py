#!/usr/bin/env python
"""Check current logged in user from the screenshot."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from accounts.models import User

# من الصورة، المستخدم اسمه "dean"
username = 'dean'
try:
    user = User.objects.get(username=username)
    print(f"✅ User found: {user.username}")
    print(f"   Role: {user.role}")
    print(f"   Is Admin: {user.role == 'admin'}")
    print(f"   Is Dean: {user.role == 'dean'}")
    print(f"   Is Staff: {user.is_staff}")
    print(f"   Is Superuser: {user.is_superuser}")
except User.DoesNotExist:
    print(f"❌ User '{username}' NOT FOUND")
    print(f"\nAll users:")
    for u in User.objects.all()[:10]:
        print(f"  - {u.username} (role: {u.role})")
