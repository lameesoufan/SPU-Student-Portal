"""Cross-application security integration tests for the project lifecycle.

These tests focus on boundaries that span more than one Django app: project
participation state, board access, workflows, grades, dynamic forms, reports,
and GitLab integration.
"""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from dy_forms.models import FieldResponse, FormField, FormResponse
from gitlab_integration.models import GitLabProject
from grades.models import CommitteeGradingMode, DoctorGradeDraft, ProjectGrade
from project_management.models import ProjectBoard
from projects.models import ProjectParticipation

from tests.integration.test_api_lifecycle import (
    SEMESTER,
    client_for,
    gitlab_url,
    grade_payload,
    make_assigned_project,
    make_committee,
    make_form,
    make_pending_proposal,
    make_workflow_template,
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration, pytest.mark.security]


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def anonymous_request(api_client, method, url, data=None, format_name="json"):
    request = getattr(api_client, method)
    if data is None:
        return request(url)
    return request(url, data, format=format_name)


def apply_workflow(board, doctor):
    template, _, field = make_workflow_template(doctor)
    response = client_for(doctor).post(
        reverse("workflow:apply_workflow_to_project"),
        {"project_board_id": board.id, "template_id": template.id},
        format="json",
    )
    assert response.status_code == 201
    return field


def enable_collective(committee, hod):
    committee.members.add(hod)
    response = client_for(hod).post(
        reverse("grading-mode"),
        {"committee_id": committee.id, "collective": True},
        format="json",
    )
    assert response.status_code == 200
    return response


def draft_payload(proposal, student, committee, score):
    return {
        "committee_id": committee.id,
        "project_source": "StudentIdeaProposal",
        "project_id": proposal.id,
        "committee_type": committee.committee_type,
        "semester": committee.semester,
        "grades": [{"student_id": student.id, "score_main": score}],
    }


class TestCrossAppAnonymousBoundary:
    @pytest.mark.parametrize(
        ("method", "url_factory", "data"),
        [
            ("get", lambda: reverse("my_board"), None),
            ("get", lambda: reverse("workflow:get_pending_stages"), None),
            ("get", lambda: reverse("my-grades"), None),
            ("get", lambda: reverse("student_get_form", args=["software_engineering", "propose"]), None),
            ("post", lambda: reverse("submit_form_response"), {"form": 1, "proposal_id": 1, "field_responses": []}),
            ("get", lambda: gitlab_url("board-commits", 999999), None),
        ],
    )
    def test_sensitive_cross_app_routes_require_authentication(self, api_client, method, url_factory, data):
        response = anonymous_request(api_client, method, url_factory(), data)
        assert response.status_code in {401, 403}


