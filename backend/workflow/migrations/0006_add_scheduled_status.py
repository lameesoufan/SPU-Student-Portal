from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0005_fix_recurring_unique_constraint'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflowstageinstance',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Scheduled'),
                    ('pending', 'Pending'),
                    ('in_progress', 'In Progress'),
                    ('submitted', 'Submitted'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                    ('overdue', 'Overdue'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]