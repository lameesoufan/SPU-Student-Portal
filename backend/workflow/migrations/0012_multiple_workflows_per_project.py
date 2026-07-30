from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def populate_assigned_by(apps, schema_editor):
    ProjectWorkflow = apps.get_model('workflow', 'ProjectWorkflow')
    for workflow in ProjectWorkflow.objects.select_related('template__created_by').all():
        workflow.assigned_by_id = workflow.template.created_by_id
        workflow.save(update_fields=['assigned_by'])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workflow', '0010_alter_projectworkflow_project_board'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectworkflow',
            name='assigned_by',
            field=models.ForeignKey(blank=True, help_text='The doctor or HOD who assigned this workflow to the project', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assigned_project_workflows', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(populate_assigned_by, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='projectworkflow',
            name='unique_active_workflow_per_project_board',
        ),
        migrations.AddConstraint(
            model_name='projectworkflow',
            constraint=models.UniqueConstraint(condition=Q(is_active=True), fields=('project_board', 'assigned_by'), name='unique_active_workflow_per_project_assigner'),
        ),
    ]
