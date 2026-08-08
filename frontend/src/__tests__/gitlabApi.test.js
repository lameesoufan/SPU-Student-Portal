import { beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => {
  const instances = [];
  const makeInstance = () => {
    const handlers = {
      requestFulfilled: null,
      responseFulfilled: null,
      responseRejected: null,
    };
    const instance = vi.fn();
    instance.defaults = { headers: { common: {} } };
    instance.get = vi.fn();
    instance.post = vi.fn();
    instance.put = vi.fn();
    instance.patch = vi.fn();
    instance.delete = vi.fn();
    instance.interceptors = {
      request: {
        use: vi.fn((fulfilled) => { handlers.requestFulfilled = fulfilled; }),
      },
      response: {
        use: vi.fn((fulfilled, rejected) => {
          handlers.responseFulfilled = fulfilled;
          handlers.responseRejected = rejected;
        }),
      },
    };
    instances.push({ instance, handlers });
    return instance;
  };

  const axios = {
    create: vi.fn(() => makeInstance()),
    post: vi.fn(),
  };
  return { axios, instances };
});

vi.mock('axios', () => ({ default: state.axios }));

import { clearAccessToken, getAccessToken, setAccessToken } from '../api.jsx';
import {
  checkGitLabHealth,
  getGitLabConfig,
  verifyGitLabToken,
  linkGitLabAccount,
  unlinkGitLabAccount,
  getGitLabAccountStatus,
  createGitLabProject,
  getBoardGitLabInfo,
  getBoardMembers,
  addBoardMember,
  removeBoardMember,
  getBoardCommits,
  getCommitDetail,
  getBoardCommitStats,
  syncCommits,
  getAllBoardsStats,
} from '../gitlabApi.jsx';

const main = state.instances[0];
const gitlab = state.instances[1];

describe('GitLab API client security and refresh behavior', () => {
  beforeEach(() => {
    clearAccessToken();
    state.axios.post.mockReset();
    gitlab.instance.mockClear();
    gitlab.instance.get.mockClear();
    gitlab.instance.post.mockClear();
  });

  it('creates a separate credentialed GitLab client under /api/gitlab', () => {
    expect(state.axios.create).toHaveBeenNthCalledWith(2, {
      baseURL: 'http://localhost:8000/api/gitlab',
      withCredentials: true,
    });
  });

  it('does not add Authorization when there is no in-memory token', () => {
    const config = { headers: {} };
    expect(gitlab.handlers.requestFulfilled(config)).toBe(config);
    expect(config.headers.Authorization).toBeUndefined();
  });

  it('adds the current in-memory access token to GitLab requests', () => {
    setAccessToken('access-1');
    const config = { headers: {} };
    gitlab.handlers.requestFulfilled(config);
    expect(config.headers.Authorization).toBe('Bearer access-1');
  });

  it('reads the newest token on every request rather than capturing an old token', () => {
    setAccessToken('one');
    const first = { headers: {} };
    gitlab.handlers.requestFulfilled(first);
    setAccessToken('two');
    const second = { headers: {} };
    gitlab.handlers.requestFulfilled(second);
    expect(first.headers.Authorization).toBe('Bearer one');
    expect(second.headers.Authorization).toBe('Bearer two');
  });

  it('passes successful responses through unchanged', () => {
    const response = { status: 200 };
    expect(gitlab.handlers.responseFulfilled(response)).toBe(response);
  });

  it('does not refresh non-401 errors', async () => {
    const error = { config: { url: '/health/' }, response: { status: 403 } };
    await expect(gitlab.handlers.responseRejected(error)).rejects.toBe(error);
    expect(state.axios.post).not.toHaveBeenCalled();
  });

  it('does not retry an already retried GitLab request', async () => {
    const error = { config: { url: '/health/', _retry: true }, response: { status: 401 } };
    await expect(gitlab.handlers.responseRejected(error)).rejects.toBe(error);
    expect(state.axios.post).not.toHaveBeenCalled();
  });

  it('refreshes on 401, updates shared access token, then retries GitLab request', async () => {
    const original = { url: '/board/4/', method: 'get' };
    const retried = { status: 200 };
    state.axios.post.mockResolvedValueOnce({ data: { access: 'fresh' } });
    gitlab.instance.mockResolvedValueOnce(retried);

    await expect(gitlab.handlers.responseRejected({
      config: original,
      response: { status: 401 },
    })).resolves.toBe(retried);

    expect(state.axios.post).toHaveBeenCalledWith(
      'http://localhost:8000/api/token/refresh/',
      {},
      { withCredentials: true },
    );
    expect(original._retry).toBe(true);
    expect(getAccessToken()).toBe('fresh');
    expect(main.instance.defaults.headers.common.Authorization).toBe('Bearer fresh');
    expect(gitlab.instance).toHaveBeenCalledWith(original);
  });

  it('clears the shared stale access token when GitLab refresh fails', async () => {
    setAccessToken('expired');
    const refreshError = new Error('expired session');
    state.axios.post.mockRejectedValueOnce(refreshError);

    await expect(gitlab.handlers.responseRejected({
      config: { url: '/board/4/' },
      response: { status: 401 },
    })).rejects.toBe(refreshError);

    expect(getAccessToken()).toBeNull();
    expect(main.instance.defaults.headers.common.Authorization).toBeUndefined();
    expect(refreshError.isSessionExpired).toBe(true);
  });

  it('deduplicates simultaneous GitLab refreshes', async () => {
    let resolveRefresh;
    const refresh = new Promise((resolve) => { resolveRefresh = resolve; });
    state.axios.post.mockReturnValueOnce(refresh);
    gitlab.instance.mockResolvedValue({ status: 200 });

    const first = gitlab.handlers.responseRejected({ config: { url: '/board/1/' }, response: { status: 401 } });
    const second = gitlab.handlers.responseRejected({ config: { url: '/board/2/' }, response: { status: 401 } });
    expect(state.axios.post).toHaveBeenCalledTimes(1);

    resolveRefresh({ data: { access: 'shared' } });
    await Promise.all([first, second]);
    expect(gitlab.instance).toHaveBeenCalledTimes(2);
  });
});

