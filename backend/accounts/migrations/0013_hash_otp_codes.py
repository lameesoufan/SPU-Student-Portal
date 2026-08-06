from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations, models


def hash_existing_otp_codes(apps, schema_editor):
    """Convert any legacy plain-text OTP values to Django password hashes."""
    OTPCode = apps.get_model('accounts', 'OTPCode')
    for otp in OTPCode.objects.all().iterator():
        try:
            identify_hasher(otp.code_hash)
        except ValueError:
            otp.code_hash = make_password(otp.code_hash)
            otp.save(update_fields=['code_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_emailchangecode'),
    ]

    operations = [
        migrations.RenameField(
            model_name='otpcode',
            old_name='code',
            new_name='code_hash',
        ),
        migrations.AlterField(
            model_name='otpcode',
            name='code_hash',
            field=models.CharField(max_length=128),
        ),
        # Intentionally irreversible: hashed OTPs cannot be restored to plain text.
        migrations.RunPython(hash_existing_otp_codes),
    ]
