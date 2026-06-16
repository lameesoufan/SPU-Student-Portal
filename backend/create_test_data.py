"""
SPU Portal — Load Test Data Setup
==================================
سكربت لإنشاء بيانات تجريبية لاختبار الأداء والتحمل

Usage:
    python manage.py shell < create_test_data.py
    # أو:
    python manage.py shell
    >>> exec(open('create_test_data.py').read())
"""

import random
import string
from django.contrib.auth import get_user_model

User = get_user_model()

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

PASSWORD = "TestPass123!"
NUM_STUDENTS = 10
NUM_DOCTORS = 5
NUM_HODS = 2

# ═══════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════

def random_name(prefix, length=4):
    return f"{prefix}{''.join(random.choices(string.digits, k=length))}"

# ═══════════════════════════════════════════════════════════════
# Create Departments
# ═══════════════════════════════════════════════════════════════

from accounts.models import Department

departments = []
dept_names = ["Computer Science", "Software Engineering", "Information Technology", "Computer Engineering"]

for name in dept_names:
    dept, created = Department.objects.get_or_create(name=name)
    departments.append(dept)
    if created:
        print(f"  Created department: {name}")

# ═══════════════════════════════════════════════════════════════
# Create Dean
# ═══════════════════════════════════════════════════════════════

dean, created = User.objects.get_or_create(
    username="dean1",
    defaults={
        "email": "dean1@spu.edu.sy",
        "first_name": "Dean",
        "last_name": "Admin",
        "role": "dean",
        "must_change_password": False,
    }
)
if created:
    dean.set_password(PASSWORD)
    dean.save()
    print(f"  Created dean: {dean.username}")
else:
    dean.set_password(PASSWORD)
    dean.must_change_password = False
    dean.save()
    print(f"  Dean already exists, password reset: {dean.username}")

# ═══════════════════════════════════════════════════════════════
# Create HoDs
# ═══════════════════════════════════════════════════════════════

hods = []
for i in range(NUM_HODS):
    username = f"hod{i+1}"
    dept = departments[i % len(departments)]
    hod, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": f"{username}@spu.edu.sy",
            "first_name": f"HoD",
            "last_name": f"User{i+1}",
            "role": "hod",
            "department": dept,
            "must_change_password": False,
        }
    )
    if created:
        hod.set_password(PASSWORD)
        hod.save()
        print(f"  Created HoD: {hod.username} ({dept.name})")
    else:
        hod.set_password(PASSWORD)
        hod.must_change_password = False
        hod.department = dept
        hod.save()
        print(f"  HoD already exists, updated: {hod.username}")
    hods.append(hod)

    # تعيين كرئيس قسم
    dept.hod = hod
    dept.save()

# ═══════════════════════════════════════════════════════════════
# Create Doctors
# ═══════════════════════════════════════════════════════════════

doctors = []
for i in range(NUM_DOCTORS):
    username = f"doctor{i+1}"
    dept = departments[i % len(departments)]
    doctor, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": f"{username}@spu.edu.sy",
            "first_name": f"Doctor",
            "last_name": f"User{i+1}",
            "role": "doctor",
            "department": dept,
            "must_change_password": False,
        }
    )
    if created:
        doctor.set_password(PASSWORD)
        doctor.save()
        print(f"  Created Doctor: {doctor.username} ({dept.name})")
    else:
        doctor.set_password(PASSWORD)
        doctor.must_change_password = False
        doctor.department = dept
        doctor.save()
        print(f"  Doctor already exists, updated: {doctor.username}")
    doctors.append(doctor)

# ═══════════════════════════════════════════════════════════════
# Create Students
# ═══════════════════════════════════════════════════════════════

students = []
for i in range(NUM_STUDENTS):
    username = f"student{i+1}"
    dept = departments[i % len(departments)]
    student, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": f"{username}@spu.edu.sy",
            "first_name": f"Student",
            "last_name": f"User{i+1}",
            "role": "student",
            "department": dept,
            "must_change_password": False,
        }
    )
    if created:
        student.set_password(PASSWORD)
        student.save()
        print(f"  Created Student: {student.username} ({dept.name})")
    else:
        student.set_password(PASSWORD)
        student.must_change_password = False
        student.department = dept
        student.save()
        print(f"  Student already exists, updated: {student.username}")
    students.append(student)

# ═══════════════════════════════════════════════════════════════
# Create Project Ideas (by doctors)
# ═══════════════════════════════════════════════════════════════

from projects.models import ProjectIdea

idea_titles = [
    "Smart Campus Navigation System",
    "AI-Powered Attendance Tracker",
    "Online Exam Proctoring System",
    "Student Mental Health Chatbot",
    "Library Resource Management System",
    "University Event Management Platform",
    "Automated Grading System",
    "Research Paper Recommendation Engine",
    "Virtual Lab Simulation Platform",
    "Campus Lost & Found App",
]

