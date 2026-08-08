"""Opt-in write workload for Project Management tasks.

WARNING: this creates, updates and deletes tasks and leaves activity-log rows.
Use only on a disposable/staging database with dedicated load-test accounts.
It refuses to start unless ALLOW_WRITE_LOAD_TESTS=1.
"""

from __future__ import annotations

import os
import uuid

from locust import between, task
from locust.exception import StopUser

from common import AuthenticatedApiUser


def _writes_enabled() -> bool:
    return os.getenv("ALLOW_WRITE_LOAD_TESTS", "0").strip().lower() in {"1", "true", "yes"}


class TaskWriteMixin:
    board_id: int | None = None

    def _guard_writes(self) -> None:
        if not _writes_enabled():
            raise StopUser(
                "Write load tests are disabled. Set ALLOW_WRITE_LOAD_TESTS=1 only on a disposable/staging DB."
            )

    def _create_patch_delete_task(self) -> None:
        if not self.board_id:
            raise StopUser("No writable project board is available for this account.")

        marker = uuid.uuid4().hex[:10]
        payload = {
            "title": f"LOADTEST-{marker}",
            "description": "Temporary task created by the opt-in Locust write workload.",
            "status": "todo",
            "priority": "medium",
        }

        task_id = None
        with self.client.post(
            f"/api/project-management/board/{self.board_id}/tasks/",
            json=payload,
            name="POST create task [write-load]",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"create task returned HTTP {response.status_code}")
                return
            try:
                task_id = response.json().get("id")
            except ValueError:
                response.failure("create task returned non-JSON response")
                return
            if not task_id:
                response.failure("create task response did not contain id")
                return
            response.success()

        try:
            with self.client.patch(
                f"/api/project-management/board/{self.board_id}/tasks/{task_id}/",
                json={"status": "in_progress", "priority": "high"},
                name="PATCH update task [write-load]",
                catch_response=True,
            ) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"update task returned HTTP {response.status_code}")
        finally:
            with self.client.delete(
                f"/api/project-management/board/{self.board_id}/tasks/{task_id}/delete/",
                name="DELETE task cleanup [write-load]",
                catch_response=True,
            ) as response:
                if response.status_code == 204:
                    response.success()
                else:
                    response.failure(f"cleanup returned HTTP {response.status_code}")

    @task
    def create_update_delete_task(self):
        self._create_patch_delete_task()


class StudentWriteUser(TaskWriteMixin, AuthenticatedApiUser):
    role = "student"
    weight = 70
    wait_time = between(2.0, 5.0)

    def on_start(self) -> None:
        self._guard_writes()
        super().on_start()
        payload = self.get_json(
            "/api/project-management/board/",
            name="GET discover writable board [student]",
        )
        if not isinstance(payload, dict) or not payload.get("has_project"):
            raise StopUser("Student load account has no active project board.")
        self.board_id = (payload.get("board") or {}).get("id")
        if not self.board_id:
            raise StopUser("Student project board response did not include an id.")


class DoctorWriteUser(TaskWriteMixin, AuthenticatedApiUser):
    role = "doctor"
    weight = 30
    wait_time = between(2.0, 5.0)

    def on_start(self) -> None:
        self._guard_writes()
        super().on_start()
        boards = self.get_json(
            "/api/project-management/supervisor/boards/",
            name="GET discover writable board [doctor]",
        )
        if not isinstance(boards, list) or not boards:
            raise StopUser("Doctor load account supervises no writable project board.")
        self.board_id = boards[0].get("id")
        if not self.board_id:
            raise StopUser("Supervisor board response did not include an id.")
