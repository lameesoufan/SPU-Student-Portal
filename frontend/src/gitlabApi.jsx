import axios from 'axios';

const API_BASE = 'http://localhost:8000/api/gitlab';

const getAuthHeaders = () => {
  const token = localStorage.getItem('access');
  return {
    headers: { Authorization: `Bearer ${token}` },
  };
};

// ===== Health Check =====
export const checkGitLabHealth = () =>
  axios.get(`${API_BASE}/health/`, getAuthHeaders());

// ===== GitLab Config =====
export const getGitLabConfig = () =>
  axios.get(`${API_BASE}/config/`, getAuthHeaders());

// ===== Account Linking =====
export const verifyGitLabToken = (gitlabToken) =>
  axios.post(`${API_BASE}/verify-token/`, { gitlab_token: gitlabToken }, getAuthHeaders());

export const linkGitLabAccount = (gitlabToken, gitlabUsername) =>
  axios.post(`${API_BASE}/link-account/`, {
    gitlab_token: gitlabToken,
    gitlab_username: gitlabUsername || undefined,
  }, getAuthHeaders());

export const unlinkGitLabAccount = () =>
  axios.post(`${API_BASE}/unlink-account/`, {}, getAuthHeaders());

export const getGitLabAccountStatus = () =>
  axios.get(`${API_BASE}/account-status/`, getAuthHeaders());

// ===== Project (per board) =====
export const createGitLabProject = (boardId, data = {}) =>
  axios.post(`${API_BASE}/board/${boardId}/create-project/`, data, getAuthHeaders());

export const getBoardGitLabInfo = (boardId) =>
  axios.get(`${API_BASE}/board/${boardId}/`, getAuthHeaders());

// ===== Members =====
export const getBoardMembers = (boardId) =>
  axios.get(`${API_BASE}/board/${boardId}/members/`, getAuthHeaders());

export const addBoardMember = (boardId, gitlabUsername, accessLevel = 30) =>
  axios.post(`${API_BASE}/board/${boardId}/members/add/`, {
    gitlab_username: gitlabUsername,
    access_level: accessLevel,
  }, getAuthHeaders());

export const removeBoardMember = (boardId, gitlabUserId) =>
  axios.post(`${API_BASE}/board/${boardId}/members/remove/`, {
    gitlab_user_id: gitlabUserId,
  }, getAuthHeaders());

// ===== Commits =====
export const getBoardCommits = (boardId, params = {}) => {
  const query = new URLSearchParams(params).toString();
  return axios.get(`${API_BASE}/board/${boardId}/commits/${query ? `?${query}` : ''}`, getAuthHeaders());
};

export const getCommitDetail = (boardId, commitId) =>
  axios.get(`${API_BASE}/board/${boardId}/commits/${commitId}/`, getAuthHeaders());

export const getBoardCommitStats = (boardId) =>
  axios.get(`${API_BASE}/board/${boardId}/stats/`, getAuthHeaders());

export const syncCommits = (boardId) =>
  axios.post(`${API_BASE}/board/${boardId}/sync/`, {}, getAuthHeaders());

// ===== All Boards Stats =====
export const getAllBoardsStats = () =>
  axios.get(`${API_BASE}/stats/`, getAuthHeaders());
