from django.db import migrations, models


def add_file_column_if_missing(apps, schema_editor):
    WorkflowFieldResponse = apps.get_model('workflow', 'WorkflowFieldResponse')
    table_name = WorkflowFieldResponse._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if 'file' in columns:
        return

    field = models.FileField(
        upload_to='workflow_uploads/%Y/%m/',
        blank=True,
        null=True,
    )
    field.set_attributes_from_name('file')
    schema_editor.add_field(WorkflowFieldResponse, field)


def remove_file_column_if_present(apps, schema_editor):
    WorkflowFieldResponse = apps.get_model('workflow', 'WorkflowFieldResponse')
    table_name = WorkflowFieldResponse._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if 'file' not in columns:
        return

    field = models.FileField(
        upload_to='workflow_uploads/%Y/%m/',
        blank=True,
        null=True,
    )
    field.set_attributes_from_name('file')
    schema_editor.remove_field(WorkflowFieldResponse, field)


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0013_workflow_stage_optional_closing'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_file_column_if_missing,
                    remove_file_column_if_present,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='workflowfieldresponse',
                    name='file',
                    field=models.FileField(
                        blank=True,
                        null=True,
                        upload_to='workflow_uploads/%Y/%m/',
                    ),
                ),
            ],
        ),
    ]
