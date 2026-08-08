"""Role-based read-heavy workload for the current University Project Management API.

This is the default load suite. It does not intentionally modify application
business data. Student virtual users receive distinct prepared identities, then each role follows
endpoints used by its real dashboard/workflow.
"""

from __future__ import annotations

import random

from locust import between, task

from common import AuthenticatedApiUser


class CommonReadMixin:
    @task(2)
    def unread_notifications(self):
        self.get_json(
            "/api/notifications/unread-count/",
            name="GET /api/notifications/unread-count/",
        )

    @task(1)
    def notifications(self):
        self.get_json("/api/notifications/", name="GET /api/notifications/")

    @task(1)
    def current_user(self):
        self.get_json("/api/auth/me/", name="GET /api/auth/me/")


class StudentReadUser(CommonReadMixin, AuthenticatedApiUser):
    role = "student"
    weight = 55
    wait_time = between(0.8, 2.5)

    @task(5)
    def browse_ideas(self):
        self.get_json("/api/projects/ideas/browse/", name="GET student browse ideas")

    @task(4)
    def project_board(self):
        payload = self.get_json(
            "/api/project-management/board/",
            name="GET student project board",
        )
        if not isinstance(payload, dict) or not payload.get("has_project"):
            return

        board = payload.get("board") or {}
        board_id = board.get("id")
        if not board_id:
            return

        if random.random() < 0.55:
            self.get_json(
                f"/api/project-management/board/{board_id}/activity/",
                name="GET board activity [student]",
            )
        if random.random() < 0.45:
            self.get_json(
                f"/api/workflow/project/{board_id}/",
                name="GET project workflow [student]",
            )

    @task(3)
    def my_grades(self):
        self.get_json("/api/grades/my-grades/", name="GET student my grades")

    @task(2)
    def pending_workflow(self):
        self.get_json("/api/workflow/pending/", name="GET workflow pending [student]")

    @task(1)
    def team_invitations(self):
        self.get_json("/api/projects/invitations/mine/", name="GET team invitations [student]")

    @task(1)
    def proposal_invitations(self):
        self.get_json(
            "/api/projects/proposal-invitations/mine/",
            name="GET proposal invitations [student]",
        )


class DoctorReadUser(CommonReadMixin, AuthenticatedApiUser):
    role = "doctor"
    weight = 25
    wait_time = between(1.0, 3.0)

    @task(4)
    def pending_supervisor_proposals(self):
        self.get_json(
            "/api/projects/proposals/pending-supervisor/",
            name="GET pending supervisor proposals [doctor]",
        )

    @task(4)
    def pending_applications(self):
        self.get_json(
            "/api/projects/applications/pending-doctor/",
            name="GET pending applications [doctor]",
        )

    @task(4)
    def supervised_boards(self):
        boards = self.get_json(
            "/api/project-management/supervisor/boards/",
            name="GET supervisor boards [doctor]",
        )
        if not isinstance(boards, list) or not boards:
            return
        board_id = random.choice(boards).get("id")
        if board_id and random.random() < 0.5:
            self.get_json(
                f"/api/project-management/board/{board_id}/activity/",
                name="GET board activity [doctor]",
            )

    @task(3)
    def committee_schedule(self):
        self.get_json("/api/committees/my-schedule/", name="GET committee schedule [doctor]")

    @task(2)
    def committee_grades(self):
        self.get_json(
            "/api/grades/my-committee-grades/",
            name="GET committee grades [doctor]",
        )

    @task(2)
    def my_ideas(self):
        self.get_json("/api/projects/ideas/", name="GET doctor ideas")


class HodReadUser(CommonReadMixin, AuthenticatedApiUser):
    role = "hod"
    weight = 12
    wait_time = between(1.0, 3.0)

    @task(4)
    def pending_student_proposals(self):
        self.get_json(
            "/api/projects/proposals/pending-hod/",
            name="GET pending proposals [hod]",
        )

    @task(3)
    def pending_doctor_ideas(self):
        self.get_json(
            "/api/projects/ideas/pending-hod/",
            name="GET pending doctor ideas [hod]",
        )

    @task(3)
    def pending_applications(self):
        self.get_json(
            "/api/projects/applications/pending-hod/",
            name="GET pending applications [hod]",
        )

    @task(4)
    def department_boards(self):
        self.get_json(
            "/api/project-management/hod/boards/",
            name="GET department boards [hod]",
        )

    @task(3)
    def department_stats(self):
        self.get_json(
            "/api/project-management/hod/stats/",
            name="GET department stats [hod]",
        )

    @task(3)
    def grades_summary(self):
        self.get_json("/api/grades/hod-summary/", name="GET grades summary [hod]")



class DeanReadUser(CommonReadMixin, AuthenticatedApiUser):
    role = "dean"
    weight = 8
    wait_time = between(1.0, 3.5)

    @task(5)
    def committees_dashboard(self):
        self.get_json("/api/committees/dashboard/", name="GET committees dashboard [dean]")

    @task(4)
    def participation_stats(self):
        self.get_json(
            "/api/projects/participations/status-management/stats/",
            name="GET participation stats [dean]",
        )

    @task(4)
    def grades_summary(self):
        self.get_json("/api/grades/summary/", name="GET grades summary [dean]")

    @task(3)
    def scheduling_runs(self):
        self.get_json(
            "/api/committees/schedule/runs/",
            name="GET scheduling runs [dean]",
        )

    @task(2)
    def departments(self):
        self.get_json("/api/departments/", name="GET departments [dean]")
