from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0016_ideaapplication_project_type_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='studentideaproposal',
            name='co_supervisors',
            field=models.ManyToManyField(
                blank=True,
                limit_choices_to={'role': 'doctor'},
                related_name='co_supervised_proposals',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
