import { beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => {
  const instance = vi.fn();
  instance.defaults = { headers: { common: {} } };
  instance.get = vi.fn();
  instance.post = vi.fn();
  instance.put = vi.fn();
  instance.patch = vi.fn();
  instance.delete = vi.fn();
  instance.interceptors = { response: { use: vi.fn() } };
  const axios = { create: vi.fn(() => instance), post: vi.fn() };
  return { instance, axios };
});

vi.mock('axios', () => ({ default: state.axios }));

import api, {
  login,
  fetchCurrentUser,
  logoutUser,
  changePassword,
  requestPasswordReset,
  verifyPasswordResetCode,
  confirmPasswordReset,
  changeUsername,
  assignHod,
  studentSelfRegister,
  submitProjectIdea,
  fetchMyIdeas,
  submitStudentProposal,
  fetchMyProposal,
  cancelProposal,
  browseIdeas,
  applyOnIdea,
  fetchMyIdeaApplication,
  doctorReviewApplication,
  supervisorReview,
  hodReview,
  hodReviewDoctorIdea,
  hodReviewApplication,
  respondToInvitation,
  respondToProposalInvitation,
  replaceProposalMember,
  markParticipationFailed,
  markParticipationWithdrawn,
  reverseParticipationToActive,
  designateStudentStatus,
  searchStudents,
  fetchNotifications,
  markNotifRead,
  markAllNotifsRead,
  fetchHodForm,
  saveHodForm,
  fetchStudentForm,
  submitFormResponse,
  fetchResponseByProposal,
  fetchResponseByApplication,
  fetchMyBoard,
  updateBoard,
  createTask,
  updateTask,
  deleteTask,
  postComment,
  deleteComment,
  fetchBoardActivity,
  fetchWorkflowTemplates,
  fetchWorkflowTemplate,
  createWorkflowTemplate,
  updateWorkflowTemplate,
  deleteWorkflowTemplate,
  applyWorkflowToProject,
  fetchProjectWorkflow,
  submitWorkflowStage,
  reviewWorkflowStage,
  replaceWorkflowForProject,
  fetchCommitteesDashboard,
  createCommitteeTemplate,
  updateCommitteeTemplate,
  deleteCommitteeTemplate,
  spawnCommitteesForTemplate,
  approveCommitteeTemplate,
  copyCommitteeTemplate,
  fetchCommittee,
  updateCommittee,
  deleteCommittee,
  updateCommitteeDoctors,
  distributeProjects,
  fetchAvailableCommitteesForSwap,
  swapProject,
  updateProjectSchedules,
  fetchMyCommitteeSchedule,
  fetchProjectReport,
  downloadProjectReport,
  enterGrade,
  enterBulkGrades,
  fetchGradingModes,
  setGradingMode,
  submitGradeDraft,
  fetchGradeDrafts,
  fetchProjectGrades,
  fetchMyCommitteeGrades,
  fetchMyGrades,
  fetchGradesSummary,
  fetchHodGradesSummary,
  exportGrades,
  exportHodGradesWord,
  fetchRooms,
  createRoom,
  updateRoom,
  deleteRoom,
  fetchDoctorAvailability,
  setMyAvailability,
  addMyAvailabilityDay,
  deleteMyAvailability,
  createMyException,
  deleteMyException,
  fetchSolverSettings,
  createSolverSettings,
  updateSolverSettings,
  deleteSolverSettings,
  schedulePreview,
  scheduleApply,
  scheduleReject,
  semesterSetup,
  scheduleAll,
  scheduleApplyAll,
  scheduleRejectAll,
  studentLoginRequest,
  studentLoginVerify,
  requestEmailChange,
  confirmEmailChange,
} from '../api.jsx';

const payload = { value: 1 };

