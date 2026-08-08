"""Service tests for committee creation, project collection, and distribution."""

from datetime import timedelta

import pytest
from django.utils import timezone

from committees.models import (
    ALL_COMMITTEE_TYPES,
    Committee,
    CommitteeDistributionAudit,
    CommitteeTemplate,
)
from committees.services import (
    CollectedProject,
    DistributionPlan,
    RedistributionSafetyError,
    TypeDistribution,
    apply_distribution_plan,
    build_distribution_plan,
    build_distribution_plan_for_combo,
    collect_projects_for_template,
    copy_template,
    distribute_projects_to_committees,
    get_dashboard_warnings,
    get_doctor_workload,
    get_redistribution_safety,
    spawn_committee_for_template,
    spawn_committees_for_template,
)
from grades.models import DoctorGradeDraft, ProjectGrade
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    ProposalInvitation,
    StudentIdeaProposal,
    TeamInvitation,
)

pytestmark = pytest.mark.django_db


def create_template(doctor, **overrides):
    values = {
        "name": "Committee Template",
        "committee_type": "seminar_1",
        "department": "software_engineering",
        "project_type": "seasonal",
        "semester": "Fall 2026",
        "chair": doctor,
        "created_by": doctor,
        "discussion_duration": 20,
    }
    values.update(overrides)
    return CommitteeTemplate.objects.create(**values)


def create_committee(doctor, **overrides):
    template = overrides.pop("template", None) or create_template(doctor)
    values = {
        "template": template,
        "sequence_number": 1,
        "committee_type": template.committee_type,
        "department": template.department,
        "project_type": template.project_type,
        "semester": template.semester,
        "chair": template.chair,
        "discussion_duration": template.discussion_duration,
    }
    values.update(overrides)
    return Committee.objects.create(**values)


def create_proposal(student, doctor, **overrides):
    values = {
        "student": student,
        "supervisor": doctor,
        "title": "Student Project",
        "description": "Description",
        "department": "software_engineering",
        "team_size": 1,
        "project_type": "seasonal",
        "status": "assigned",
        "operational_status": "active",
    }
    values.update(overrides)
    return StudentIdeaProposal.objects.create(**values)


def create_idea_application(student, doctor, **overrides):
    idea_values = {
        "doctor": doctor,
        "title": "Doctor Project",
        "description": "Description",
        "department": "software_engineering",
        "project_type": "seasonal",
        "status": "approved",
    }
    idea_values.update(overrides.pop("idea", {}))
    idea = ProjectIdea.objects.create(**idea_values)
    values = {
        "idea": idea,
        "student": student,
        "team_size": 1,
        "project_type": idea.project_type,
        "status": "registered",
        "operational_status": "active",
    }
    values.update(overrides)
    return IdeaApplication.objects.create(**values)


def collected(source="StudentIdeaProposal", project_id=1, title="Project"):
    return CollectedProject(
        source=source,
        id=project_id,
        title=title,
        department="software_engineering",
        project_type="seasonal",
        supervisor_id=10,
        supervisor_name="Supervisor",
        student_id=20,
        student_name="Student",
        team_size=1,
        active_students=[{"id": 20, "status": "active"}],
        active_team_size=1,
        original_team_size=1,
    )