class TestStudentIdorAcrossApps:
    def test_outsider_cannot_mutate_another_students_board(self, student, doctor, user_factory):
        _, _, board = make_assigned_project(student, doctor)
        outsider = user_factory(role="student", department=student.department)

        response = client_for(outsider).patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {"github_repo": "https://github.com/outsider/attempt"},
            format="json",
        )

        board.refresh_from_db()
        assert response.status_code == 404
        assert board.github_repo is None

    def test_outsider_cannot_read_another_students_workflow(self, student, doctor, user_factory):
        _, _, board = make_assigned_project(student, doctor)
        apply_workflow(board, doctor)
        outsider = user_factory(role="student", department=student.department)

        response = client_for(outsider).get(reverse("workflow:get_project_workflow", args=[board.id]))

        assert response.status_code == 403

    def test_outsider_cannot_read_another_students_grades(self, student, doctor, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        client_for(doctor).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")
        outsider = user_factory(role="student", department=student.department)

        response = client_for(outsider).get(reverse("project-grades", args=["StudentIdeaProposal", proposal.id]))

        assert response.status_code == 403

    def test_outsider_cannot_read_another_students_form_response(self, student, doctor, hod, user_factory, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        form, field = make_form(hod)
        created = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": [{"field": field.id, "value": "private"}]},
            format="json",
        )
        assert created.status_code == 201
        outsider = user_factory(role="student", department=student.department)

        response = client_for(outsider).get(reverse("response_by_proposal", args=[proposal.id]))

        assert response.status_code == 404

    def test_outsider_cannot_read_another_students_gitlab_board(self, student, doctor, user_factory):
        _, _, board = make_assigned_project(student, doctor)
        GitLabProject.objects.create(
            board=board,
            gitlab_project_id=8101,
            gitlab_project_path="students/private-idor",
            project_name="Private IDOR Repo",
            web_url="https://gitlab.example/students/private-idor",
        )
        outsider = user_factory(role="student", department=student.department)

        response = client_for(outsider).get(gitlab_url("board-commits", board.id))

        assert response.status_code == 403

    def test_outsider_cannot_download_another_students_form_file(self, student, doctor, hod, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        form, _ = make_form(hod)
        file_field = FormField.objects.create(
            form=form,
            label="Private attachment",
            field_type="file",
            required=False,
            options=[],
            order=5,
        )
        response_row = FormResponse.objects.create(form=form, student=student, proposal_id=proposal.id)
        answer = FieldResponse.objects.create(
            response=response_row,
            field=file_field,
            file=SimpleUploadedFile("private.txt", b"private", content_type="text/plain"),
        )
        outsider = user_factory(role="student", department=student.department)

        response = client_for(outsider).get(reverse("dynamic_form_file_download", args=[answer.id]))

        assert response.status_code == 404


class TestParticipationRevocationPropagation:
    def test_withdrawal_revokes_board_mutation(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Security revocation"},
            format="json",
        )

        response = student_client.patch(
            reverse("update_board", kwargs={"board_id": board.id}),
            {"github_repo": "https://github.com/student/blocked"},
            format="json",
        )

        assert response.status_code == 404

    def test_withdrawal_revokes_workflow_submission(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        field = apply_workflow(board, doctor)
        pending = student_client.get(reverse("workflow:get_pending_stages"))
        stage_id = pending.data[0]["id"]
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Security revocation"}, format="json",
        )

        response = student_client.post(
            reverse("workflow:submit_workflow_stage", args=[stage_id]),
            {"field_responses": {str(field.id): "blocked"}},
            format="json",
        )

        assert response.status_code == 403

    def test_withdrawal_hides_existing_grade(self, student, doctor, dean, student_client):
        proposal, participation, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        entered = client_for(doctor).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")
        assert entered.status_code == 201
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Security revocation"}, format="json",
        )

        response = student_client.get(reverse("my-grades"))

        assert response.status_code == 200
        assert response.data == {"projects": []}
        assert ProjectGrade.objects.filter(student=student, project_id=proposal.id).exists()

    def test_withdrawal_blocks_new_form_submission(self, student, doctor, hod, dean, student_client):
        proposal, participation, _ = make_assigned_project(student, doctor)
        form, field = make_form(hod)
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Security revocation"}, format="json",
        )

        response = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": [{"field": field.id, "value": "blocked"}]},
            format="json",
        )

        assert response.status_code == 403
        assert not FormResponse.objects.exists()

    def test_withdrawal_revokes_gitlab_board_access(self, student, doctor, dean, student_client):
        _, participation, board = make_assigned_project(student, doctor)
        GitLabProject.objects.create(
            board=board,
            gitlab_project_id=8102,
            gitlab_project_path="students/revoked",
            project_name="Revoked Repo",
            web_url="https://gitlab.example/students/revoked",
        )
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Security revocation"}, format="json",
        )

        response = student_client.get(gitlab_url("board-commits", board.id))

        assert response.status_code == 403

    def test_withdrawal_blocks_project_report_upload(self, student, doctor, dean, student_client):
        proposal, participation, _ = make_assigned_project(student, doctor)
        client_for(dean).post(
            reverse("mark_participation_withdrawn", args=[participation.id]),
            {"reason": "Security revocation"}, format="json",
        )

        response = student_client.post(
            reverse("report-upload"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.id,
                "semester": SEMESTER,
                "file": SimpleUploadedFile("report.pdf", b"%PDF-1.4 security", content_type="application/pdf"),
            },
            format="multipart",
        )

        assert response.status_code == 403

    def test_failed_participation_blocks_new_grade_and_student_board(self, student, doctor, dean, student_client):
        proposal, participation, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        changed = client_for(dean).post(
            reverse("mark_participation_failed", args=[participation.id]),
            {"reason": "Failed project"}, format="json",
        )
        assert changed.status_code == 200

        board_response = student_client.get(reverse("my_board"))
        grade_response = client_for(doctor).post(
            reverse("enter-grade"), grade_payload(proposal, student, committee), format="json"
        )

        assert board_response.data == {"has_project": False}
        assert grade_response.status_code == 400
        assert not ProjectGrade.objects.exists()


