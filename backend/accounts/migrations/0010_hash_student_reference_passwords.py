"""Migration: hash any existing plain-text StudentReference.password values.

This is a one-time data migration that runs after the schema migration
0008_studentreference. For each StudentReference row that has a non-empty
password that does NOT look like a Django hash (i.e. it doesn't start with
'pbkdf2_', 'argon2', 'bcrypt', 'scrypt', 'md5$', 'sha1$'), we hash it in
place using Django's default hasher (PBKDF2).

Rows with empty passwords are left untouched — an empty password means
"no password required for self-registration" in the legacy logic, and we
preserve that semantics.

This migration is idempotent: re-running it on already-hashed rows is a
no-op because identify_hasher() will succeed and we skip the row.
"""
from django.db import migrations
from django.contrib.auth.hashers import make_password, identify_hasher


def hash_plain_text_passwords(apps, schema_editor):
    StudentReference = apps.get_model('accounts', 'StudentReference')
    updated = 0
    for ref in StudentReference.objects.exclude(password='').exclude(password__isnull=True):
        try:
            # If we can identify a hasher, the password is already hashed.
            identify_hasher(ref.password)
            continue
        except Exception:
            # Plain-text value — hash it.
            ref.password = make_password(ref.password)
            ref.save(update_fields=['password'])
            updated += 1
    if updated:
        print(f'\n  [hash_plain_text_passwords] Hashed {updated} plain-text passwords.')


def unhash_passwords(apps, schema_editor):
    """No-op reverse migration.

    We cannot recover the original plain-text passwords, so the reverse
    direction simply leaves the hashed values in place.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_otpcode'),
    ]

    operations = [
        migrations.RunPython(hash_plain_text_passwords, unhash_passwords),
    ]
