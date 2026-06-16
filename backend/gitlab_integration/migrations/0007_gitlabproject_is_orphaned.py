# M-15 Fix: إضافة حقل is_orphaned لتتبع المستودعات المحذوفة يدوياً من GitLab

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gitlab_integration', '0006_alter_gitlabuser_access_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='gitlabproject',
            name='is_orphaned',
            field=models.BooleanField(
                default=False,
                help_text='True إذا حُذف المستودع يدوياً من GitLab — يجب إنشاء مستودع جديد'
            ),
        ),
    ]