const cases = [
  ['login posts username and password', 'post', () => login('alice', 'secret'), ['/api/token/', { username: 'alice', password: 'secret' }]],
  ['current user uses auth/me', 'get', () => fetchCurrentUser(), ['/api/auth/me/']],
  ['logout posts to logout endpoint', 'post', () => logoutUser(), ['/api/logout/']],
  ['change password preserves all three password fields', 'post', () => changePassword('new', 'new', 'old'), ['/api/change-password/', { current_password: 'old', new_password: 'new', confirm_password: 'new' }]],
  ['password reset request uses identifier', 'post', () => requestPasswordReset('u1'), ['/api/auth/password-reset/request/', { identifier: 'u1' }]],
  ['password reset verify binds session and code', 'post', () => verifyPasswordResetCode('s1', '123456'), ['/api/auth/password-reset/verify/', { session_token: 's1', code: '123456' }]],
  ['password reset confirm binds session, code and passwords', 'post', () => confirmPasswordReset('s1', '123456', 'new', 'new'), ['/api/auth/password-reset/confirm/', { session_token: 's1', code: '123456', new_password: 'new', confirm_password: 'new' }]],
  ['username change uses new_username', 'post', () => changeUsername('new-name'), ['/api/change-username/', { new_username: 'new-name' }]],
  ['assign HoD binds doctor and department', 'post', () => assignHod(7, 'software_engineering'), ['/api/assign-hod/', { doctor_id: 7, department: 'software_engineering' }]],
  ['student self-registration uses university id and password', 'post', () => studentSelfRegister('2026001', 'pw'), ['/api/register/', { university_id: '2026001', password: 'pw' }]],

  ['doctor project idea submission keeps payload', 'post', () => submitProjectIdea(payload), ['/api/projects/ideas/submit/', payload]],
  ['my ideas uses correct endpoint', 'get', () => fetchMyIdeas(), ['/api/projects/ideas/']],
  ['student proposal submission keeps payload', 'post', () => submitStudentProposal(payload), ['/api/projects/proposals/submit/', payload]],
  ['my proposal uses mine endpoint', 'get', () => fetchMyProposal(), ['/api/projects/proposals/mine/']],
  ['proposal cancellation binds proposal id', 'post', () => cancelProposal(11), ['/api/projects/proposals/11/cancel/']],
  ['idea browsing uses browse endpoint', 'get', () => browseIdeas(), ['/api/projects/ideas/browse/']],
  ['application binds idea id', 'post', () => applyOnIdea(12, payload), ['/api/projects/ideas/12/apply/', payload]],
  ['my application uses mine endpoint', 'get', () => fetchMyIdeaApplication(), ['/api/projects/applications/mine/']],
  ['doctor review binds application id', 'post', () => doctorReviewApplication(13, payload), ['/api/projects/applications/13/doctor-review/', payload]],
  ['supervisor review binds proposal id', 'post', () => supervisorReview(14, payload), ['/api/projects/proposals/14/supervisor-review/', payload]],
  ['HoD proposal review binds proposal id', 'post', () => hodReview(15, payload), ['/api/projects/proposals/15/hod-review/', payload]],
  ['HoD doctor idea review binds idea id', 'post', () => hodReviewDoctorIdea(16, payload), ['/api/projects/ideas/16/hod-review/', payload]],
  ['HoD application review binds application id', 'post', () => hodReviewApplication(17, payload), ['/api/projects/applications/17/hod-review/', payload]],
  ['invitation response binds action', 'post', () => respondToInvitation(18, 'accept'), ['/api/projects/invitations/18/respond/', { action: 'accept' }]],
  ['proposal invitation rejection preserves reason', 'post', () => respondToProposalInvitation(19, 'reject', 'busy'), ['/api/projects/proposal-invitations/19/respond/', { action: 'reject', rejection_reason: 'busy' }]],
  ['proposal member replacement binds both members', 'post', () => replaceProposalMember(20, 1, 2), ['/api/projects/proposals/20/replace-member/', { old_member_id: 1, new_member_id: 2 }]],
  ['failed participation binds participation id', 'post', () => markParticipationFailed(21, payload), ['/api/projects/participations/21/mark-failed/', payload]],
  ['withdrawn participation binds participation id', 'post', () => markParticipationWithdrawn(22, payload), ['/api/projects/participations/22/mark-withdrawn/', payload]],
  ['reactivation binds participation id', 'post', () => reverseParticipationToActive(23, payload), ['/api/projects/participations/23/reverse-to-active/', payload]],
  ['student status designation binds student id', 'post', () => designateStudentStatus(24, payload), ['/api/projects/students/24/designate-status/', payload]],
  ['student search sends q as params', 'get', () => searchStudents('sara'), ['/api/projects/students/', { params: { q: 'sara' } }]],

  ['notifications list uses notifications root', 'get', () => fetchNotifications(), ['/api/notifications/']],
  ['mark notification read binds id', 'post', () => markNotifRead(25), ['/api/notifications/25/read/']],
  ['mark all notifications read uses dedicated endpoint', 'post', () => markAllNotifsRead(), ['/api/notifications/mark-all-read/']],

  ['HoD form fetch binds context', 'get', () => fetchHodForm('propose'), ['/api/dy-forms/hod/propose/']],
  ['HoD form save binds context and payload', 'post', () => saveHodForm('propose', payload), ['/api/dy-forms/hod/propose/save/', payload]],
  ['student form fetch binds department and context', 'get', () => fetchStudentForm('software_engineering', 'propose'), ['/api/dy-forms/software_engineering/propose/']],
  ['dynamic response submission keeps payload', 'post', () => submitFormResponse(payload), ['/api/dy-forms/responses/submit/', payload]],
  ['proposal response lookup binds proposal id', 'get', () => fetchResponseByProposal(26), ['/api/dy-forms/responses/proposal/26/']],
  ['application response lookup binds application id', 'get', () => fetchResponseByApplication(27), ['/api/dy-forms/responses/application/27/']],

  ['student board uses board root', 'get', () => fetchMyBoard(), ['/api/project-management/board/']],
  ['board update uses patch and board id', 'patch', () => updateBoard(28, payload), ['/api/project-management/board/28/update/', payload]],
  ['task creation binds board id', 'post', () => createTask(29, payload), ['/api/project-management/board/29/tasks/', payload]],
  ['task update binds board and task ids', 'patch', () => updateTask(29, 30, payload), ['/api/project-management/board/29/tasks/30/', payload]],
  ['task delete binds board and task ids', 'delete', () => deleteTask(29, 30), ['/api/project-management/board/29/tasks/30/delete/']],
  ['comment post keeps body only', 'post', () => postComment(29, 30, 'hello'), ['/api/project-management/board/29/tasks/30/comments/', { body: 'hello' }]],
  ['comment delete binds all ids', 'delete', () => deleteComment(29, 30, 31), ['/api/project-management/board/29/tasks/30/comments/31/delete/']],
  ['board activity binds board id', 'get', () => fetchBoardActivity(29), ['/api/project-management/board/29/activity/']],

  ['workflow templates uses template root', 'get', () => fetchWorkflowTemplates(), ['/api/workflow/templates/']],
  ['single workflow template binds id', 'get', () => fetchWorkflowTemplate(32), ['/api/workflow/templates/32/']],
  ['workflow template create keeps payload', 'post', () => createWorkflowTemplate(payload), ['/api/workflow/templates/create/', payload]],
  ['workflow template update uses put', 'put', () => updateWorkflowTemplate(32, payload), ['/api/workflow/templates/32/update/', payload]],
  ['workflow template delete binds id', 'delete', () => deleteWorkflowTemplate(32), ['/api/workflow/templates/32/delete/']],
  ['workflow application keeps payload', 'post', () => applyWorkflowToProject(payload), ['/api/workflow/apply/', payload]],
  ['project workflow lookup binds board id', 'get', () => fetchProjectWorkflow(33), ['/api/workflow/project/33/']],
  ['plain workflow submission does not force multipart config', 'post', () => submitWorkflowStage(34, payload), ['/api/workflow/stage/34/submit/', payload, undefined]],
  ['workflow review binds stage id', 'post', () => reviewWorkflowStage(34, payload), ['/api/workflow/stage/34/review/', payload]],
  ['workflow replacement uses put', 'put', () => replaceWorkflowForProject(33, payload), ['/api/workflow/project/33/replace/', payload]],

  ['committee dashboard sends semester filter', 'get', () => fetchCommitteesDashboard('2026-1'), ['/api/committees/dashboard/', { params: { semester: '2026-1' } }]],
  ['committee template create keeps payload', 'post', () => createCommitteeTemplate(payload), ['/api/committees/templates/', payload]],
  ['committee template update uses patch', 'patch', () => updateCommitteeTemplate(35, payload), ['/api/committees/templates/35/', payload]],
  ['committee template delete binds id', 'delete', () => deleteCommitteeTemplate(35), ['/api/committees/templates/35/']],
  ['committee spawn binds template id', 'post', () => spawnCommitteesForTemplate(35), ['/api/committees/templates/35/spawn/']],
  ['committee approval binds template id', 'post', () => approveCommitteeTemplate(35), ['/api/committees/templates/35/approve/']],
  ['committee copy keeps payload', 'post', () => copyCommitteeTemplate(35, payload), ['/api/committees/templates/35/copy/', payload]],
  ['committee lookup binds id', 'get', () => fetchCommittee(36), ['/api/committees/committees/36/']],
  ['committee update uses patch', 'patch', () => updateCommittee(36, payload), ['/api/committees/committees/36/', payload]],
  ['committee delete binds id', 'delete', () => deleteCommittee(36), ['/api/committees/committees/36/']],
  ['committee doctor update uses doctors endpoint', 'post', () => updateCommitteeDoctors(36, payload), ['/api/committees/committees/36/doctors/', payload]],
  ['project distribution keeps payload', 'post', () => distributeProjects(payload), ['/api/committees/distribute/', payload]],
  ['available swap committees bind project identity', 'get', () => fetchAvailableCommitteesForSwap(36, 'proposal', 37), ['/api/committees/committees/36/available-for-swap/', { params: { project_source: 'proposal', project_id: 37 } }]],
  ['project swap binds committee id', 'post', () => swapProject(36, payload), ['/api/committees/committees/36/swap_project/', payload]],
  ['schedule updates are wrapped under updates', 'post', () => updateProjectSchedules([payload]), ['/api/committees/update-schedules/', { updates: [payload] }]],
  ['doctor committee schedule sends semester', 'get', () => fetchMyCommitteeSchedule('2026-1'), ['/api/committees/my-schedule/', { params: { semester: '2026-1' } }]],

  ['project report lookup binds source and id', 'get', () => fetchProjectReport('proposal', 38), ['/api/grades/report/proposal/38/']],
  ['project report download is requested as blob', 'get', () => downloadProjectReport('proposal', 38), ['/api/grades/report/proposal/38/download/', { responseType: 'blob' }]],
  ['individual grade entry keeps payload', 'post', () => enterGrade(payload), ['/api/grades/enter/', payload]],
  ['bulk individual grade entry keeps payload', 'post', () => enterBulkGrades(payload), ['/api/grades/enter/bulk/', payload]],
  ['grading modes lookup uses dedicated endpoint', 'get', () => fetchGradingModes(), ['/api/grades/grading-mode/']],
  ['grading mode update preserves boolean collective flag', 'post', () => setGradingMode(39, true), ['/api/grades/grading-mode/', { committee_id: 39, collective: true }]],
  ['collective grade draft uses draft endpoint', 'post', () => submitGradeDraft(payload), ['/api/grades/draft/', payload]],
  ['grade draft lookup binds full committee/project identity', 'get', () => fetchGradeDrafts(39, 'proposal', 38, 'discussion'), ['/api/grades/draft/', { params: { committee_id: 39, project_source: 'proposal', project_id: 38, committee_type: 'discussion' } }]],
  ['project grades lookup binds source and id', 'get', () => fetchProjectGrades('proposal', 38), ['/api/grades/project/proposal/38/']],
  ['my committee grades sends semester', 'get', () => fetchMyCommitteeGrades('2026-1'), ['/api/grades/my-committee-grades/', { params: { semester: '2026-1' } }]],
  ['student grades uses my-grades endpoint', 'get', () => fetchMyGrades(), ['/api/grades/my-grades/']],
  ['grades summary maps camelCase arguments to backend query names', 'get', () => fetchGradesSummary('2026-1', 'software_engineering', 'graduation_1', 'discussion'), ['/api/grades/summary/', { params: { semester: '2026-1', department: 'software_engineering', project_type: 'graduation_1', committee_type: 'discussion' } }]],
  ['HoD grades summary does not send department', 'get', () => fetchHodGradesSummary('2026-1', 'graduation_1', 'discussion'), ['/api/grades/hod-summary/', { params: { semester: '2026-1', project_type: 'graduation_1', committee_type: 'discussion' } }]],
  ['grade export uses blob response and all filters', 'get', () => exportGrades('2026-1', 'software_engineering', 'graduation_1', 'discussion', '2026-08-07'), ['/api/grades/export/', { params: { semester: '2026-1', department: 'software_engineering', project_type: 'graduation_1', committee_type: 'discussion', export_date: '2026-08-07' }, responseType: 'blob' }]],
  ['HoD Word export uses blob response', 'get', () => exportHodGradesWord('2026-1', 'graduation_1', 'discussion'), ['/api/grades/export/word/', { params: { semester: '2026-1', project_type: 'graduation_1', committee_type: 'discussion' }, responseType: 'blob' }]],

  ['rooms list forwards params', 'get', () => fetchRooms({ active: true }), ['/api/committees/rooms/', { params: { active: true } }]],
  ['room create keeps payload', 'post', () => createRoom(payload), ['/api/committees/rooms/', payload]],
  ['room update uses patch', 'patch', () => updateRoom(40, payload), ['/api/committees/rooms/40/', payload]],
  ['room delete binds id', 'delete', () => deleteRoom(40), ['/api/committees/rooms/40/']],
  ['doctor availability sends doctor id', 'get', () => fetchDoctorAvailability(41), ['/api/committees/availability/', { params: { doctor_id: 41 } }]],
  ['self availability set wraps weekdays', 'post', () => setMyAvailability([1, 2]), ['/api/committees/my-availability/', { weekdays: [1, 2] }]],
  ['self availability add wraps weekday', 'post', () => addMyAvailabilityDay(3), ['/api/committees/my-availability/', { weekday: 3 }]],
  ['self availability delete binds id', 'delete', () => deleteMyAvailability(42), ['/api/committees/my-availability/42/']],
  ['self exception create keeps payload', 'post', () => createMyException(payload), ['/api/committees/my-availability/exceptions/', payload]],
  ['self exception delete binds id', 'delete', () => deleteMyException(43), ['/api/committees/my-availability/exceptions/43/']],
  ['solver settings forwards params', 'get', () => fetchSolverSettings({ semester: '2026-1' }), ['/api/committees/solver-settings/', { params: { semester: '2026-1' } }]],
  ['solver settings create keeps payload', 'post', () => createSolverSettings(payload), ['/api/committees/solver-settings/', payload]],
  ['solver settings update uses patch', 'patch', () => updateSolverSettings(44, payload), ['/api/committees/solver-settings/44/', payload]],
  ['solver settings delete binds id', 'delete', () => deleteSolverSettings(44), ['/api/committees/solver-settings/44/']],
  ['schedule preview keeps payload', 'post', () => schedulePreview(payload), ['/api/committees/schedule/preview/', payload]],
  ['schedule apply binds run id', 'post', () => scheduleApply(45), ['/api/committees/schedule/45/apply/']],
  ['schedule reject binds run id', 'post', () => scheduleReject(45), ['/api/committees/schedule/45/reject/']],
  ['semester setup keeps payload', 'post', () => semesterSetup(payload), ['/api/committees/semester-setup/', payload]],
  ['schedule all keeps payload', 'post', () => scheduleAll(payload), ['/api/committees/schedule-all/', payload]],
  ['schedule apply all wraps semester', 'post', () => scheduleApplyAll('2026-1'), ['/api/committees/schedule-apply-all/', { semester: '2026-1' }]],
  ['schedule reject all wraps semester', 'post', () => scheduleRejectAll('2026-1'), ['/api/committees/schedule-reject-all/', { semester: '2026-1' }]],

  ['student login request keeps university id and password', 'post', () => studentLoginRequest('2026001', 'pw'), ['/api/auth/student-login-request/', { university_id: '2026001', password: 'pw' }]],
  ['student login verify binds session and code', 'post', () => studentLoginVerify('session', '654321'), ['/api/auth/student-login-verify/', { session_token: 'session', code: '654321' }]],
  ['email change request binds new email and current password', 'post', () => requestEmailChange('new@example.com', 'pw'), ['/api/change-email/request/', { new_email: 'new@example.com', current_password: 'pw' }]],
  ['email change confirm binds session and code', 'post', () => confirmEmailChange('session', '654321'), ['/api/change-email/confirm/', { session_token: 'session', code: '654321' }]],
];

