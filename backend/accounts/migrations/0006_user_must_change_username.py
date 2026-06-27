from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_unique_hod_per_department'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='must_change_username',
            field=models.BooleanField(default=False),
        ),
    ]