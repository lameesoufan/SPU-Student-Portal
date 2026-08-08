import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import migrations, models

import grades.models


def _fernet():
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(key)


def encrypt_existing_values(apps, schema_editor):
    GradeAuditLog = apps.get_model('grades', 'GradeAuditLog')
    cipher = _fernet()

    for row in GradeAuditLog.objects.all().iterator():
        updates = {}
        for field_name in ('old_value', 'new_value'):
            value = getattr(row, field_name)
            if value in (None, ''):
                continue
            raw = str(value)
            try:
                cipher.decrypt(raw.encode())
            except (InvalidToken, ValueError):
                updates[field_name] = cipher.encrypt(raw.encode()).decode()
        if updates:
            GradeAuditLog.objects.filter(pk=row.pk).update(**updates)


def decrypt_existing_values(apps, schema_editor):
    GradeAuditLog = apps.get_model('grades', 'GradeAuditLog')
    cipher = _fernet()

    for row in GradeAuditLog.objects.all().iterator():
        updates = {}
        for field_name in ('old_value', 'new_value'):
            value = getattr(row, field_name)
            if value in (None, ''):
                continue
            try:
                updates[field_name] = cipher.decrypt(str(value).encode()).decode()
            except (InvalidToken, ValueError):
                continue
        if updates:
            GradeAuditLog.objects.filter(pk=row.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [
        ('grades', '0003_committeegradingmode_doctorgradedraft'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gradeauditlog',
            name='old_value',
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.AlterField(
            model_name='gradeauditlog',
            name='new_value',
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.RunPython(encrypt_existing_values, decrypt_existing_values),
        migrations.AlterField(
            model_name='gradeauditlog',
            name='old_value',
            field=grades.models.EncryptedScoreField(blank=True, max_length=512, null=True),
        ),
        migrations.AlterField(
            model_name='gradeauditlog',
            name='new_value',
            field=grades.models.EncryptedScoreField(blank=True, max_length=512, null=True),
        ),
    ]
