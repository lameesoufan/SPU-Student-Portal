from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def backfill_supervisor_decisions(apps, schema_editor):
    Proposal = apps.get_model('projects', 'StudentIdeaProposal')
    Decision = apps.get_model('projects', 'ProposalSupervisorDecision')

    for proposal in Proposal.objects.all().iterator():
        if proposal.status in ('pending_hod', 'assigned'):
            decision_status = 'approved'
        elif proposal.status == 'rejected':
            decision_status = 'rejected'
        else:
            decision_status = 'pending'

        if proposal.supervisor_id:
            Decision.objects.get_or_create(
                proposal_id=proposal.id,
                supervisor_id=proposal.supervisor_id,
                defaults={
                    'is_primary': True,
                    'status': decision_status,
                    'is_active': True,
                },
            )

        for supervisor in proposal.co_supervisors.all():
            Decision.objects.get_or_create(
                proposal_id=proposal.id,
                supervisor_id=supervisor.id,
                defaults={
                    'is_primary': False,
                    'status': decision_status,
                    'is_active': True,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0019_ideaapplication_unique_active_application_per_student'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='studentideaproposal',
            name='status',
            field=models.CharField(
                choices=[
                    ('awaiting_members', 'Awaiting Member Confirmation'),
                    ('pending_supervisor', 'Pending Supervisor Approval'),
                    ('supervisor_action_required', 'Supervisor Action Required'),
                    ('pending_hod', 'Pending HoD Review'),
                    ('assigned', 'Assigned'),
                    ('rejected', 'Rejected'),
                ],
                default='pending_supervisor',
                max_length=32,
            ),
        ),
        migrations.RemoveConstraint(
            model_name='studentideaproposal',
            name='unique_active_proposal_per_student',
        ),
        migrations.AddConstraint(
            model_name='studentideaproposal',
            constraint=models.UniqueConstraint(
                condition=Q(status__in=[
                    'awaiting_members',
                    'pending_supervisor',
                    'supervisor_action_required',
                    'pending_hod',
                    'assigned',
                ]),
                fields=('student',),
                name='unique_active_proposal_per_student',
            ),
        ),
        migrations.AddField(
            model_name='proposalinvitation',
            name='rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='ProposalSupervisorDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_primary', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('rejection_reason', models.TextField(blank=True)),
                ('responded_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('proposal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='supervisor_decisions', to='projects.studentideaproposal')),
                ('supervisor', models.ForeignKey(limit_choices_to={'role__in': ['doctor', 'hod']}, on_delete=django.db.models.deletion.CASCADE, related_name='proposal_supervisor_decisions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['supervisor', 'status', 'is_active'], name='projects_pr_supervi_bf029d_idx'),
                    models.Index(fields=['proposal', 'is_active', 'status'], name='projects_pr_proposa_6b151a_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(fields=('proposal', 'supervisor'), name='unique_supervisor_decision_per_proposal'),
                ],
            },
        ),
        migrations.RunPython(backfill_supervisor_decisions, migrations.RunPython.noop),
    ]
