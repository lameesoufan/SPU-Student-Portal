"""
Migration 0002 — Drop legacy columns from committees_committeetemplate.

PROBLEM:
    The DB table still has `committees_count` and `max_projects_per_committee`
    columns (NOT NULL), but the model no longer has these fields. This causes
    a NOT NULL violation whenever a new template is inserted.

WHY THIS HAPPENED:
    - Original 0001_initial.py (with the two fields) was already applied to DB.
    - We replaced 0001_initial.py with a new version (without the fields).
    - Django sees "0001_initial is already applied" and skips it.
    - Result: model and DB are out of sync.

WHY RunSQL instead of RemoveField:
    Django's RemoveField operation requires the field to exist in the migration
    state. Since the new 0001_initial.py doesn't have these fields, RemoveField
    fails with KeyError. RunSQL bypasses the migration state and just executes
    raw SQL on the DB.

USAGE:
    1. Save this file as: backend/committees/migrations/0002_drop_legacy_columns.py
    2. Run: python manage.py migrate committees
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('committees', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE committees_committeetemplate
                    DROP COLUMN IF EXISTS committees_count,
                    DROP COLUMN IF EXISTS max_projects_per_committee;
            """,
            reverse_sql="""
                ALTER TABLE committees_committeetemplate
                    ADD COLUMN committees_count integer NOT NULL DEFAULT 1,
                    ADD COLUMN max_projects_per_committee integer NOT NULL DEFAULT 10;
            """,
        ),
    ]
