from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0004_remove_projectworkflow_unique_active_workflow_per_project_board_and_more'),
    ]

    operations = [
        # إزالة القيد القديم اللي بيمنع تكرار نفس المرحلة بنفس المشروع
        # واستبداله بقيد جديد يسمح بالتكرار بس برقم تكرار مختلف
        migrations.AlterUniqueTogether(
            name='workflowstageinstance',
            unique_together=set(),  # إزالة unique_together القديم
        ),
        migrations.AddConstraint(
            model_name='workflowstageinstance',
            constraint=models.UniqueConstraint(
                fields=['project_workflow', 'stage', 'occurrence_number'],
                name='unique_stage_occurrence_per_workflow',
            ),
        ),
    ]