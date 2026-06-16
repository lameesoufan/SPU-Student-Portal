from django.contrib.auth import get_user_model
User = get_user_model()
students = User.objects.filter(role='student')
print(f'Total students: {students.count()}')
for u in students:
    print(f'  - {u.username} | {u.get_full_name() or u.first_name} | {u.email or "no email"}')