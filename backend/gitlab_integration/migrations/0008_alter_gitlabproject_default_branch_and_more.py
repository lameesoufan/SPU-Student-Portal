# Generated to align GitLabProject fields with the current model definition.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gitlab_integration', '0007_gitlabproject_is_orphaned'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gitlabproject',
            name='default_branch',
            field=models.CharField(blank=True, default='main', max_length=100),
        ),
        migrations.AlterField(
            model_name='gitlabproject',
            name='webhook_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
