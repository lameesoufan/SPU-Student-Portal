# Generated manually for committee redistribution safety and audit logging.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('committees', '0009_remove_solversettings_max_committees_per_doctor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommitteeDistributionAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('outcome', models.CharField(choices=[('executed', 'Executed'), ('blocked', 'Blocked')], default='executed', max_length=20)),
                ('scheduling_mode', models.CharField(choices=[('single', 'Single — same committee across all 4 committee types'), ('multi', 'Multi — 4 independent committees per project')], max_length=10)),
                ('semester', models.CharField(blank=True, default='', max_length=50)),
                ('template_ids', models.JSONField(blank=True, default=list)),
                ('affected_scopes', models.JSONField(blank=True, default=list)),
                ('committees_before', models.PositiveIntegerField(default=0)),
                ('committees_after', models.PositiveIntegerField(default=0)),
                ('draft_count', models.PositiveIntegerField(default=0)),
                ('final_grade_count', models.PositiveIntegerField(default=0)),
                ('draft_loss_confirmed', models.BooleanField(default=False)),
                ('result_summary', models.JSONField(blank=True, default=dict)),
                ('message', models.TextField(blank=True, default='')),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='committee_distribution_audits', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Committee Distribution Audit',
                'verbose_name_plural': 'Committee Distribution Audits',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='committeedistributionaudit',
            index=models.Index(fields=['created_at', 'outcome'], name='committees_created_139c6d_idx'),
        ),
        migrations.AddIndex(
            model_name='committeedistributionaudit',
            index=models.Index(fields=['semester', 'scheduling_mode'], name='committees_semeste_75b17e_idx'),
        ),
    ]
