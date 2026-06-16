from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0011_alter_ideaapplication_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ideaapplication',
            name='team_size_reason',
            field=models.TextField(blank=True, help_text='Required when team_size is 1 or 4'),
        ),
    ]