class TestRedistributionSafety:
    def test_empty_scope_has_no_impact(self):
        safety = get_redistribution_safety(set())

        assert safety == {
            "affected_scopes": [],
            "affected_committee_ids": [],
            "committees_count": 0,
            "draft_count": 0,
            "final_grade_count": 0,
            "has_drafts": False,
            "has_final_grades": False,
        }

    def test_scope_lists_only_matching_committees(self, doctor):
        matching = create_committee(doctor)
        create_committee(
            doctor,
            template=create_template(
                doctor,
                department="artificial_intelligence",
                committee_type="technical",
            ),
        )

        safety = get_redistribution_safety({("software_engineering", "seasonal")})

        assert safety["affected_committee_ids"] == [matching.id]
        assert safety["committees_count"] == 1

    def test_draft_count_marks_confirmation_requirement(self, doctor, student):
        committee = create_committee(doctor)
        DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="StudentIdeaProposal",
            project_id=1,
            student=student,
            committee_type="seminar_1",
            doctor=doctor,
            score_main=8,
        )

        safety = get_redistribution_safety({("software_engineering", "seasonal")})

        assert safety["draft_count"] == 1
        assert safety["has_drafts"] is True
        assert safety["has_final_grades"] is False

    def test_final_grade_count_ignores_empty_grade_and_counts_scored_grade(
        self, doctor, student, user_factory
    ):
        committee = create_committee(doctor)
        second_student = user_factory(role="student", department="software_engineering")
        ProjectGrade.objects.create(
            project_source="StudentIdeaProposal",
            project_id=1,
            semester="Fall 2026",
            student=student,
            committee_type="seminar_1",
            committee=committee,
            entered_by=doctor,
        )
        ProjectGrade.objects.create(
            project_source="StudentIdeaProposal",
            project_id=1,
            semester="Fall 2026",
            student=second_student,
            committee_type="seminar_1",
            committee=committee,
            score_main=9,
            entered_by=doctor,
        )

        safety = get_redistribution_safety({("software_engineering", "seasonal")})

        assert safety["final_grade_count"] == 1
        assert safety["has_final_grades"] is True


class TestCommitteeSpawning:
    def test_multi_template_creates_one_committee_and_copies_fields(self, doctor):
        template = create_template(doctor, committee_type="technical")

        committee = spawn_committee_for_template(template)

        assert committee.template == template
        assert committee.sequence_number == 1
        assert committee.committee_type == "technical"
        assert committee.department == template.department
        assert committee.project_type == template.project_type
        assert committee.semester == template.semester
        assert committee.chair == doctor
        assert committee.status == "draft"

    def test_members_are_copied_to_spawned_committee(self, doctor, user_factory):
        member = user_factory(role="doctor", department="software_engineering")
        template = create_template(doctor)
        template.members.add(member)

        committee = spawn_committee_for_template(template)

        assert list(committee.members.values_list("pk", flat=True)) == [member.pk]

    def test_spawning_is_idempotent(self, doctor):
        template = create_template(doctor)

        first = spawn_committee_for_template(template)
        second = spawn_committee_for_template(template)

        assert first.pk == second.pk
        assert template.committees.count() == 1

    def test_single_mode_skips_immediate_spawning(self, doctor):
        template = create_template(doctor, scheduling_mode="single")

        assert spawn_committee_for_template(template) is None
        assert not template.committees.exists()

    def test_backward_compatible_wrapper_returns_list(self, doctor):
        multi = create_template(doctor)
        single = create_template(doctor, committee_type="seminar_2", scheduling_mode="single")

        assert len(spawn_committees_for_template(multi, count=99)) == 1
        assert spawn_committees_for_template(single) == []


