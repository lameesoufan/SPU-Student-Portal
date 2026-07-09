"""Migration 0006 — Add discussion_duration to CommitteeTemplate."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('committees', '0005_scheduling'),
    ]

    operations = [
        migrations.AddField(
            model_name='committeetemplate',
            name='discussion_duration',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='مدة المناقشة لكل مشروع بالدقائق (مثال: 15، 20، 30). مطلوبة لتشغيل الـ Solver — تُنتقل للـ Committees المُنشأة.',
                null=True,
            ),
        ),
    ]
