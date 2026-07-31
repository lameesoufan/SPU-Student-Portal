from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0003_notification_event_key_and_workflow_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notif_type',
            field=models.CharField(choices=[('idea_submitted', 'Idea Submitted'), ('idea_approved', 'Idea Approved'), ('idea_rejected', 'Idea Rejected'), ('proposal_submitted', 'Proposal Submitted'), ('proposal_approved_sup', 'Proposal Approved by Supervisor'), ('proposal_approved_hod', 'Proposal Approved by HoD'), ('proposal_rejected', 'Proposal Rejected'), ('proposal_assigned', 'Proposal Assigned'), ('application_submitted', 'Application Submitted'), ('application_approved_doc', 'Application Approved by Doctor'), ('application_approved_hod', 'Application Approved by HoD'), ('application_rejected', 'Application Rejected'), ('application_registered', 'Application Registered'), ('invitation_received', 'Invitation Received'), ('invitation_accepted', 'Invitation Accepted'), ('invitation_rejected', 'Invitation Rejected'), ('workflow_stage_reminder', 'Workflow Stage Reminder'), ('workflow_stage_opened', 'Workflow Stage Opened'), ('workflow_stage_closing_reminder', 'Workflow Stage Closing Reminder'), ('workflow_stage_closed', 'Workflow Stage Closed')], max_length=40),
        ),
    ]
