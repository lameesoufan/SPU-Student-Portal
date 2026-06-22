"""Allow HoD to submit project ideas (auto-approved).

- Change ProjectIdea.doctor limit_choices_to from {'role': 'doctor'}
  to {'role__in': ['doctor', 'hod']}.
- This is a Django-level constraint only (no DB column change),
  so this migration is a no-op at the database level.
"""

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0011_alter_ideaapplication_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectidea',
            name='doctor',
            field=models.ForeignKey(
                limit_choices_to={'role__in': ['doctor', 'hod']},
                on_delete=models.deletion.CASCADE,
                related_name='project_ideas',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]