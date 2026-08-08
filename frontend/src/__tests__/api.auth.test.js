import { beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => {
  const handlers = { responseFulfilled: null, responseRejected: null };
  const instance = vi.fn();
  instance.defaults = { headers: { common: {} } };
  instance.get = vi.fn();
  instance.post = vi.fn();
  instance.put = vi.fn();
  instance.patch = vi.fn();
  instance.delete = vi.fn();
  instance.interceptors = {
    response: {
      use: vi.fn((fulfilled, rejected) => {
        handlers.responseFulfilled = fulfilled;
        handlers.responseRejected = rejected;
      }),
    },
  };
  const axios = {
    create: vi.fn(() => instance),
    post: vi.fn(),
  };
  return { handlers, instance, axios };
});

vi.mock('axios', () => ({ default: state.axios }));

import api, {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from '../api.jsx';

const make401 = (config = { url: '/api/auth/me/' }) => ({
  config,
  response: { status: 401 },
});

describe('main API client authentication contract', () => {
  beforeEach(() => {
    state.instance.mockClear();
    state.instance.get.mockClear();
    state.instance.post.mockClear();
    state.instance.put.mockClear();
    state.instance.patch.mockClear();
    state.instance.delete.mockClear();
    state.axios.post.mockReset();
    clearAccessToken();
  });

  it('creates the API client with credentials enabled', () => {
    expect(state.axios.create).toHaveBeenCalledWith({
      baseURL: 'http://localhost:8000',
      withCredentials: true,
    });
  });

  it('stores an access token only in memory and the axios default header', () => {
    setAccessToken('access-123');
    expect(getAccessToken()).toBe('access-123');
    expect(api.defaults.headers.common.Authorization).toBe('Bearer access-123');
  });

  it('clears the in-memory token and Authorization header', () => {
    setAccessToken('access-123');
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
    expect(api.defaults.headers.common.Authorization).toBeUndefined();
  });

  it('treats an empty token as clearing the Authorization header', () => {
    setAccessToken('access-123');
    setAccessToken('');
    expect(getAccessToken()).toBe('');
    expect(api.defaults.headers.common.Authorization).toBeUndefined();
  });

  it('passes successful responses through unchanged', () => {
    const response = { status: 200, data: { ok: true } };
    expect(state.handlers.responseFulfilled(response)).toBe(response);
  });

  it('does not refresh non-401 failures', async () => {
    const error = { config: { url: '/api/auth/me/' }, response: { status: 403 } };
    await expect(state.handlers.responseRejected(error)).rejects.toBe(error);
    expect(state.axios.post).not.toHaveBeenCalled();
  });

  it('does not refresh a failure without an original request config', async () => {
    const error = { response: { status: 401 } };
    await expect(state.handlers.responseRejected(error)).rejects.toBe(error);
    expect(state.axios.post).not.toHaveBeenCalled();
  });

  it('does not refresh an already retried request', async () => {
    const error = make401({ url: '/api/auth/me/', _retry: true });
    await expect(state.handlers.responseRejected(error)).rejects.toBe(error);
    expect(state.axios.post).not.toHaveBeenCalled();
  });

  it('does not recursively refresh token endpoints', async () => {
    const error = make401({ url: '/api/token/' });
    await expect(state.handlers.responseRejected(error)).rejects.toBe(error);
    expect(state.axios.post).not.toHaveBeenCalled();
  });

  it('refreshes once, stores the new access token, and retries the original request', async () => {
    const original = { url: '/api/auth/me/', method: 'get' };
    const retried = { status: 200 };
    state.axios.post.mockResolvedValueOnce({ data: { access: 'fresh-token' } });
    state.instance.mockResolvedValueOnce(retried);

    await expect(state.handlers.responseRejected(make401(original))).resolves.toBe(retried);

    expect(original._retry).toBe(true);
    expect(state.axios.post).toHaveBeenCalledWith(
      'http://localhost:8000/api/token/refresh/',
      {},
      { withCredentials: true },
    );
    expect(getAccessToken()).toBe('fresh-token');
    expect(api.defaults.headers.common.Authorization).toBe('Bearer fresh-token');
    expect(state.instance).toHaveBeenCalledWith(original);
  });

  it('supports cookie-only refresh responses that do not contain an access token', async () => {
    const original = { url: '/api/notifications/', method: 'get' };
    state.axios.post.mockResolvedValueOnce({ data: {} });
    state.instance.mockResolvedValueOnce({ status: 200 });

    await state.handlers.responseRejected(make401(original));

    expect(getAccessToken()).toBeNull();
    expect(state.instance).toHaveBeenCalledWith(original);
  });

  it('clears a stale access token when refresh fails', async () => {
    setAccessToken('expired-token');
    const refreshError = new Error('refresh failed');
    state.axios.post.mockRejectedValueOnce(refreshError);

    await expect(
      state.handlers.responseRejected(make401({ url: '/api/auth/me/' })),
    ).rejects.toBe(refreshError);

    expect(getAccessToken()).toBeNull();
    expect(api.defaults.headers.common.Authorization).toBeUndefined();
  });

  it('deduplicates simultaneous refresh attempts', async () => {
    let resolveRefresh;
    const refresh = new Promise((resolve) => { resolveRefresh = resolve; });
    state.axios.post.mockReturnValueOnce(refresh);
    state.instance.mockResolvedValue({ status: 200 });

    const first = state.handlers.responseRejected(make401({ url: '/api/a/' }));
    const second = state.handlers.responseRejected(make401({ url: '/api/b/' }));

    expect(state.axios.post).toHaveBeenCalledTimes(1);
    resolveRefresh({ data: { access: 'shared-token' } });
    await Promise.all([first, second]);

    expect(state.instance).toHaveBeenCalledTimes(2);
    expect(getAccessToken()).toBe('shared-token');
  });

  it('allows a new refresh after the previous refresh promise has settled', async () => {
    state.axios.post
      .mockResolvedValueOnce({ data: { access: 'one' } })
      .mockResolvedValueOnce({ data: { access: 'two' } });
    state.instance.mockResolvedValue({ status: 200 });

    await state.handlers.responseRejected(make401({ url: '/api/one/' }));
    await state.handlers.responseRejected(make401({ url: '/api/two/' }));

    expect(state.axios.post).toHaveBeenCalledTimes(2);
    expect(getAccessToken()).toBe('two');
  });
});
