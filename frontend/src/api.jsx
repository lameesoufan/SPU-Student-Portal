import axios from 'axios';

const api = axios.create({
  baseURL: '',
  withCredentials: true,
});

// Interceptor لإضافة Token وتحديثه تلقائياً
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        await api.post('/api/token/refresh/');
        return api(originalRequest);
      } catch (refreshError) {
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// Auth
export const login = (credentials) => api.post('/api/token/', credentials);
export const studentLoginRequest = (universityId) => api.post('/api/auth/student-login-request/', { university_id: universityId });
export const studentLoginVerify = (universityId, otp) => api.post('/api/auth/student-login-verify/', { university_id: universityId, otp });
export const logout = () => api.post('/api/logout/');
export const getCurrentUser = () => api.get('/api/auth/me/');
export const registerStudent = (data) => api.post('/api/register/', data);

// Users & HOD
export const importUsers = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/import-users/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const assignHod = (department, userId) => api.post('/api/assign-hod/', { department, user_id: userId });
export const getStudentsReference = () => api.get('/api/students-reference/');
export const uploadReferenceDb = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/upload-students-reference/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

// Projects & Ideas
export const getProjectIdeas = (params) => api.get('/api/projects/ideas/', { params });
export const createProjectIdea = (data) => api.post('/api/projects/ideas/', data);
export const reviewProjectIdea = (id, data) => api.patch(`/api/projects/ideas/${id}/review/`, data);
export const getStudentProposals = (params) => api.get('/api/projects/proposals/', { params });
export const createStudentProposal = (data) => api.post('/api/projects/proposals/', data);
export const reviewProposal = (id, data) => api.patch(`/api/projects/proposals/${id}/review/`, data);
export const getIdeaApplications = (params) => api.get('/api/projects/applications/', { params });
export const applyForIdea = (data) => api.post('/api/projects/applications/', data);
export const reviewApplication = (id, data) => api.patch(`/api/projects/applications/${id}/review/`, data);
export const getMyProjects = () => api.get('/api/projects/my-projects/');
export const getProjectDetail = (id) => api.get(`/api/projects/${id}/`);
export const inviteMembers = (data) => api.post('/api/projects/invitations/', data);
export const respondToInvitation = (invitationId, action) => api.patch(`/api/projects/invitations/${invitationId}/respond/`, { action });
export const getMyInvitations = () => api.get('/api/projects/my-invitations/');
export const updateParticipationStatus = (projectId, studentId, status) => 
  api.patch(`/api/projects/participations/status-management/`, { project_id: projectId, student_id: studentId, status });

// Dynamic Forms
export const getDynamicForms = (context) => api.get('/api/dy-forms/', { params: { context } });
export const createDynamicForm = (data) => api.post('/api/dy-forms/', data);
export const updateDynamicForm = (id, data) => api.patch(`/api/dy-forms/${id}/`, data);
export const submitFormResponse = (formId, responses) => api.post('/api/dy-forms/responses/', { form_id: formId, responses });
export const getFormResponses = (formId) => api.get(`/api/dy-forms/responses/?form_id=${formId}`);

// Workflow
export const getWorkflowTemplates = () => api.get('/api/workflow/templates/');
export const createWorkflowTemplate = (data) => api.post('/api/workflow/templates/', data);
export const getProjectWorkflow = (projectId) => api.get(`/api/workflow/project-workflow/${projectId}/`);
export const fetchProjectWorkflow = (projectId) => api.get(`/api/workflow/project-workflow/${projectId}/`);
export const submitWorkflowStage = (stageInstanceId, data) => {
  const formData = new FormData();
  Object.keys(data).forEach(key => {
    if (data[key] instanceof File) {
      formData.append(key, data[key]);
    } else if (Array.isArray(data[key]) && data[key][0] instanceof File) {
      data[key].forEach(file => formData.append(key, file));
    } else {
      formData.append(key, data[key]);
    }
  });
  return api.patch(`/api/workflow/stage-instances/${stageInstanceId}/submit/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const reviewWorkflowStage = (stageInstanceId, data) => api.patch(`/api/workflow/stage-instances/${stageInstanceId}/review/`, data);
export const getReviewableProjects = () => api.get('/api/workflow/reviewable-projects/');
export const fetchReviewableProjects = () => api.get('/api/workflow/reviewable-projects/');

// Kanban
export const getKanbanBoard = (projectId) => api.get(`/api/project-management/kanban/${projectId}/`);
export const createTask = (data) => api.post('/api/project-management/tasks/', data);
export const updateTask = (id, data) => api.patch(`/api/project-management/tasks/${id}/`, data);
export const deleteTask = (id) => api.delete(`/api/project-management/tasks/${id}/`);
export const moveTask = (taskId, status) => api.patch(`/api/project-management/tasks/${taskId}/move/`, { status });
export const addComment = (taskId, content) => api.post('/api/project-management/comments/', { task_id: taskId, content });
export const getTaskComments = (taskId) => api.get(`/api/project-management/comments/?task_id=${taskId}`);

// Committees
export const getCommitteeTemplates = () => api.get('/api/committees/templates/');
export const createCommitteeTemplate = (data) => api.post('/api/committees/templates/', data);
export const getCommittees = (params) => api.get('/api/committees/', { params });
export const spawnCommittees = (templateId) => api.post(`/api/committees/templates/${templateId}/spawn/`);
export const distributeProjects = (committeeType) => api.post('/api/committees/distribute-projects/', { committee_type: committeeType });
export const getSchedulingPreview = (committeeType) => api.get('/api/committees/scheduling-preview/', { params: { committee_type: committeeType } });
export const applyScheduling = (runId) => api.post(`/api/committees/scheduling-runs/${runId}/apply/`);
export const rejectScheduling = (runId) => api.post(`/api/committees/scheduling-runs/${runId}/reject/`);
export const getDoctorAvailability = () => api.get('/api/committees/doctor-availability/');
export const updateDoctorAvailability = (data) => api.post('/api/committees/doctor-availability/', data);
export const getRooms = () => api.get('/api/committees/rooms/');
export const createRoom = (data) => api.post('/api/committees/rooms/', data);

// Grades
export const uploadReport = (data) => {
  const formData = new FormData();
  formData.append('project_id', data.project_id);
  formData.append('report_file', data.report_file);
  return api.post('/api/grades/report/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const enterGrade = (data) => api.post('/api/grades/enter/', data);
export const enterBulkGrades = (data) => api.post('/api/grades/enter/bulk/', data);
export const getMyGrades = () => api.get('/api/grades/my-grades/');
export const getHodGradesSummary = (params) => api.get('/api/grades/hod-summary/', { params });
export const getGradesSummary = (params) => api.get('/api/grades/summary/', { params });
export const exportGrades = (semester, department, projectType, committeeType) =>
  api.get('/api/grades/export/', {
    params: { 
      ...(semester ? { semester } : {}),
      ...(department ? { department } : {}),
      ...(projectType ? { project_type: projectType } : {}),
      ...(committeeType ? { committee_type: committeeType } : {}),
    },
    responseType: 'blob',
  });
export const exportGradesWord = (semester, department, projectType, committeeType) =>
  api.get('/api/grades/export/word/', {
    params: { 
      ...(semester ? { semester } : {}),
      ...(department ? { department } : {}),
      ...(projectType ? { project_type: projectType } : {}),
      ...(committeeType ? { committee_type: committeeType } : {}),
    },
    responseType: 'blob',
  });
export const toggleGradingMode = (committeeType, enabled) => api.post('/api/grades/grading-mode/', { committee_type: committeeType, enabled });

// Notifications
export const getNotifications = () => api.get('/api/notifications/');
export const markNotificationAsRead = (id) => api.patch(`/api/notifications/${id}/read/`);
export const markAllNotificationsAsRead = () => api.patch('/api/notifications/read-all/');

// GitLab
export const linkGitLabProject = (data) => api.post('/api/gitlab/link/', data);
export const getGitLabWebhooks = (projectId) => api.get(`/api/gitlab/webhooks/${projectId}/`);

// Project Imports
export const previewImport = (file, importType) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('import_type', importType);
  return api.post('/api/project-imports/preview/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const confirmImport = (data) => api.post('/api/project-imports/confirm/', data);

export default api;