describe('frontend to backend API contracts', () => {
  beforeEach(() => {
    for (const method of ['get', 'post', 'put', 'patch', 'delete']) {
      api[method].mockClear();
    }
  });

  it.each(cases)('%s', (_name, method, call, expectedArgs) => {
    call();
    expect(api[method]).toHaveBeenCalledTimes(1);
    expect(api[method]).toHaveBeenCalledWith(...expectedArgs);
  });

  it('multipart workflow submission advertises multipart form data', () => {
    const form = new FormData();
    form.append('answer', 'x');
    submitWorkflowStage(50, form);
    expect(api.post).toHaveBeenCalledWith(
      '/api/workflow/stage/50/submit/',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('optional summary filters are omitted instead of sent as empty strings', () => {
    fetchGradesSummary('', '', '', '');
    expect(api.get).toHaveBeenCalledWith('/api/grades/summary/', { params: {} });
  });

  it('committee dashboard omits an empty semester', () => {
    fetchCommitteesDashboard('');
    expect(api.get).toHaveBeenCalledWith('/api/committees/dashboard/', { params: {} });
  });

  it('doctor availability omits an empty doctor id', () => {
    fetchDoctorAvailability(null);
    expect(api.get).toHaveBeenCalledWith('/api/committees/availability/', { params: {} });
  });
});
