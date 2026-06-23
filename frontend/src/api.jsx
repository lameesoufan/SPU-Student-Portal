import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,  // ← مهم: يبعث الـ cookies مع كل request
});
let refreshPromise = null;

// No need for request interceptor — cookies are sent automatically!
// But keep a fallback for any edge cases
api.interceptors.request.use((config) => {
  // مع HttpOnly cookies، ما نحتاج نحط Authorization header يدوي
  // الـ JWTCookieMiddleware بالـ backend بيقري الـ cookie وبيحط الـ header
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const isTokenRequest = original?.url?.includes('/api/token/');

    if (status !== 401 || !original || original._retry || isTokenRequest) {
      return Promise.reject(error);
    }

    original._retry = true;
    try {
      if (!refreshPromise) {
        refreshPromise = axios.post(`${API_BASE}/api/token/refresh/`, {}, {
          withCredentials: true,  // ← يبعث الـ refresh cookie
        }).finally(() => { refreshPromise = null; });
      }
      await refreshPromise;
      // الـ backend بيضبط الـ cookies الجديدة تلقائياً
      return api(original);
    } catch (refreshError) {
      // Refresh فشل — الـ cookies انحذفت أو انتهت
      return Promise.reject(refreshError);
    }
  }
);

export const login = (username, password) =>
  api.post('/api/token/', { username, password });

