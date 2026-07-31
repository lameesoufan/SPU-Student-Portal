from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('workflow', '0012_multiple_workflows_per_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowstage',
            name='end_date',
            field=models.DateField(blank=True, help_text='Optional date when the stage closes automatically', null=True),
        ),
        migrations.AddField(
            model_name='workflowstage',
            name='close_notify_before_days',
            field=models.PositiveIntegerField(blank=True, default=1, help_text='Notify before automatic closing', null=True),
        ),
        migrations.AlterField(
            model_name='workflowstageinstance',
            name='status',
            field=models.CharField(choices=[('scheduled', 'Scheduled'), ('pending', 'Pending'), ('in_progress', 'In Progress'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('overdue', 'Overdue'), ('closed', 'Closed')], default='pending', max_length=20),
        ),
    ]