class TestProjectCollection:
    def test_collects_assigned_proposal_and_registered_application(
        self, doctor, student, user_factory
    ):
        second_student = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor)
        application = create_idea_application(second_student, doctor)
        template = create_template(doctor)

        projects = collect_projects_for_template(template)

        assert {(item.source, item.id) for item in projects} == {
            ("StudentIdeaProposal", proposal.id),
            ("IdeaApplication", application.id),
        }

    def test_filters_department_project_type_and_status(
        self, doctor, student, user_factory
    ):
        create_proposal(student, doctor, status="pending_hod")
        other_student = user_factory(role="student", department="artificial_intelligence")
        create_proposal(
            other_student,
            doctor,
            department="artificial_intelligence",
            project_type="graduation_1",
        )
        template = create_template(doctor)

        assert collect_projects_for_template(template) == []

    @pytest.mark.parametrize("operational_status", ["fully_withdrawn", "fully_failed", "inactive"])
    def test_excludes_inactive_operational_projects(
        self, operational_status, doctor, student
    ):
        create_proposal(student, doctor, operational_status=operational_status)
        template = create_template(doctor)

        assert collect_projects_for_template(template) == []

    def test_legacy_invitations_supply_team_members(self, doctor, student, user_factory):
        member = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor, team_size=2)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=member,
            status="accepted",
        )

        project = collect_projects_for_template(create_template(doctor))[0]

        assert project.team_size == 2
        assert project.active_team_size == 2
        assert {entry["id"] for entry in project.active_students} == {student.id, member.id}

    def test_participations_override_legacy_invitations_and_split_inactive_students(
        self, doctor, student, user_factory
    ):
        active_member = user_factory(role="student", department="software_engineering")
        failed_member = user_factory(role="student", department="software_engineering")
        legacy_member = user_factory(role="student", department="software_engineering")
        proposal = create_proposal(student, doctor, team_size=3)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=legacy_member,
            status="accepted",
        )
        ProjectParticipation.objects.create(
            student=active_member,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="active",
        )
        ProjectParticipation.objects.create(
            student=failed_member,
            project_source="student_proposal",
            student_proposal=proposal,
            role="member",
            status="failed",
            status_reason="Failed requirement",
        )

        project = collect_projects_for_template(create_template(doctor))[0]

        assert [entry["id"] for entry in project.active_students] == [active_member.id]
        assert [entry["id"] for entry in project.inactive_students] == [failed_member.id]
        assert legacy_member.id not in {
            entry["id"] for entry in project.active_students + project.inactive_students
        }
        assert project.active_team_size == 1
        assert project.original_team_size == 2

    def test_project_with_only_inactive_participations_is_excluded(
        self, doctor, student
    ):
        proposal = create_proposal(student, doctor)
        ProjectParticipation.objects.create(
            student=student,
            project_source="student_proposal",
            student_proposal=proposal,
            role="leader",
            status="withdrawn",
        )

        assert collect_projects_for_template(create_template(doctor)) == []

    def test_application_legacy_team_invitation_is_collected(
        self, doctor, student, user_factory
    ):
        member = user_factory(role="student", department="software_engineering")
        application = create_idea_application(student, doctor, team_size=2)
        TeamInvitation.objects.create(
            application=application,
            invitee=member,
            status="accepted",
        )

        project = collect_projects_for_template(create_template(doctor))[0]

        assert project.source == "IdeaApplication"
        assert project.supervisor_id == doctor.id
        assert project.team_size == 2


class TestDistributionPlanning:
    def test_plan_contains_all_four_committee_types(self, doctor):
        template = create_template(doctor)
        projects = [collected(project_id=1)]

        plan = build_distribution_plan(template, projects=projects)

        assert [item.committee_type for item in plan.by_type] == ALL_COMMITTEE_TYPES
        assert all(item.undistributed for item in plan.by_type)
        assert plan.projects_count == 1

    def test_round_robin_distribution_is_balanced(self, doctor, monkeypatch):
        monkeypatch.setattr("committees.services.random.shuffle", lambda items: None)
        templates = [
            create_template(doctor, name="First"),
            create_template(doctor, name="Second"),
        ]
        committees = [create_committee(doctor, template=template) for template in templates]
        projects = [collected(project_id=index) for index in range(1, 6)]

        plan = build_distribution_plan(templates[0], projects=projects)
        seminar = next(item for item in plan.by_type if item.committee_type == "seminar_1")

        assert [row["committee_id"] for row in seminar.assignments] == [
            committees[0].id,
            committees[1].id,
            committees[0].id,
            committees[1].id,
            committees[0].id,
        ]

    def test_combo_plan_uses_no_template_id(self, doctor):
        create_committee(doctor)

        plan = build_distribution_plan_for_combo(
            "software_engineering", "seasonal", projects=[]
        )

        assert plan.template_id is None
        assert plan.department == "software_engineering"
        assert plan.project_type == "seasonal"

    def test_apply_plan_writes_both_sources_and_clears_old_assignments(
        self, doctor, student, user_factory
    ):
        committee = create_committee(doctor)
        old = create_proposal(student, doctor)
        new_student = user_factory(role="student", department="software_engineering")
        new_proposal = create_proposal(
            new_student,
            doctor,
            title="New Proposal",
            status="rejected",
        )
        application_student = user_factory(role="student", department="software_engineering")
        application = create_idea_application(application_student, doctor)
        committee.proposals.add(old)
        plan = DistributionPlan(
            template_id=committee.template_id,
            department="software_engineering",
            project_type="seasonal",
            semester="Fall 2026",
            projects_count=2,
            by_type=[
                TypeDistribution(
                    committee_type="seminar_1",
                    committees_count=1,
                    assignments=[
                        {
                            "committee_id": committee.id,
                            "sequence_number": 1,
                            "project": {"source": "StudentIdeaProposal", "id": new_proposal.id},
                        },
                        {
                            "committee_id": committee.id,
                            "sequence_number": 1,
                            "project": {"source": "IdeaApplication", "id": application.id},
                        },
                    ],
                )
            ],
        )

        written = apply_distribution_plan(plan)

        assert written == 2
        assert list(committee.proposals.values_list("pk", flat=True)) == [new_proposal.id]
        assert list(committee.applications.values_list("pk", flat=True)) == [application.id]
        assert old not in committee.proposals.all()

    def test_apply_plan_skips_assignment_to_missing_committee(self):
        plan = DistributionPlan(
            template_id=None,
            department="software_engineering",
            project_type="seasonal",
            semester=None,
            projects_count=1,
            by_type=[
                TypeDistribution(
                    committee_type="seminar_1",
                    committees_count=1,
                    assignments=[
                        {
                            "committee_id": 999999,
                            "sequence_number": 1,
                            "project": {"source": "StudentIdeaProposal", "id": 1},
                        }
                    ],
                )
            ],
        )

        assert apply_distribution_plan(plan) == 0