class TestDepartmentIsolationAcrossApps:
    def test_foreign_hod_cannot_review_proposal(self, student, doctor, user_factory):
        proposal = make_pending_proposal(student, doctor)
        foreign_hod = user_factory(role="hod", department="information_security")
        approved = client_for(doctor).post(
            reverse("supervisor_review", args=[proposal.id]), {"action": "approve"}, format="json"
        )
        assert approved.status_code == 200

        response = client_for(foreign_hod).post(
            reverse("hod_review", args=[proposal.id]), {"action": "approve"}, format="json"
        )

        assert response.status_code in {403, 404}

    def test_foreign_hod_board_list_excludes_other_department(self, student, doctor, user_factory):
        _, _, board = make_assigned_project(student, doctor)
        foreign_hod = user_factory(role="hod", department="information_security")

        response = client_for(foreign_hod).get(reverse("hod_boards"))

        assert response.status_code == 200
        assert all(row["id"] != board.id for row in response.data)

    def test_foreign_hod_cannot_read_form_response(self, student, doctor, hod, user_factory, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        form, field = make_form(hod)
        created = student_client.post(
            reverse("submit_form_response"),
            {"form": form.id, "proposal_id": proposal.id, "field_responses": [{"field": field.id, "value": "department private"}]},
            format="json",
        )
        assert created.status_code == 201
        foreign_hod = user_factory(role="hod", department="information_security")

        response = client_for(foreign_hod).get(reverse("response_by_proposal", args=[proposal.id]))

        assert response.status_code == 404

    def test_foreign_hod_cannot_change_grading_mode(self, student, doctor, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        foreign_hod = user_factory(role="hod", department="information_security")

        response = client_for(foreign_hod).post(
            reverse("grading-mode"),
            {"committee_id": committee.id, "collective": True},
            format="json",
        )

        assert response.status_code == 403
        assert not CommitteeGradingMode.objects.filter(committee=committee).exists()

    def test_foreign_hod_cannot_read_gitlab_board(self, student, doctor, user_factory):
        _, _, board = make_assigned_project(student, doctor)
        GitLabProject.objects.create(
            board=board,
            gitlab_project_id=8103,
            gitlab_project_path="students/department-private",
            project_name="Department Private Repo",
            web_url="https://gitlab.example/students/department-private",
        )
        foreign_hod = user_factory(role="hod", department="information_security")

        response = client_for(foreign_hod).get(gitlab_url("board-commits", board.id))

        assert response.status_code == 403


class TestGradingModeSecurityContract:
    def test_individual_mode_rejects_plain_doctor_member(self, student, doctor, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        member = user_factory(role="doctor", department=student.department)
        committee = make_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)

        response = client_for(member).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")

        assert response.status_code == 403
        assert not ProjectGrade.objects.exists()

    def test_individual_mode_rejects_hod_member(self, student, doctor, hod):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.members.add(hod)
        committee.proposals.add(proposal)

        response = client_for(hod).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")

        assert response.status_code == 403
        assert not ProjectGrade.objects.exists()

    def test_individual_mode_allows_chair(self, student, doctor):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)

        response = client_for(doctor).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")

        assert response.status_code == 201
        assert ProjectGrade.objects.get(student=student).score_main == 8

    def test_collective_mode_blocks_chair_direct_entry(self, student, doctor, hod):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)

        response = client_for(doctor).post(reverse("enter-grade"), grade_payload(proposal, student, committee), format="json")

        assert response.status_code == 409
        assert not ProjectGrade.objects.exists()

    def test_collective_mode_blocks_chair_bulk_entry(self, student, doctor, hod):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)

        response = client_for(doctor).post(
            reverse("enter-grade-bulk"),
            {
                "project_source": "StudentIdeaProposal",
                "project_id": proposal.id,
                "committee_type": committee.committee_type,
                "committee_id": committee.id,
                "semester": committee.semester,
                "grades": [{"student_id": student.id, "score_main": 8}],
            },
            format="json",
        )

        assert response.status_code == 409
        assert not ProjectGrade.objects.exists()

    def test_collective_mode_blocks_direct_entry_even_without_committee_id(self, student, doctor, hod):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)
        payload = grade_payload(proposal, student, committee)
        payload.pop("committee_id")

        response = client_for(doctor).post(reverse("enter-grade"), payload, format="json")

        assert response.status_code == 409
        assert not ProjectGrade.objects.exists()

    def test_collective_mode_allows_plain_doctor_member_draft(self, student, doctor, hod, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        member = user_factory(role="doctor", department=student.department)
        committee = make_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)

        response = client_for(member).post(
            reverse("grade-draft"), draft_payload(proposal, student, committee, 7), format="json"
        )

        assert response.status_code == 200
        assert DoctorGradeDraft.objects.filter(committee=committee, doctor=member, student=student).exists()

    def test_collective_mode_allows_hod_member_draft(self, student, doctor, hod):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)

        response = client_for(hod).post(
            reverse("grade-draft"), draft_payload(proposal, student, committee, 10), format="json"
        )

        assert response.status_code == 200
        assert DoctorGradeDraft.objects.filter(committee=committee, doctor=hod, student=student).exists()

    def test_collective_mode_rejects_non_member_draft(self, student, doctor, hod, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)
        outsider = user_factory(role="doctor", department=student.department)

        response = client_for(outsider).post(
            reverse("grade-draft"), draft_payload(proposal, student, committee, 10), format="json"
        )

        assert response.status_code == 403
        assert not DoctorGradeDraft.objects.filter(doctor=outsider).exists()

    def test_collective_grade_stays_pending_until_every_current_grader_submits(self, student, doctor, hod, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        member = user_factory(role="doctor", department=student.department)
        committee = make_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)

        first = client_for(doctor).post(reverse("grade-draft"), draft_payload(proposal, student, committee, 8), format="json")
        second = client_for(member).post(reverse("grade-draft"), draft_payload(proposal, student, committee, 10), format="json")

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.data["pending_students"] == [
            {"student_id": student.id, "submitted_count": 2, "required_count": 3}
        ]
        assert not ProjectGrade.objects.exists()

    def test_collective_grade_finalizes_integer_average_after_all_graders(self, student, doctor, hod, user_factory, student_client):
        proposal, _, _ = make_assigned_project(student, doctor)
        member = user_factory(role="doctor", department=student.department)
        committee = make_committee(doctor)
        committee.members.add(member)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)

        client_for(doctor).post(reverse("grade-draft"), draft_payload(proposal, student, committee, 7), format="json")
        client_for(member).post(reverse("grade-draft"), draft_payload(proposal, student, committee, 8), format="json")
        final = client_for(hod).post(reverse("grade-draft"), draft_payload(proposal, student, committee, 9), format="json")

        grade = ProjectGrade.objects.get(student=student, committee=committee)
        visible = student_client.get(reverse("my-grades"))
        assert final.status_code == 200
        assert final.data["finalized_students"] == [student.id]
        assert grade.score_main == 8
        assert isinstance(grade.score_main, int)
        assert visible.data["projects"][0]["total_score"] == 8

    def test_collective_draft_project_scope_cannot_cross_to_unassigned_project(self, student, doctor, hod, user_factory):
        proposal, _, _ = make_assigned_project(student, doctor)
        committee = make_committee(doctor)
        committee.proposals.add(proposal)
        enable_collective(committee, hod)
        other_student = user_factory(role="student", department=student.department)
        other_proposal, _, _ = make_assigned_project(other_student, doctor, title="Other project")

        response = client_for(hod).post(
            reverse("grade-draft"), draft_payload(other_proposal, other_student, committee, 9), format="json"
        )

        assert response.status_code == 400
        assert not DoctorGradeDraft.objects.filter(project_id=other_proposal.id).exists()
