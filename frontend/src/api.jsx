import axios from 'axios';

const api = axios.create({
  baseURL: '',
  withCredentials: true,
});

// Interceptor لإضافة الـ CSRF token وحل مشاكل التوكن
api.interceptors.request.use((config) => {
  const csrftoken = document.cookie
    .split('; ')
    .find((row) => row.startsWith('csrftoken='))
    ?.split('=')[1];
  if (csrftoken) {
    config.headers['X-CSRFToken'] = csrftoken;
  }
  return config;
});

// Auth APIs
export const login = (username, password) =>
  api.post('/api/token/', { username, password });

export const studentLoginRequest = (university_id) =>
  api.post('/api/auth/student-login-request/', { university_id });

export const studentLoginVerify = (university_id, otp) =>
  api.post('/api/auth/student-login-verify/', { university_id, otp });

export const logout = () => api.post('/api/logout/');

export const getMe = () => api.get('/api/auth/me/');

export const registerStudent = (data) => api.post('/api/register/', data);

// User Management
export const importUsers = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/import-users/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const assignHod = (userId, department) =>
  api.post('/api/assign-hod/', { user_id: userId, department });

// Projects
export const getProjectIdeas = (params) =>
  api.get('/api/projects/ideas/', { params });

export const submitIdea = (data) => api.post('/api/projects/ideas/', data);

export const reviewIdea = (id, data) =>
  api.patch(`/api/projects/ideas/${id}/`, data);

export const getMyProposals = () => api.get('/api/projects/my-proposals/');

export const submitProposal = (data) =>
  api.post('/api/projects/proposals/', data);

export const getProposalInvitations = () =>
  api.get('/api/projects/proposal-invitations/');

export const respondToInvitation = (id, status) =>
  api.patch(`/api/projects/proposal-invitations/${id}/`, { status });

export const getTeamInvitations = () =>
  api.get('/api/projects/team-invitations/');

export const respondToTeamInvitation = (id, status) =>
  api.patch(`/api/projects/team-invitations/${id}/`, { status });

export const getMyProject = () => api.get('/api/projects/my-project/');

export const getProjectDetails = (id) =>
  api.get(`/api/projects/my-project/${id}/`);

export const updateProjectStatus = (id, status) =>
  api.patch(`/api/projects/my-project/${id}/`, { status });

export const getApplications = (params) =>
  api.get('/api/projects/applications/', { params });

export const submitApplication = (data) =>
  api.post('/api/projects/applications/', data);

export const reviewApplication = (id, data) =>
  api.patch(`/api/projects/applications/${id}/`, data);

export const getDoctorProjects = () => api.get('/api/projects/doctor-projects/');

export const getSupervisorProjects = () =>
  api.get('/api/projects/supervisor-projects/');

// Project Management (Kanban)
export const getKanbanBoard = (projectId) =>
  api.get(`/api/project-management/boards/${projectId}/`);

export const createTask = (projectId, data) =>
  api.post(`/api/project-management/boards/${projectId}/tasks/`, data);

export const updateTask = (projectId, taskId, data) =>
  api.patch(
    `/api/project-management/boards/${projectId}/tasks/${taskId}/`,
    data
  );

export const deleteTask = (projectId, taskId) =>
  api.delete(`/api/project-management/boards/${projectId}/tasks/${taskId}/`);

export const addTaskComment = (projectId, taskId, data) =>
  api.post(
    `/api/project-management/boards/${projectId}/tasks/${taskId}/comments/`,
    data
  );

