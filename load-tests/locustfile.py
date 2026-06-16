import os

from locust import HttpUser, between, task


class PortalReadinessUser(HttpUser):
    wait_time = between(1, 4)

    def on_start(self):
        self.token = None
        username = os.getenv('LOCUST_USERNAME')
        password = os.getenv('LOCUST_PASSWORD')
        if username and password:
            response = self.client.post('/api/token/', json={'username': username, 'password': password}, name='POST /api/token/')
            if response.ok:
                self.token = response.json().get('access')

    @property
    def auth_headers(self):
        if not self.token:
            return {}
        return {'Authorization': f'Bearer {self.token}'}

    @task(8)
    def browse_project_ideas(self):
        self.client.get('/api/projects/ideas/browse/', headers=self.auth_headers, name='GET /api/projects/ideas/browse/')

    @task(5)
    def read_notifications_count(self):
        self.client.get('/api/notifications/unread-count/', headers=self.auth_headers, name='GET /api/notifications/unread-count/')

    @task(4)
    def load_my_project_board(self):
        self.client.get('/api/project-management/board/', headers=self.auth_headers, name='GET /api/project-management/board/')

    @task(3)
    def load_workflow_templates(self):
        self.client.get('/api/workflow/templates/', headers=self.auth_headers, name='GET /api/workflow/templates/')

    @task(2)
    def load_available_workflow_projects(self):
        self.client.get('/api/workflow/available-projects/', headers=self.auth_headers, name='GET /api/workflow/available-projects/')

    @task(1)
    def load_review_queue(self):
        self.client.get('/api/projects/proposals/pending-hod/', headers=self.auth_headers, name='GET /api/projects/proposals/pending-hod/')