describe('GitLab endpoint contracts', () => {
  beforeEach(() => {
    gitlab.instance.get.mockClear();
    gitlab.instance.post.mockClear();
  });

  const cases = [
    ['health check', 'get', () => checkGitLabHealth(), ['/health/']],
    ['configuration', 'get', () => getGitLabConfig(), ['/config/']],
    ['token verification', 'post', () => verifyGitLabToken('gl-token'), ['/verify-token/', { gitlab_token: 'gl-token' }]],
    ['account link with username', 'post', () => linkGitLabAccount('gl-token', 'alice'), ['/link-account/', { gitlab_token: 'gl-token', gitlab_username: 'alice' }]],
    ['account unlink', 'post', () => unlinkGitLabAccount(), ['/unlink-account/']],
    ['account status', 'get', () => getGitLabAccountStatus(), ['/account-status/']],
    ['project creation', 'post', () => createGitLabProject(3, { name: 'repo' }), ['/board/3/create-project/', { name: 'repo' }]],
    ['board GitLab info', 'get', () => getBoardGitLabInfo(3), ['/board/3/']],
    ['board members', 'get', () => getBoardMembers(3), ['/board/3/members/']],
    ['add board member', 'post', () => addBoardMember(3, 'bob', 40), ['/board/3/members/add/', { gitlab_username: 'bob', access_level: 40 }]],
    ['remove board member', 'post', () => removeBoardMember(3, 77), ['/board/3/members/remove/', { gitlab_user_id: 77 }]],
    ['commit detail', 'get', () => getCommitDetail(3, 'abc123'), ['/board/3/commits/abc123/']],
    ['commit stats', 'get', () => getBoardCommitStats(3), ['/board/3/stats/']],
    ['sync commits', 'post', () => syncCommits(3), ['/board/3/sync/']],
    ['all boards stats', 'get', () => getAllBoardsStats(), ['/stats/']],
  ];

  it.each(cases)('%s', (_name, method, call, expectedArgs) => {
    call();
    expect(gitlab.instance[method]).toHaveBeenCalledTimes(1);
    expect(gitlab.instance[method]).toHaveBeenCalledWith(...expectedArgs);
  });

  it('omits an empty GitLab username instead of sending an empty string', () => {
    linkGitLabAccount('gl-token', '');
    expect(gitlab.instance.post).toHaveBeenCalledWith('/link-account/', {
      gitlab_token: 'gl-token',
      gitlab_username: undefined,
    });
  });

  it('uses the default developer access level 30', () => {
    addBoardMember(3, 'bob');
    expect(gitlab.instance.post).toHaveBeenCalledWith('/board/3/members/add/', {
      gitlab_username: 'bob',
      access_level: 30,
    });
  });

  it('serializes commit filters as a query string', () => {
    getBoardCommits(3, { page: 2, per_page: 50 });
    expect(gitlab.instance.get).toHaveBeenCalledWith('/board/3/commits/?page=2&per_page=50');
  });

  it('does not append a question mark when commit filters are empty', () => {
    getBoardCommits(3);
    expect(gitlab.instance.get).toHaveBeenCalledWith('/board/3/commits/');
  });
});