export const uploadTaskAttachment = (projectId, taskId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(
    `/api/project-management/boards/${projectId}/tasks/${taskId}/attachments/`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
};

// Dynamic Forms
export const getDynamicForms = (context) =>
  api.get('/api/dy-forms/forms/', { params: { context } });

export const createDynamicForm = (data) =>
  api.post('/api/dy-forms/forms/', data);

export const updateDynamicForm = (id, data) =>
  api.patch(`/api/dy-forms/forms/${id}/`, data);

export const deleteDynamicForm = (id) =>
  api.delete(`/api/dy-forms/forms/${id}/`);

export const submitFormResponse = (formId, data) =>
  api.post(`/api/dy-forms/forms/${formId}/responses/`, data);

export const getFormResponses = (formId) =>
  api.get(`/api/dy-forms/forms/${formId}/responses/`);

// Workflow
export const getWorkflowTemplates = () =>
  api.get('/api/workflow/templates/');

export const createWorkflowTemplate = (data) =>
  api.post('/api/workflow/templates/', data);

export const updateWorkflowTemplate = (id, data) =>
  api.patch(`/api/workflow/templates/${id}/`, data);

export const deleteWorkflowTemplate = (id) =>
  api.delete(`/api/workflow/templates/${id}/`);

export const getProjectWorkflow = (projectId) =>
  api.get(`/api/workflow/projects/${projectId}/workflow/`);

export const fetchProjectWorkflow = async (projectId) => {
  const response = await api.get(`/api/workflow/projects/${projectId}/workflow/`);
  return response.data;
};

export const getReviewableProjects = async () => {
  const response = await api.get('/api/workflow/reviewable-projects/');
  return response.data;
};

export const reviewWorkflowStage = async (stageInstanceId, data) => {
  // Handle file uploads if present
  if (data.files && data.files.length > 0) {
    const formData = new FormData();
    formData.append('status', data.status || 'approved');
    if (data.comments) {
      formData.append('comments', data.comments);
    }
    data.files.forEach((file) => {
      formData.append('files', file);
    });
    
    const response = await api.post(
      `/api/workflow/stage-instances/${stageInstanceId}/review/`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  } else {
    const response = await api.post(
      `/api/workflow/stage-instances/${stageInstanceId}/review/`,
      {
        status: data.status || 'approved',
        comments: data.comments || '',
      }
    );
    return response.data;
  }
};

export const submitWorkflowStage = (projectId, stageId, data) =>
  api.post(`/api/workflow/projects/${projectId}/stages/${stageId}/submit/`, data);

// Notifications
export const getNotifications = () => api.get('/api/notifications/');

export const markNotificationAsRead = (id) =>
  api.patch(`/api/notifications/${id}/`, { is_read: true });

export const markAllNotificationsAsRead = () =>
  api.post('/api/notifications/mark-all-read/');

// Committees
export const getCommitteeTemplates = () =>
  api.get('/api/committees/templates/');

export const createCommitteeTemplate = (data) =>
  api.post('/api/committees/templates/', data);

export const getCommittees = (params) =>
  api.get('/api/committees/', { params });

export const createCommittee = (data) =>
  api.post('/api/committees/', data);

export const distributeProjects = (templateId) =>
  api.post(`/api/committees/templates/${templateId}/distribute/`);

export const runScheduling = (templateId, preview = false) =>
  api.post(`/api/committees/templates/${templateId}/schedule/`, { preview });

export const applyScheduling = (runId) =>
  api.post(`/api/committees/scheduling-runs/${runId}/apply/`);

export const rejectScheduling = (runId) =>
  api.post(`/api/committees/scheduling-runs/${runId}/reject/`);

export const getRooms = () => api.get('/api/committees/rooms/');

export const createRoom = (data) => api.post('/api/committees/rooms/', data);

export const getDoctorAvailability = (doctorId, params) =>
  api.get(`/api/committees/doctors/${doctorId}/availability/`, { params });

export const setDoctorAvailability = (doctorId, data) =>
  api.post(`/api/committees/doctors/${doctorId}/availability/`, data);

export const getDoctorExceptions = (doctorId, params) =>
  api.get(`/api/committees/doctors/${doctorId}/exceptions/`, { params });

export const setDoctorException = (doctorId, data) =>
  api.post(`/api/committees/doctors/${doctorId}/exceptions/`, data);

// Grades
export const uploadReport = (data) => {
  const formData = new FormData();
  formData.append('report', data.report);
  if (data.project_application)
    formData.append('project_application', data.project_application);
  if (data.student_proposal)
    formData.append('student_proposal', data.student_proposal);
  return api.post('/api/grades/report/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const enterGrade = (data) => api.post('/api/grades/enter/', data);

export const bulkEnterGrades = (data) =>
  api.post('/api/grades/enter/bulk/', data);

export const getMyGrades = () => api.get('/api/grades/my-grades/');

export const getHodGradesSummary = (params) =>
  api.get('/api/grades/hod-summary/', { params });

export const getDeanGradesSummary = (params) =>
  api.get('/api/grades/dean-summary/', { params });

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

export const getGradingMode = (committeeId) =>
  api.get(`/api/grades/committees/${committeeId}/mode/`);

export const setGradingMode = (committeeId, mode) =>
  api.post(`/api/grades/committees/${committeeId}/mode/`, { mode });

export const submitDoctorGradeDraft = (data) =>
  api.post('/api/grades/doctor-draft/', data);

// Project Imports
export const previewImport = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/project-imports/preview/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const confirmImport = (data) =>
  api.post('/api/project-imports/confirm/', data);

// GitLab Integration
export const linkGitLabProject = (projectId, gitLabData) =>
  api.post(`/api/gitlab/projects/${projectId}/link/`, gitLabData);

export const unlinkGitLabProject = (projectId) =>
  api.delete(`/api/gitlab/projects/${projectId}/unlink/`);

export const getGitLabWebhooks = (projectId) =>
  api.get(`/api/gitlab/projects/${projectId}/webhooks/`);

// Student Status Management
export const getStudentParticipations = (params) =>
  api.get('/api/projects/participations/status-management/', { params });

export const updateStudentStatus = (participationId, status, reason) =>
  api.patch(`/api/projects/participations/${participationId}/status/`, {
    status,
    reason,
  });

export default api;