export const importUsers = (file, role) => {
  const form = new FormData();
  form.append('file', file);
  form.append('role', role);
  return api.post('/api/import-users/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const importProjects = (file, { dry_run = true, preview_result_id = null } = {}) => {
  const form = new FormData();
  form.append('file', file);
  if (preview_result_id) form.append('preview_result_id', preview_result_id);
  return api.post(`/api/import/projects/?dry_run=${dry_run ? 'true' : 'false'}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const downloadProjectImportTemplate = () =>
  api.get('/api/import/template/', { responseType: 'blob' });

export const fetchProjectImportHistory = (params = {}) =>
  api.get('/api/import/history/', { params });

export const fetchProjectImportRows = (sessionId) =>
  api.get(`/api/import/history/${sessionId}/rows/`);

export const logoutUser = () =>
  api.post('/api/logout/');

export const changePassword = (new_password, confirm_password) =>
  api.post('/api/change-password/', { new_password, confirm_password });

export const fetchDoctors = () => api.get('/api/doctors/');
export const fetchDepartments = () => api.get('/api/departments/');
export const assignHod = (doctor_id, department) =>
  api.post('/api/assign-hod/', { doctor_id, department });

export const uploadReferenceDb = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/api/upload-reference/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const studentSelfRegister = (university_id, password) =>
  api.post('/api/register/', { university_id, password });

// ── Projects: Doctor (UC-01) ──────────────────────────────────────────────────
export const submitProjectIdea = (data) =>
  api.post('/api/projects/ideas/submit/', data);

export const fetchMyIdeas = () =>
  api.get('/api/projects/ideas/');

// ── Projects: Student (UC-02) ─────────────────────────────────────────────────
export const submitStudentProposal = (data) =>
  api.post('/api/projects/proposals/submit/', data);

export const fetchMyProposal = () =>
  api.get('/api/projects/proposals/mine/');

export const cancelProposal = (proposalId) =>
  api.post(`/api/projects/proposals/${proposalId}/cancel/`);

// ── Projects: UC-03 Browse & Apply ───────────────────────────────────────────
export const browseIdeas = () =>
  api.get('/api/projects/ideas/browse/');

export const applyOnIdea = (ideaId, data) =>
  api.post(`/api/projects/ideas/${ideaId}/apply/`, data);

export const fetchMyIdeaApplication = () =>
  api.get('/api/projects/applications/mine/');

// ── Projects: Doctor reviews applications ─────────────────────────────────────
export const fetchDoctorPendingApplications = () =>
  api.get('/api/projects/applications/pending-doctor/');

export const doctorReviewApplication = (appId, data) =>
  api.post(`/api/projects/applications/${appId}/doctor-review/`, data);

// ── Projects: Supervisor review ───────────────────────────────────────────────
export const fetchSupervisorPending = () =>
  api.get('/api/projects/proposals/pending-supervisor/');

export const supervisorReview = (proposalId, data) =>
  api.post(`/api/projects/proposals/${proposalId}/supervisor-review/`, data);

// ── Projects: HoD review ──────────────────────────────────────────────────────
export const fetchHodPending = () =>
  api.get('/api/projects/proposals/pending-hod/');

export const hodReview = (proposalId, data) =>
  api.post(`/api/projects/proposals/${proposalId}/hod-review/`, data);

export const fetchHodPendingDoctorIdeas = () =>
  api.get('/api/projects/ideas/pending-hod/');

export const hodReviewDoctorIdea = (ideaId, data) =>
  api.post(`/api/projects/ideas/${ideaId}/hod-review/`, data);

export const fetchHodPendingApplications = () =>
  api.get('/api/projects/applications/pending-hod/');

export const hodReviewApplication = (appId, data) =>
  api.post(`/api/projects/applications/${appId}/hod-review/`, data);

// ── Team invitations ──────────────────────────────────────────────────────────
export const fetchMyInvitations = () =>
  api.get('/api/projects/invitations/mine/');

export const respondToInvitation = (invId, action) =>
  api.post(`/api/projects/invitations/${invId}/respond/`, { action });

// ── Proposal invitations (student proposals) ──────────────────────────────────
export const fetchMyProposalInvitations = () =>
  api.get('/api/projects/proposal-invitations/mine/');

export const respondToProposalInvitation = (invId, action) =>
  api.post(`/api/projects/proposal-invitations/${invId}/respond/`, { action });

export const replaceProposalMember = (proposalId, old_member_id, new_member_id) =>
  api.post(`/api/projects/proposals/${proposalId}/replace-member/`, { old_member_id, new_member_id });

export const replaceApplicationMember = (appId, old_member_id, new_member_id) =>
  api.post(`/api/projects/applications/${appId}/replace-member/`, { old_member_id, new_member_id });

// ── Doctors list (for supervisor dropdown) ────────────────────────────────────
export const fetchDoctorsList = () =>
  api.get('/api/projects/doctors/');

export const searchStudents = (q) =>
  api.get('/api/projects/students/', { params: { q } });

export default api;

// ── Notifications ─────────────────────────────────────────────────────────────
export const fetchNotifications = () =>
  api.get('/api/notifications/');

export const fetchUnreadCount = () =>
  api.get('/api/notifications/unread-count/');

export const markNotifRead = (id) =>
  api.post(`/api/notifications/${id}/read/`);

export const markAllNotifsRead = () =>
  api.post('/api/notifications/mark-all-read/');

// ── Dynamic Forms ─────────────────────────────────────────────────────────────
export const fetchHodForm = (context) =>
  api.get(`/api/dy-forms/hod/${context}/`);

export const saveHodForm = (context, data) =>
  api.post(`/api/dy-forms/hod/${context}/save/`, data);

export const fetchStudentForm = (department, context) =>
  api.get(`/api/dy-forms/${department}/${context}/`);

export const submitFormResponse = (data) =>
  api.post('/api/dy-forms/responses/submit/', data);

export const fetchHodFormResponses = (context) =>
  api.get(`/api/dy-forms/hod/${context}/responses/`);

export const fetchResponseByProposal = (proposalId) =>
  api.get(`/api/dy-forms/responses/proposal/${proposalId}/`);

export const fetchResponseByApplication = (applicationId) =>
  api.get(`/api/dy-forms/responses/application/${applicationId}/`);

// ── Project Management (Kanban Board) ─────────────────────────────────────────
export const fetchMyBoard = () =>
  api.get('/api/project-management/board/');

export const updateBoard = (boardId, data) =>
  api.patch(`/api/project-management/board/${boardId}/update/`, data);

export const fetchSupervisorBoards = () =>
  api.get('/api/project-management/supervisor/boards/');

export const createTask = (boardId, data) =>
  api.post(`/api/project-management/board/${boardId}/tasks/`, data);

export const updateTask = (boardId, taskId, data) =>
  api.patch(`/api/project-management/board/${boardId}/tasks/${taskId}/`, data);

export const deleteTask = (boardId, taskId) =>
  api.delete(`/api/project-management/board/${boardId}/tasks/${taskId}/delete/`);

// ── Task Comments ──────────────────────────────────────────────────────────────
export const fetchComments = (boardId, taskId) =>
  api.get(`/api/project-management/board/${boardId}/tasks/${taskId}/comments/`);

export const postComment = (boardId, taskId, body) =>
  api.post(`/api/project-management/board/${boardId}/tasks/${taskId}/comments/`, { body });

export const deleteComment = (boardId, taskId, commentId) =>
  api.delete(`/api/project-management/board/${boardId}/tasks/${taskId}/comments/${commentId}/delete/`);

// ── Task Attachments ───────────────────────────────────────────────────────────
export const uploadAttachment = (boardId, taskId, file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post(`/api/project-management/board/${boardId}/tasks/${taskId}/attachments/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const deleteAttachment = (boardId, taskId, attachmentId) =>
  api.delete(`/api/project-management/board/${boardId}/tasks/${taskId}/attachments/${attachmentId}/delete/`);

// ── Board Activity ─────────────────────────────────────────────────────────────
export const fetchBoardActivity = (boardId) =>
  api.get(`/api/project-management/board/${boardId}/activity/`);

// ── HoD & Dean ─────────────────────────────────────────────────────────────────
export const fetchHodBoards = () =>
  api.get('/api/project-management/hod/boards/');

export const fetchHodStats = () =>
  api.get('/api/project-management/hod/stats/');

// ── Workflow Management ────────────────────────────────────────────────────────
export const fetchWorkflowTemplates = () =>
  api.get('/api/workflow/templates/');

export const fetchWorkflowTemplate = (templateId) =>
  api.get(`/api/workflow/templates/${templateId}/`);

export const createWorkflowTemplate = (data) =>
  api.post('/api/workflow/templates/create/', data);

export const updateWorkflowTemplate = (templateId, data) =>
  api.put(`/api/workflow/templates/${templateId}/update/`, data);

export const deleteWorkflowTemplate = (templateId) =>
  api.delete(`/api/workflow/templates/${templateId}/delete/`);

export const applyWorkflowToProject = (data) =>
  api.post('/api/workflow/apply/', data);

export const fetchProjectWorkflow = (projectBoardId) =>
  api.get(`/api/workflow/project/${projectBoardId}/`);

export const fetchPendingWorkflowStages = () =>
  api.get('/api/workflow/pending/');

export const submitWorkflowStage = (stageInstanceId, data) =>
  api.post(`/api/workflow/stage/${stageInstanceId}/submit/`, data);

export const reviewWorkflowStage = (stageInstanceId, data) =>
  api.post(`/api/workflow/stage/${stageInstanceId}/review/`, data);

export const fetchAvailableProjects = () =>
  api.get('/api/workflow/available-projects/');

export const fetchReviewableProjects = () =>
  api.get('/api/workflow/reviewable-projects/');

export const applyWorkflowBulk = (data) =>
  api.post('/api/workflow/apply-bulk/', data);

export const replaceWorkflowForProject = (projectBoardId, data) =>
  api.put(`/api/workflow/project/${projectBoardId}/replace/`, data);

export const fetchProjectsWorkflowStatus = () =>
  api.get('/api/workflow/projects-status/');