class TestFullDistribution:
    def create_four_templates(self, doctor):
        return [
            create_template(doctor, name=committee_type, committee_type=committee_type)
            for committee_type in ALL_COMMITTEE_TYPES
        ]

    def test_dry_run_does_not_delete_or_create_committees(self, doctor):
        templates = self.create_four_templates(doctor)
        existing = create_committee(doctor, template=templates[0])

        result = distribute_projects_to_committees(dry_run=True)

        assert Committee.objects.filter(pk=existing.pk).exists()
        assert result["dry_run"] is True
        assert "audit_id" not in result
        assert CommitteeDistributionAudit.objects.count() == 0

    def test_multi_distribution_rebuilds_scope_and_creates_audit(
        self, doctor, dean, student
    ):
        self.create_four_templates(doctor)
        proposal = create_proposal(student, doctor)

        result = distribute_projects_to_committees(actor=dean)

        assert result["processed_scopes"] == 1
        assert result["distributed_projects"] == 4
        assert Committee.objects.count() == 4
        assert all(
            committee.proposals.filter(pk=proposal.pk).exists()
            for committee in Committee.objects.all()
        )
        audit = CommitteeDistributionAudit.objects.get(pk=result["audit_id"])
        assert audit.actor == dean
        assert audit.committees_after == 4
        assert audit.result_summary["distributed_projects"] == 4

    def test_draft_data_requires_explicit_confirmation(self, doctor, student):
        template = create_template(doctor)
        committee = create_committee(doctor, template=template)
        DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="StudentIdeaProposal",
            project_id=1,
            student=student,
            committee_type="seminar_1",
            doctor=doctor,
            score_main=7,
        )

        with pytest.raises(RedistributionSafetyError) as exc_info:
            distribute_projects_to_committees()

        assert exc_info.value.code == "redistribution_confirmation_required"
        assert CommitteeDistributionAudit.objects.count() == 0

    def test_confirmed_draft_loss_executes_and_records_confirmation(
        self, doctor, student, dean
    ):
        template = create_template(doctor)
        committee = create_committee(doctor, template=template)
        DoctorGradeDraft.objects.create(
            committee=committee,
            project_source="StudentIdeaProposal",
            project_id=1,
            student=student,
            committee_type="seminar_1",
            doctor=doctor,
            score_main=7,
        )

        result = distribute_projects_to_committees(
            actor=dean,
            confirm_draft_loss=True,
        )

        audit = CommitteeDistributionAudit.objects.get(pk=result["audit_id"])
        assert audit.draft_count == 1
        assert audit.draft_loss_confirmed is True

    def test_final_grades_always_block_redistribution(self, doctor, student):
        template = create_template(doctor)
        committee = create_committee(doctor, template=template)
        ProjectGrade.objects.create(
            project_source="StudentIdeaProposal",
            project_id=1,
            semester="Fall 2026",
            student=student,
            committee_type="seminar_1",
            committee=committee,
            score_main=8,
            entered_by=doctor,
        )

        with pytest.raises(RedistributionSafetyError) as exc_info:
            distribute_projects_to_committees(confirm_draft_loss=True)

        assert exc_info.value.code == "redistribution_blocked_final_grades"


