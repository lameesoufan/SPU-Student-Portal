"""
Migration 0007 — Drop the restrictive unique_together on Committee.

PROBLEM:
  The unique_together = ('template', 'sequence_number') constraint was
  designed for MULTI mode where each template has exactly 1 committee.
  In SINGLE mode, multiple committees share the same template (4 per
  project × N projects), so this constraint blocks re-distribution.

FIX:
  Drop the unique_together. The original purpose (preventing duplicate
  committees in MULTI mode) is already handled by the idempotent
  spawn_committee_for_template() function.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('committees', '0006_committeetemplate_discussion_duration'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='committee',
            unique_together=set(),  # remove the constraint entirely
        ),
    ]
