# Generated to align the database schema with ProjectWorkflow's active-only constraint.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project_management', '0003_activitylog_project_man_board_i_3bf52e_idx_and_more'),
        ('workflow', '0009_workflowtemplate_department_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectworkflow',
            name='project_board',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='workflows',
                to='project_management.projectboard',
            ),
        ),
    ]