class TestTemplateCopying:
    def test_copy_creates_unapproved_template_and_copies_doctors(
        self, doctor, user_factory, dean
    ):
        member = user_factory(role="doctor", department="software_engineering")
        source = create_template(doctor, name="Original")
        source.members.add(member)

        copied = copy_template(source, created_by=dean)

        assert copied.pk != source.pk
        assert copied.name.startswith("Original")
        assert copied.name != source.name
        assert copied.is_approved is False
        assert copied.created_by == dean
        assert copied.chair == doctor
        assert list(copied.members.values_list("pk", flat=True)) == [member.pk]

    def test_copy_without_doctors_and_with_classification_overrides(self, doctor):
        source = create_template(doctor)

        copied = copy_template(
            source,
            copy_doctors=False,
            new_committee_type="technical",
            new_department="artificial_intelligence",
            new_project_type="graduation_1",
            new_semester="Spring 2027",
        )

        assert copied.committee_type == "technical"
        assert copied.department == "artificial_intelligence"
        assert copied.project_type == "graduation_1"
        assert copied.semester == "Spring 2027"
        assert copied.chair is None
        assert copied.members.count() == 0


class TestWarningsAndWorkload:
    def test_warnings_include_missing_chair_and_unscheduled(self, doctor):
        template = create_template(doctor, chair=None)
        committee = create_committee(doctor, template=template, chair=None)

        warnings = get_dashboard_warnings(semester="Fall 2026")
        codes = [warning["code"] for warning in warnings]

        assert "no_chair" in codes
        assert "unscheduled" in codes
        assert any(warning["related_id"] == committee.id for warning in warnings)

    def test_active_project_warns_for_each_missing_committee_type(self, doctor, student):
        create_proposal(student, doctor)

        warnings = get_dashboard_warnings()
        missing = [warning for warning in warnings if warning["code"] == "missing_committee_type"]

        assert len(missing) == 4

    def test_existing_type_removes_one_missing_type_warning(self, doctor, student):
        create_proposal(student, doctor)
        create_committee(doctor)

        warnings = get_dashboard_warnings()
        missing = [warning for warning in warnings if warning["code"] == "missing_committee_type"]

        assert len(missing) == 3

    def test_workload_counts_chair_and_members_and_assigns_levels(
        self, doctor, user_factory
    ):
        member = user_factory(role="doctor", department="software_engineering")
        for index in range(3):
            template = create_template(
                doctor,
                name=f"T{index}",
                committee_type=ALL_COMMITTEE_TYPES[index],
            )
            committee = create_committee(doctor, template=template)
            if index < 2:
                committee.members.add(member)

        workload = {row["doctor_id"]: row for row in get_doctor_workload()}

        assert workload[doctor.id]["chaired_count"] == 3
        assert workload[doctor.id]["total_committees"] == 3
        assert workload[doctor.id]["workload_level"] == "med"
        assert workload[member.id]["member_count"] == 2
        assert workload[member.id]["workload_level"] == "low"

    def test_six_committees_generate_overload_warning(self, doctor):
        for index in range(6):
            template = create_template(
                doctor,
                name=f"Overload {index}",
                committee_type=ALL_COMMITTEE_TYPES[index % 4],
                semester=f"Semester {index}",
            )
            create_committee(doctor, template=template)

        warnings = get_dashboard_warnings()

        overload = [warning for warning in warnings if warning["code"] == "doctor_overload"]
        assert len(overload) == 1
        assert overload[0]["related_id"] == doctor.id

    def test_workload_semester_filter_excludes_other_semesters(self, doctor):
        fall_template = create_template(doctor, name="Fall")
        create_committee(doctor, template=fall_template)
        spring_template = create_template(
            doctor,
            name="Spring",
            committee_type="seminar_2",
            semester="Spring 2027",
        )
        create_committee(doctor, template=spring_template)

        fall = get_doctor_workload(semester="Fall 2026")

        assert len(fall) == 1
        assert fall[0]["total_committees"] == 1
