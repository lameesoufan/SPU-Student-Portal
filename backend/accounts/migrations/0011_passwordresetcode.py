from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('accounts', '0010_hash_student_reference_passwords')]
    operations = [
        migrations.CreateModel(
            name='PasswordResetCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code_hash', models.CharField(max_length=128)),
                ('session_token', models.CharField(db_index=True, max_length=96, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('is_used', models.BooleanField(default=False)),
                ('failed_attempts', models.PositiveSmallIntegerField(default=0)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='password_reset_codes', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(model_name='passwordresetcode', index=models.Index(fields=['session_token'], name='accounts_pa_session_2e0c28_idx')),
        migrations.AddIndex(model_name='passwordresetcode', index=models.Index(fields=['expires_at'], name='accounts_pa_expires_3f81d1_idx')),
    ]
