# Generated migration to add missing fields
# Run this migration with --fake since the columns may already exist in the database

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('gitlab_integration', '0003_rename_created_at_gitlabuser_linked_at_and_more'),  # Replace with your last migration name
    ]

    operations = [
        # GitLabUser: ensure updated_at exists
        migrations.AddField(
            model_name='gitlabuser',
            name='updated_at',
            field=models.DateTimeField(default=timezone.now),
        ),
        # GitLabProject: ensure updated_at exists
        migrations.AddField(
            model_name='gitlabproject',
            name='updated_at',
            field=models.DateTimeField(default=timezone.now),
        ),
        # GitLabCommit: ensure web_url exists
        migrations.AddField(
            model_name='gitlabcommit',
            name='web_url',
            field=models.URLField(blank=True, default=''),
        ),
    ]
