"""
Migration 0005 — Add CP-SAT scheduling infrastructure.

Adds:
  - New model: Room (simple room: name + capacity + is_active)
  - New model: DoctorWeeklyAvailability (doctor × weekday — full workday)
  - New model: DoctorDateException (doctor × date × type)
  - New model: SolverSettings (per committee_type × semester)
  - New model: SchedulingRun (preview/apply/reject workflow)

Modifies:
  - CommitteeTemplate: add scheduling_mode ('single' | 'multi')
  - Committee: add room (FK PROTECT), scheduled_start, scheduled_end,
    scheduling_group (UUID), manually_scheduled, last_scheduling_run (FK)
"""
import uuid
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('committees', '0004_committee_discussion_duration'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── 1. New model: Room ────────────────────────────────────────────
        migrations.CreateModel(
            name='Room',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='اسم القاعة فقط (مثال: قاعة 201)', max_length=255, unique=True)),
                ('capacity', models.PositiveIntegerField(default=30)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': 'Room',
                'verbose_name_plural': 'Rooms',
            },
        ),
        migrations.AddIndex(
            model_name='room',
            index=models.Index(fields=['is_active'], name='committees_room_active_idx'),
        ),

        # ── 2. New model: DoctorWeeklyAvailability ───────────────────────
        migrations.CreateModel(
            name='DoctorWeeklyAvailability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')], help_text='0=Monday, 6=Sunday')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('doctor', models.ForeignKey(limit_choices_to={'role__in': ['doctor', 'hod']}, on_delete=django.db.models.deletion.CASCADE, related_name='weekly_availability', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Doctor Weekly Availability',
                'verbose_name_plural': 'Doctor Weekly Availabilities',
                'unique_together': {('doctor', 'weekday')},
            },
        ),
        migrations.AddIndex(
            model_name='doctorweeklyavailability',
            index=models.Index(fields=['doctor', 'weekday'], name='committees_dwa_doc_day_idx'),
        ),

        # ── 3. New model: DoctorDateException ────────────────────────────
        migrations.CreateModel(
            name='DoctorDateException',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('exception_type', models.CharField(choices=[('available', 'Available (override)'), ('blocked', 'Blocked (override)')], max_length=10)),
                ('reason', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('doctor', models.ForeignKey(limit_choices_to={'role__in': ['doctor', 'hod']}, on_delete=django.db.models.deletion.CASCADE, related_name='date_exceptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Doctor Date Exception',
                'verbose_name_plural': 'Doctor Date Exceptions',
                'unique_together': {('doctor', 'date')},
            },
        ),
        migrations.AddIndex(
            model_name='doctordateexception',
            index=models.Index(fields=['date'], name='committees_dde_date_idx'),
        ),
        migrations.AddIndex(
            model_name='doctordateexception',
            index=models.Index(fields=['doctor', 'date'], name='committees_dde_doc_date_idx'),
        ),

        # ── 4. New model: SolverSettings ─────────────────────────────────
        migrations.CreateModel(
            name='SolverSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Default', help_text='Human label for this config', max_length=100)),
                ('committee_type', models.CharField(choices=[('seminar_1', 'Seminar 1'), ('seminar_2', 'Seminar 2'), ('technical', 'Technical Committee'), ('final_discussion', 'Final Discussion')], max_length=25)),
                ('semester', models.CharField(max_length=50)),
                ('date_range_start', models.DateField()),
                ('date_range_end', models.DateField()),
                ('workdays', models.JSONField(default=list, help_text='List of weekday ints (0=Monday, 6=Sunday). Example: [5, 6] for Sat+Sun')),
                ('daily_start', models.TimeField(default='09:00')),
                ('daily_end', models.TimeField(default='17:00')),
                ('buffer_between_committees_minutes', models.PositiveIntegerField(default=10, help_text='Buffer (in minutes) added after each committee in the same room')),
                ('max_committees_per_doctor', models.PositiveIntegerField(default=5)),
                ('solver_timeout_seconds', models.PositiveIntegerField(default=30, help_text='Max wall-clock time for CP-SAT solver')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_solver_settings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Solver Settings',
                'verbose_name_plural': 'Solver Settings',
                'ordering': ['-created_at'],
                'unique_together': {('committee_type', 'semester')},
            },
        ),
        migrations.AddIndex(
            model_name='solversettings',
            index=models.Index(fields=['committee_type', 'semester', 'is_active'], name='committees_ss_type_sem_idx'),
        ),

        # ── 5. New model: SchedulingRun ──────────────────────────────────
        migrations.CreateModel(
            name='SchedulingRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('committee_type', models.CharField(choices=[('seminar_1', 'Seminar 1'), ('seminar_2', 'Seminar 2'), ('technical', 'Technical Committee'), ('final_discussion', 'Final Discussion')], max_length=25)),
                ('semester', models.CharField(max_length=50)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('preview', 'Preview Ready'), ('applied', 'Applied'), ('rejected', 'Rejected'), ('failed', 'Failed')], db_index=True, default='pending', max_length=20)),
                ('plan_json', models.JSONField(blank=True, default=dict)),
                ('infeasibility_report', models.JSONField(blank=True, default=list)),
                ('summary_stats', models.JSONField(blank=True, default=dict)),
                ('solver_status', models.CharField(blank=True, choices=[('OPTIMAL', 'Optimal'), ('FEASIBLE', 'Feasible'), ('INFEASIBLE', 'Infeasible'), ('UNKNOWN', 'Unknown (timeout or no solution found)'), ('ERROR', 'Error during solving')], default='', max_length=30)),
                ('solver_wall_time_sec', models.FloatField(default=0)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('requested_by', models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name='requested_scheduling_runs', to=settings.AUTH_USER_MODEL)),
                ('solver_settings', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='runs', to='committees.solversettings')),
            ],
            options={
                'verbose_name': 'Scheduling Run',
                'verbose_name_plural': 'Scheduling Runs',
                'ordering': ['-requested_at'],
            },
        ),
        migrations.AddIndex(
            model_name='schedulingrun',
            index=models.Index(fields=['committee_type', 'semester', 'status'], name='committees_sr_type_sem_idx'),
        ),
        migrations.AddIndex(
            model_name='schedulingrun',
            index=models.Index(fields=['requested_at'], name='committees_sr_req_at_idx'),
        ),

        # ── 6. Add scheduling_mode on CommitteeTemplate ──────────────────
        migrations.AddField(
            model_name='committeetemplate',
            name='scheduling_mode',
            field=models.CharField(
                choices=[('single', 'Single — same committee across all 4 committee types'), ('multi', 'Multi — 4 independent committees per project')],
                default='multi',
                help_text='single: نفس اللجنة تقيّم المشروع في 4 جلسات (أنواع مختلفة). multi: 4 لجان مستقلة لكل مشروع.',
                max_length=10,
            ),
        ),

        # ── 7. Add scheduling fields on Committee ────────────────────────
        migrations.AddField(
            model_name='committee',
            name='room',
            field=models.ForeignKey(
                blank=True, help_text='القاعة المُجدوَلة (PROTECT: لا يمكن حذف قاعة مستخدمة)',
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='committees', to='committees.room',
            ),
        ),
        migrations.AddField(
            model_name='committee',
            name='scheduled_start',
            field=models.DateTimeField(blank=True, help_text='بداية الجلسة الكاملة (تاريخ + وقت)', null=True),
        ),
        migrations.AddField(
            model_name='committee',
            name='scheduled_end',
            field=models.DateTimeField(blank=True, help_text='نهاية الجلسة الكاملة (تاريخ + وقت)', null=True),
        ),
        migrations.AddField(
            model_name='committee',
            name='scheduling_group',
            field=models.UUIDField(
                blank=True, db_index=True, null=True,
                help_text='في وضع single: يربط الـ 4 Committees (للأنواع الأربعة) التي تمثل نفس المشروع بنفس الأطباء',
            ),
        ),
        migrations.AddField(
            model_name='committee',
            name='manually_scheduled',
            field=models.BooleanField(default=False, help_text='True إذا تم تعديل الجدولة يدوياً بعد Apply'),
        ),
        migrations.AddField(
            model_name='committee',
            name='last_scheduling_run',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='committees', to='committees.schedulingrun',
            ),
        ),
    ]
