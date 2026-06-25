from django.db import migrations, models
import workflow.models


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0008_alter_projectworkflow_project_board'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workflowtemplate',
            name='department',
            field=models.CharField(
                blank=True,
                choices=workflow.models.DEPARTMENTS,
                help_text='Leave empty for a global template accessible to all departments',
                max_length=50,
                null=True,
            ),
        ),
    ]