ideas = []
for i, title in enumerate(idea_titles):
    doctor = doctors[i % len(doctors)]
    dept = doctor.department
    idea, created = ProjectIdea.objects.get_or_create(
        title=title,
        defaults={
            "doctor": doctor,
            "department": dept,
            "description": f"Description for {title}. This project aims to develop a comprehensive solution for university students and staff.",
            "required_skills": "Python, Django, React",
            "max_team_size": 4,
            "status": "approved",
        }
    )
    if created:
        print(f"  Created Idea: {title}")
    else:
        print(f"  Idea already exists: {title}")
    ideas.append(idea)

# ═══════════════════════════════════════════════════════════════
# Create Project Boards for approved ideas
# ═══════════════════════════════════════════════════════════════

from project_management.models import ProjectBoard

boards = []
for i, idea in enumerate(ideas[:5]):
    # إنشاء فريق من 3 طلاب
    team = students[i*2 % len(students): i*2 % len(students) + 3]
    if len(team) < 2:
        team = students[:3]

    board, created = ProjectBoard.objects.get_or_create(
        name=f"Board: {idea.title}",
        defaults={
            "supervisor": idea.doctor,
            "department": idea.department,
        }
    )
    if created:
        board.members.set(team)
        print(f"  Created Board: {board.name}")
    else:
        print(f"  Board already exists: {board.name}")
    boards.append(board)

# ═══════════════════════════════════════════════════════════════
# Create Workflow Template
# ═══════════════════════════════════════════════════════════════

from workflow.models import WorkflowTemplate, WorkflowStageTemplate

template, created = WorkflowTemplate.objects.get_or_create(
    name="Standard Project Workflow",
    defaults={
        "department": departments[0],
        "created_by": hods[0],
        "description": "Standard workflow for all CS department projects",
    }
)

if created:
    stages_data = [
        {"name": "Proposal Submission", "order": 1, "is_recurring": False},
        {"name": "Literature Review", "order": 2, "is_recurring": False},
        {"name": "Design Phase", "order": 3, "is_recurring": False},
        {"name": "Implementation", "order": 4, "is_recurring": True},
        {"name": "Testing", "order": 5, "is_recurring": True},
        {"name": "Final Presentation", "order": 6, "is_recurring": False},
    ]
    for stage_data in stages_data:
        WorkflowStageTemplate.objects.create(
            template=template,
            **stage_data,
        )
    print(f"  Created Workflow Template: {template.name} ({len(stages_data)} stages)")
else:
    print(f"  Workflow Template already exists: {template.name}")

# ═══════════════════════════════════════════════════════════════
# Create Dynamic Form
# ═══════════════════════════════════════════════════════════════

from dy_forms.models import DynamicForm

form, created = DynamicForm.objects.get_or_create(
    department=departments[0],
    context="propose",
    defaults={
        "created_by": hods[0],
    }
)

if created:
    from dy_forms.models import FormField
    fields_data = [
        {"label": "Project Title", "field_type": "text", "required": True, "order": 1},
        {"label": "Project Description", "field_type": "textarea", "required": True, "order": 2},
        {"label": "Technology Stack", "field_type": "text", "required": True, "order": 3},
        {"label": "Team Size", "field_type": "number", "required": True, "order": 4},
        {"label": "Project Type", "field_type": "select", "required": True, "order": 5,
         "options": ["Web Application", "Mobile App", "Desktop App", "AI/ML Project"]},
    ]
    for field_data in fields_data:
        options = field_data.pop("options", None)
        field = FormField.objects.create(form=form, **field_data)
        if options:
            field.options = options
            field.save()
    print(f"  Created Dynamic Form: {form} ({len(fields_data)} fields)")
else:
    print(f"  Dynamic Form already exists: {form}")

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("  Test Data Summary")
print("=" * 60)
print(f"  Departments:    {Department.objects.count()}")
print(f"  Dean:           {User.objects.filter(role='dean').count()}")
print(f"  HoDs:           {User.objects.filter(role='hod').count()}")
print(f"  Doctors:        {User.objects.filter(role='doctor').count()}")
print(f"  Students:       {User.objects.filter(role='student').count()}")
print(f"  Project Ideas:  {ProjectIdea.objects.count()}")
print(f"  Project Boards: {ProjectBoard.objects.count()}")
print(f"  WF Templates:   {WorkflowTemplate.objects.count()}")
print(f"  Dynamic Forms:  {DynamicForm.objects.count()}")
print("=" * 60)
print(f"\n  All passwords: {PASSWORD}")
print("  Ready for Locust load testing!")
print("=" * 60)