import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

// ── In-memory access token (fallback if cookies don't work) ──
let _accessToken = null;

export function setAccessToken(token) {
  _accessToken = token;
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
}

export function clearAccessToken() {
  _accessToken = null;
  delete api.defaults.headers.common['Authorization'];
}

let refreshPromise = null;

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
          withCredentials: true,
        }).then((res) => {
          const newAccess = res.data?.access;
          if (newAccess) setAccessToken(newAccess);
          return res;
        }).finally(() => { refreshPromise = null; });
      }
      await refreshPromise;
      return api(original);
    } catch (refreshError) {
      clearAccessToken();
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

export const fetchCurrentUser = () => api.get('/api/auth/me/');

export const logoutUser = () =>
  api.post('/api/logout/');

export const changePassword = (new_password, confirm_password, current_password = '') =>
  api.post('/api/change-password/', { current_password, new_password, confirm_password });
export const requestPasswordReset = (identifier) => api.post('/api/auth/password-reset/request/', { identifier });
export const verifyPasswordResetCode = (session_token, code) => api.post('/api/auth/password-reset/verify/', { session_token, code });
export const confirmPasswordReset = (session_token, code, new_password, confirm_password) =>
  api.post('/api/auth/password-reset/confirm/', { session_token, code, new_password, confirm_password });
export const changeUsername = (new_username) =>
  api.post('/api/change-username/', { new_username });

export const fetchUsernameSuggestions = () =>
  api.get('/api/username-suggestions/');
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

export const fetchStudentStatusManagement = (params = {}) =>
  api.get('/api/projects/participations/status-management/', { params });

export const fetchStudentStatusStats = (params = {}) =>
  api.get('/api/projects/participations/status-management/stats/', { params });

export const markParticipationFailed = (participationId, payload = {}) =>
  api.post(`/api/projects/participations/${participationId}/mark-failed/`, payload);

export const markParticipationWithdrawn = (participationId, payload = {}) =>
  api.post(`/api/projects/participations/${participationId}/mark-withdrawn/`, payload);

export const reverseParticipationToActive = (participationId, payload = {}) =>
  api.post(`/api/projects/participations/${participationId}/reverse-to-active/`, payload);

export const fetchParticipationHistory = (participationId) =>
  api.get(`/api/projects/participations/${participationId}/history/`);

export const designateStudentStatus = (studentId, payload = {}) =>
  api.post(`/api/projects/students/${studentId}/designate-status/`, payload);

export const fetchStudentParticipationHistory = (studentId) =>
  api.get(`/api/projects/students/${studentId}/participation-history/`);

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
// ── Committees (Dean) ────────────────────────────────────────────────────────
// Backend endpoints (all require Dean role):
//   GET    /api/committees/dashboard/
//   GET    /api/committees/templates/                POST  /api/committees/templates/
//   GET    /api/committees/templates/{id}/           PATCH /api/committees/templates/{id}/
//   DELETE /api/committees/templates/{id}/
//   POST   /api/committees/templates/{id}/spawn/
//   POST   /api/committees/templates/{id}/approve/
//   POST   /api/committees/templates/{id}/copy/
//   GET    /api/committees/templates/{id}/preview_distribution/
//   GET    /api/committees/committees/               GET   /api/committees/committees/{id}/
//   PATCH  /api/committees/committees/{id}/
//   POST   /api/committees/committees/{id}/doctors/
//   POST   /api/committees/committees/{id}/swap_project/
//   POST   /api/committees/distribute/
//   GET    /api/committees/export/?format=pdf|xlsx

export const fetchCommitteesDashboard = (semester) =>
  api.get('/api/committees/dashboard/', { params: semester ? { semester } : {} });

export const fetchCommitteeTemplates = () =>
  api.get('/api/committees/templates/');

export const fetchCommitteeTemplate = (id) =>
  api.get(`/api/committees/templates/${id}/`);

export const createCommitteeTemplate = (data) =>
  api.post('/api/committees/templates/', data);

export const updateCommitteeTemplate = (id, data) =>
  api.patch(`/api/committees/templates/${id}/`, data);

export const deleteCommitteeTemplate = (id) =>
  api.delete(`/api/committees/templates/${id}/`);

export const spawnCommitteesForTemplate = (id) =>
  api.post(`/api/committees/templates/${id}/spawn/`);

export const approveCommitteeTemplate = (id) =>
  api.post(`/api/committees/templates/${id}/approve/`);

export const copyCommitteeTemplate = (id, data) =>
  api.post(`/api/committees/templates/${id}/copy/`, data);

export const previewTemplateDistribution = (id) =>
  api.get(`/api/committees/templates/${id}/preview_distribution/`);

export const fetchCommittees = (params = {}) =>
  api.get('/api/committees/committees/', {
    params: { ...params, _t: Date.now() },  // cache-busting
  });

export const fetchCommittee = (id) =>
  api.get(`/api/committees/committees/${id}/`);

export const updateCommittee = (id, data) =>
  api.patch(`/api/committees/committees/${id}/`, data);

export const deleteCommittee = (id) =>
  api.delete(`/api/committees/committees/${id}/`);

export const updateCommitteeDoctors = (id, data) =>
  api.post(`/api/committees/committees/${id}/doctors/`, data);

export const swapCommitteeProject = (id, data) =>
  api.post(`/api/committees/committees/${id}/swap_project/`, data);

export const distributeProjects = (data) =>
  api.post('/api/committees/distribute/', data);

export const exportCommittees = (format, semester) =>
  api.get('/api/committees/export/', {
    params: { format, ...(semester ? { semester } : {}) },
    responseType: 'blob',
  });

export const fetchProjectsAssignment = (semester) =>
  api.get('/api/committees/projects-assignment/', {
    params: semester ? { semester } : {},
  });

export const exportProjectsAssignment = (semester) =>
  api.get('/api/committees/projects-assignment/export/', {
    params: semester ? { semester } : {},
    responseType: 'blob',
  });

// Fetch available committees for swapping (same type, dept, project_type)
export const fetchAvailableCommitteesForSwap = (committeeId, projectSource, projectId) =>
  api.get(`/api/committees/committees/${committeeId}/available-for-swap/`, {
    params: { project_source: projectSource, project_id: projectId },
  });

// Swap/move a project to another committee
export const swapProject = (committeeId, data) =>
  api.post(`/api/committees/committees/${committeeId}/swap_project/`, data);

// Update project schedules (date, time, location)
export const updateProjectSchedules = (updates) =>
  api.post('/api/committees/update-schedules/', { updates });

// ── Doctors list for committee template form ────────────────────────────────
// Reuse existing /api/doctors/ endpoint (same as AssignHod).
// Returns: [{id, username, first_name, last_name, department, role}, ...]
export function getAccessToken() {
  return _accessToken;
}

// ── Doctor Committee Schedule ─────────────────────────────────────────────────
export const fetchMyCommitteeSchedule = (semester) =>
  api.get('/api/committees/my-schedule/', { params: semester ? { semester } : {} });

// ── Grades ────────────────────────────────────────────────────────────────────
export const uploadProjectReport = (formData) =>
  api.post('/api/grades/report/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const fetchProjectReport = (source, pid) =>
  api.get(`/api/grades/report/${source}/${pid}/`);

export const downloadProjectReport = (source, pid) =>
  api.get(`/api/grades/report/${source}/${pid}/download/`, { responseType: 'blob' });

export const enterGrade = (data) =>
  api.post('/api/grades/enter/', data);

export const enterBulkGrades = (data) =>
  api.post('/api/grades/enter/bulk/', data);

// Collective grading
export const fetchGradingModes = () =>
  api.get('/api/grades/grading-mode/');

export const setGradingMode = (committee_id, collective) =>
  api.post('/api/grades/grading-mode/', { committee_id, collective });

export const submitGradeDraft = (data) =>
  api.post('/api/grades/draft/', data);

export const fetchGradeDrafts = (committee_id, project_source, project_id, committee_type) =>
  api.get('/api/grades/draft/', { params: { committee_id, project_source, project_id, committee_type } });

export const fetchProjectGrades = (source, pid) =>
  api.get(`/api/grades/project/${source}/${pid}/`);

export const fetchMyCommitteeGrades = (semester) =>
  api.get('/api/grades/my-committee-grades/', { params: semester ? { semester } : {} });

export const fetchMyGrades = () =>
  api.get('/api/grades/my-grades/');

export const fetchGradesSummary = (semester, department, projectType, committeeType) =>
  api.get('/api/grades/summary/', { 
    params: { 
      ...(semester ? { semester } : {}),
      ...(department ? { department } : {}),
      ...(projectType ? { project_type: projectType } : {}),
      ...(committeeType ? { committee_type: committeeType } : {}),
    } 
  });

export const fetchHodGradesSummary = (semester, projectType, committeeType) =>
  api.get('/api/grades/hod-summary/', {
    params: {
      ...(semester ? { semester } : {}),
      ...(projectType ? { project_type: projectType } : {}),
      ...(committeeType ? { committee_type: committeeType } : {}),
    }
  });

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

export const exportHodGrades = (semester, projectType, committeeType, exportDate) =>
  api.get('/api/grades/export/', {
    params: {
      ...(semester ? { semester } : {}),
      ...(projectType ? { project_type: projectType } : {}),
      ...(committeeType ? { committee_type: committeeType } : {}),
      ...(exportDate ? { export_date: exportDate } : {}),
    },
    responseType: 'blob',
  });

export const exportHodGradesWord = (semester, projectType, committeeType) =>
  api.get('/api/grades/export/word/', {
    params: { 
      ...(semester ? { semester } : {}),
      ...(projectType ? { project_type: projectType } : {}),
      ...(committeeType ? { committee_type: committeeType } : {}),
    },
    responseType: 'blob',
  });

// ── Scheduling: Rooms ─────────────────────────────────────────────────────────
export const fetchRooms = (params = {}) =>
  api.get('/api/committees/rooms/', { params });

export const fetchRoom = (id) =>
  api.get(`/api/committees/rooms/${id}/`);

export const createRoom = (data) =>
  api.post('/api/committees/rooms/', data);

export const updateRoom = (id, data) =>
  api.patch(`/api/committees/rooms/${id}/`, data);

export const deleteRoom = (id) =>
  api.delete(`/api/committees/rooms/${id}/`);

// ── Scheduling: Doctor availability (Dean manages any doctor) ────────────────
export const fetchDoctorAvailability = (doctorId) =>
  api.get('/api/committees/availability/', { params: doctorId ? { doctor_id: doctorId } : {} });

export const createDoctorAvailability = (data) =>
  api.post('/api/committees/availability/', data);

export const deleteDoctorAvailability = (id) =>
  api.delete(`/api/committees/availability/${id}/`);

export const fetchDoctorExceptions = (doctorId) =>
  api.get('/api/committees/availability/exceptions/', { params: doctorId ? { doctor_id: doctorId } : {} });

export const createDoctorException = (data) =>
  api.post('/api/committees/availability/exceptions/', data);

export const deleteDoctorException = (id) =>
  api.delete(`/api/committees/availability/exceptions/${id}/`);

// ── Scheduling: Doctor self-availability ─────────────────────────────────────
export const fetchMyAvailability = () =>
  api.get('/api/committees/my-availability/');

export const setMyAvailability = (weekdays) =>
  api.post('/api/committees/my-availability/', { weekdays });

export const addMyAvailabilityDay = (weekday) =>
  api.post('/api/committees/my-availability/', { weekday });

export const deleteMyAvailability = (id) =>
  api.delete(`/api/committees/my-availability/${id}/`);

export const fetchMyExceptions = () =>
  api.get('/api/committees/my-availability/exceptions/');

export const createMyException = (data) =>
  api.post('/api/committees/my-availability/exceptions/', data);

export const deleteMyException = (id) =>
  api.delete(`/api/committees/my-availability/exceptions/${id}/`);

// ── Scheduling: Solver settings ──────────────────────────────────────────────
export const fetchSolverSettings = (params = {}) =>
  api.get('/api/committees/solver-settings/', { params });

export const fetchSolverSetting = (id) =>
  api.get(`/api/committees/solver-settings/${id}/`);

export const createSolverSettings = (data) =>
  api.post('/api/committees/solver-settings/', data);

export const updateSolverSettings = (id, data) =>
  api.patch(`/api/committees/solver-settings/${id}/`, data);

export const deleteSolverSettings = (id) =>
  api.delete(`/api/committees/solver-settings/${id}/`);

// ── Scheduling: Preview / Apply / Reject ─────────────────────────────────────
export const schedulePreview = (data) =>
  api.post('/api/committees/schedule/preview/', data);

export const scheduleApply = (runId) =>
  api.post(`/api/committees/schedule/${runId}/apply/`);

export const scheduleReject = (runId) =>
  api.post(`/api/committees/schedule/${runId}/reject/`);

// ── Scheduling: Runs history ─────────────────────────────────────────────────
export const fetchSchedulingRuns = (params = {}) =>
  api.get('/api/committees/schedule/runs/', { params });

export const fetchSchedulingRun = (id) =>
  api.get(`/api/committees/schedule/runs/${id}/`);

// ── Wizard: Unified semester setup + scheduling ──────────────────────────────
export const semesterSetup = (data) =>
  api.post('/api/committees/semester-setup/', data);

export const scheduleAll = (data) =>
  api.post('/api/committees/schedule-all/', data);

export const scheduleApplyAll = (semester) =>
  api.post('/api/committees/schedule-apply-all/', { semester });

export const scheduleRejectAll = (semester) =>
  api.post('/api/committees/schedule-reject-all/', { semester });

// ── OTP Authentication (2FA for Students) ────────────────────────────────────
export const studentLoginRequest = (university_id, password) =>
  api.post('/api/auth/student-login-request/', { university_id, password });

export const studentLoginVerify = (session_token, code) =>
  api.post('/api/auth/student-login-verify/', { session_token, code });
export const requestEmailChange = (new_email, current_password) =>
  api.post('/api/change-email/request/', { new_email, current_password });

export const confirmEmailChange = (session_token, code) =>
  api.post('/api/change-email/confirm/', { session_token, code });
