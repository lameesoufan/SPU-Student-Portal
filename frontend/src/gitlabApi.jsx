import axios from 'axios';
import { setAccessToken, getAccessToken, clearAccessToken } from './api';
const API_BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8000') + '/api/gitlab';
const ROOT_API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,  // ← يبعث الـ cookies تلقائياً
});
let refreshPromise = null;
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});
// لا نحتاج نحط Authorization header يدوي — الـ cookies بتنرسل تلقائياً
// والـ JWTCookieMiddleware بالـ backend بيقري الـ cookie وبيحط الـ header
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
          refreshPromise = axios.post(`${ROOT_API_BASE}/api/token/refresh/`, {}, {
          withCredentials: true,
        }).then((res) => {
          const newAccess = res.data?.access;
          if (newAccess) setAccessToken(newAccess);  // sync with api.jsx
          return res;
        }).finally(() => { refreshPromise = null; });
      }
      await refreshPromise;
      return api(original);
    } catch (refreshError) {
      clearAccessToken();
      refreshError.isSessionExpired = true;
      return Promise.reject(refreshError);
    }
  }
);

// ===== Health Check =====
export const checkGitLabHealth = () =>
  api.get('/health/');

// ===== GitLab Config =====
export const getGitLabConfig = () =>
  api.get('/config/');

// ===== Account Linking =====
export const verifyGitLabToken = (gitlabToken) =>
  api.post('/verify-token/', { gitlab_token: gitlabToken });

export const linkGitLabAccount = (gitlabToken, gitlabUsername) =>
  api.post('/link-account/', {
    gitlab_token: gitlabToken,
    gitlab_username: gitlabUsername || undefined,
  });

export const unlinkGitLabAccount = () =>
  api.post('/unlink-account/');

export const getGitLabAccountStatus = () =>
  api.get('/account-status/');

// ===== Project (per board) =====
export const createGitLabProject = (boardId, data = {}) =>
  api.post(`/board/${boardId}/create-project/`, data);

export const getBoardGitLabInfo = (boardId) =>
  api.get(`/board/${boardId}/`);

// ===== Members =====
export const getBoardMembers = (boardId) =>
  api.get(`/board/${boardId}/members/`);

export const addBoardMember = (boardId, gitlabUsername, accessLevel = 30) =>
  api.post(`/board/${boardId}/members/add/`, {
    gitlab_username: gitlabUsername,
    access_level: accessLevel,
  });

export const removeBoardMember = (boardId, gitlabUserId) =>
  api.post(`/board/${boardId}/members/remove/`, {
    gitlab_user_id: gitlabUserId,
  });

// ===== Commits =====
export const getBoardCommits = (boardId, params = {}) => {
  const query = new URLSearchParams(params).toString();
  return api.get(`/board/${boardId}/commits/${query ? `?${query}` : ''}`);
};

export const getCommitDetail = (boardId, commitId) =>
  api.get(`/board/${boardId}/commits/${commitId}/`);

export const getBoardCommitStats = (boardId) =>
  api.get(`/board/${boardId}/stats/`);

export const syncCommits = (boardId) =>
  api.post(`/board/${boardId}/sync/`);

// ===== All Boards Stats =====
export const getAllBoardsStats = () =>
  api.get('/stats/');
