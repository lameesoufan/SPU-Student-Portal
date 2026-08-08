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
  importUsers,
  importProjects,
  downloadProjectImportTemplate,
  fetchProjectImportHistory,
  fetchProjectImportRows,
  uploadReferenceDb,
  uploadAttachment,
  uploadProjectReport,
  exportCommittees,
  exportProjectsAssignment,
  fetchCommittees,
  fetchProjectsAssignment,
  fetchGradesSummary,
  fetchHodGradesSummary,
  exportGrades,
  exportHodGrades,
  fetchMyCommitteeSchedule,
} from '../api.jsx';

const makeFile = (name, type = 'text/plain') => new File(['content'], name, { type });

describe('file upload and export contracts', () => {
  beforeEach(() => {
    api.get.mockClear();
    api.post.mockClear();
  });

  it('builds multipart user import payload with file and role', () => {
    const file = makeFile('users.csv', 'text/csv');
    importUsers(file, 'student');
    const [url, form, config] = api.post.mock.calls[0];
    expect(url).toBe('/api/import-users/');
    expect(form).toBeInstanceOf(FormData);
    expect(form.get('file').name).toBe('users.csv');
    expect(form.get('role')).toBe('student');
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } });
  });

  it('defaults project import to dry-run mode', () => {
    const file = makeFile('projects.xlsx');
    importProjects(file);
    expect(api.post.mock.calls[0][0]).toBe('/api/import/projects/?dry_run=true');
  });

  it('uses commit mode when dry_run is false', () => {
    const file = makeFile('projects.xlsx');
    importProjects(file, { dry_run: false });
    expect(api.post.mock.calls[0][0]).toBe('/api/import/projects/?dry_run=false');
  });

  it('carries preview_result_id into project import form when provided', () => {
    const file = makeFile('projects.xlsx');
    importProjects(file, { dry_run: false, preview_result_id: 'preview-1' });
    const form = api.post.mock.calls[0][1];
    expect(form.get('preview_result_id')).toBe('preview-1');
  });

  it('does not send an empty preview_result_id', () => {
    const file = makeFile('projects.xlsx');
    importProjects(file, { preview_result_id: '' });
    const form = api.post.mock.calls[0][1];
    expect(form.has('preview_result_id')).toBe(false);
  });

  it('downloads the project import template as a blob', () => {
    downloadProjectImportTemplate();
    expect(api.get).toHaveBeenCalledWith('/api/import/template/', { responseType: 'blob' });
  });

  it('forwards project import history filters as params', () => {
    fetchProjectImportHistory({ page: 2, status: 'completed' });
    expect(api.get).toHaveBeenCalledWith('/api/import/history/', {
      params: { page: 2, status: 'completed' },
    });
  });

  it('binds import session id when fetching imported rows', () => {
    fetchProjectImportRows('session-1');
    expect(api.get).toHaveBeenCalledWith('/api/import/history/session-1/rows/');
  });

  it('uploads reference database as multipart form data', () => {
    const file = makeFile('reference.sqlite3', 'application/octet-stream');
    uploadReferenceDb(file);
    const [url, form, config] = api.post.mock.calls[0];
    expect(url).toBe('/api/upload-reference/');
    expect(form.get('file').name).toBe('reference.sqlite3');
    expect(config.headers['Content-Type']).toBe('multipart/form-data');
  });

  it('uploads task attachment under the exact board and task', () => {
    const file = makeFile('report.pdf', 'application/pdf');
    uploadAttachment(5, 6, file);
    const [url, form, config] = api.post.mock.calls[0];
    expect(url).toBe('/api/project-management/board/5/tasks/6/attachments/');
    expect(form.get('file').name).toBe('report.pdf');
    expect(config.headers['Content-Type']).toBe('multipart/form-data');
  });

  it('passes an existing report FormData through without rebuilding it', () => {
    const form = new FormData();
    form.append('project_source', 'proposal');
    uploadProjectReport(form);
    expect(api.post).toHaveBeenCalledWith('/api/grades/report/upload/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  });

  it('committee export preserves format, semester, and blob response', () => {
    exportCommittees('pdf', '2026-1');
    expect(api.get).toHaveBeenCalledWith('/api/committees/export/', {
      params: { format: 'pdf', semester: '2026-1' },
      responseType: 'blob',
    });
  });

  it('committee export omits an empty semester', () => {
    exportCommittees('xlsx', '');
    expect(api.get).toHaveBeenCalledWith('/api/committees/export/', {
      params: { format: 'xlsx' },
      responseType: 'blob',
    });
  });

  it('project assignment export is a blob and preserves semester', () => {
    exportProjectsAssignment('2026-1');
    expect(api.get).toHaveBeenCalledWith('/api/committees/projects-assignment/export/', {
      params: { semester: '2026-1' },
      responseType: 'blob',
    });
  });
});

describe('optional filter behavior', () => {
  beforeEach(() => api.get.mockClear());

  it('committee list keeps caller params and adds cache-busting timestamp', () => {
    vi.spyOn(Date, 'now').mockReturnValue(123456);
    fetchCommittees({ semester: '2026-1', department: 'software_engineering' });
    expect(api.get).toHaveBeenCalledWith('/api/committees/committees/', {
      params: {
        semester: '2026-1',
        department: 'software_engineering',
        _t: 123456,
      },
    });
  });

  it('projects assignment omits empty semester', () => {
    fetchProjectsAssignment('');
    expect(api.get).toHaveBeenCalledWith('/api/committees/projects-assignment/', { params: {} });
  });

  it('my committee schedule omits empty semester', () => {
    fetchMyCommitteeSchedule(null);
    expect(api.get).toHaveBeenCalledWith('/api/committees/my-schedule/', { params: {} });
  });

  it('grades summary sends only populated filters', () => {
    fetchGradesSummary('2026-1', '', 'graduation_2', '');
    expect(api.get).toHaveBeenCalledWith('/api/grades/summary/', {
      params: { semester: '2026-1', project_type: 'graduation_2' },
    });
  });

  it('HoD grades summary sends only populated filters', () => {
    fetchHodGradesSummary('', 'graduation_1', '');
    expect(api.get).toHaveBeenCalledWith('/api/grades/hod-summary/', {
      params: { project_type: 'graduation_1' },
    });
  });

  it('grade export omits empty filters and remains a blob request', () => {
    exportGrades('', '', '', '', '');
    expect(api.get).toHaveBeenCalledWith('/api/grades/export/', {
      params: {},
      responseType: 'blob',
    });
  });

  it('HoD grade export never injects a department filter', () => {
    exportHodGrades('2026-1', 'graduation_1', 'discussion', '2026-08-07');
    expect(api.get).toHaveBeenCalledWith('/api/grades/export/', {
      params: {
        semester: '2026-1',
        project_type: 'graduation_1',
        committee_type: 'discussion',
        export_date: '2026-08-07',
      },
      responseType: 'blob',
    });
  });
});
