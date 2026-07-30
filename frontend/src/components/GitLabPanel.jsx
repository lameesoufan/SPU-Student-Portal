import React, { useState, useEffect, useCallback } from 'react';
import {
  getGitLabAccountStatus,
  getGitLabConfig,
  linkGitLabAccount,
  verifyGitLabToken,
  getBoardGitLabInfo,
  createGitLabProject,
  getBoardMembers,
  addBoardMember,
  removeBoardMember,
  getBoardCommits,
  syncCommits,
  getBoardCommitStats,
} from '../gitlabApi';
import {
  GitBranch, ExternalLink, RefreshCw, UserPlus, X,
  CheckCircle2, XCircle, AlertCircle, Loader2, Link2,
  Plus, BarChart3, FileCode, Users, Shield, Lock,
  Globe, Eye, ChevronRight, KeyRound, ArrowUpRight,
  GitCommitHorizontal, Code2, CalendarDays, Clock3, Sparkles,
} from 'lucide-react';

const ACCESS_LEVELS = {
  10: { label: 'Guest', style: 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400' },
  20: { label: 'Reporter', style: 'bg-violet-500/10 text-violet-600' },
  30: { label: 'Developer', style: 'bg-violet-500/10 text-violet-600' },
  40: { label: 'Maintainer', style: 'bg-amber-500/10 text-amber-700' },
  50: { label: 'Owner', style: 'bg-amber-500/10 text-amber-700' },
};

const VISIBILITY_STYLES = {
  private: 'bg-amber-500/10 text-amber-700',
  internal: 'bg-violet-500/10 text-violet-600',
  public: 'bg-emerald-500/10 text-emerald-600',
};

// ─── Token Steps Guide ───────────────────────────────────────────────────────
function TokenSteps({ gitlabUrl }) {
  return (
    <div className="mt-3 p-3.5 bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-xl flex flex-col gap-2.5">
      {[
        'Open the university GitLab from this link:',
        'Log in with your GitLab account',
        <>Go to: <strong className="text-gray-900 dark:text-white">Profile → Edit Profile → Access Tokens</strong></>,
        <>Create a new Token with <code className="bg-violet-500/10 text-violet-600 px-1.5 py-0.5 rounded text-[12px] font-semibold">api</code> scope and copy it</>,
        'Paste the Token below',
      ].map((text, idx) => (
        <div key={idx} className="flex items-start gap-2.5 text-[13px] text-gray-500 dark:text-gray-400 leading-relaxed">
          <span className="w-6 h-6 rounded-full bg-violet-600 text-white text-[11px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
            {idx + 1}
          </span>
          <span>{text}</span>
        </div>
      ))}
      {gitlabUrl && (
        <a
          href={gitlabUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 bg-violet-500/10 text-violet-600 border border-violet-500/20 px-3.5 py-2 rounded-lg font-semibold text-[13px] hover:bg-violet-500/20 transition-colors mx-auto mt-1"
        >
          {gitlabUrl} <ArrowUpRight size={13} />
        </a>
      )}
    </div>
  );
}

// ─── Modal Wrapper ───────────────────────────────────────────────────────────
function Modal({ onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/70 z-[1000] flex items-center justify-center p-5 backdrop-blur-md" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-2xl p-7 max-w-[480px] w-full shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

export default function GitLabPanel({ boardId, canManage = false }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [accountStatus, setAccountStatus] = useState(null);
  const [gitlabProject, setGitlabProject] = useState(null);
  const [members, setMembers] = useState([]);
  const [commits, setCommits] = useState([]);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');

  const [showLinkModal, setShowLinkModal] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAddMemberModal, setShowAddMemberModal] = useState(false);

  const [tokenInput, setTokenInput] = useState('');
  const [tokenVerified, setTokenVerified] = useState(null);
  const [tokenError, setTokenError] = useState('');
  const [verifiedInfo, setVerifiedInfo] = useState(null);
  const [repoName, setRepoName] = useState('');
  const [repoVisibility, setRepoVisibility] = useState('private');
  const [newMemberUsername, setNewMemberUsername] = useState('');
  const [newMemberLevel, setNewMemberLevel] = useState(30);
  const [actionLoading, setActionLoading] = useState(false);
  const [gitlabUrl, setGitlabUrl] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState(null);

  const loadGitLabConfig = useCallback(async () => {
    try {
      const res = await getGitLabConfig();
      if (res.data.success && res.data.gitlab_url) {
        setGitlabUrl(res.data.gitlab_url);
      }
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load GitLab config:', err);
    }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [statusRes, projectRes] = await Promise.all([
        getGitLabAccountStatus(),
        getBoardGitLabInfo(boardId),
      ]);
      setAccountStatus(statusRes.data);
      if (projectRes.data.success && projectRes.data.data) {
        setGitlabProject(projectRes.data.data);
        loadProjectData(boardId);
      }
    } catch (err) {
      setError('Failed to load GitLab data');
    } finally {
      setLoading(false);
    }
  }, [boardId]);

  useEffect(() => {
    loadData();
    loadGitLabConfig();
  }, [loadData, loadGitLabConfig]);

  const loadProjectData = async (bid) => {
    try {
      const [membersRes, statsRes] = await Promise.all([
        getBoardMembers(bid),
        getBoardCommitStats(bid),
      ]);
      setMembers(membersRes.data.data || []);
      setStats(statsRes.data.data || null);
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load project data:', err);
    }
  };

  const loadCommits = async (bid, page = 1) => {
    try {
      const res = await getBoardCommits(bid, { page, limit: 20 });
      setCommits(res.data.data || []);
    } catch (err) {
      if (import.meta.env.DEV) console.error('Failed to load commits:', err);
    }
  };

  const handleVerifyToken = async () => {
    if (!tokenInput.trim()) return;
    setActionLoading(true);
    setTokenVerified(null);
    setTokenError('');
    try {
      const res = await verifyGitLabToken(tokenInput.trim());
      setTokenVerified(true);
      setVerifiedInfo(res.data);
    } catch (err) {
      setTokenVerified(false);
      setTokenError(
        err.isSessionExpired || err.response?.status === 401
          ? 'Your login session expired. Please sign in again and retry.'
          : err.response?.data?.message || 'Invalid Token. Please check and try again.'
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleLinkAccount = async () => {
    setActionLoading(true);
    try {
      const res = await linkGitLabAccount(tokenInput.trim());
      setAccountStatus({ is_linked: true, data: res.data.data });
      setShowLinkModal(false);
      setTokenInput('');
      setTokenVerified(null);
      setTokenError('');
      setVerifiedInfo(null);
      loadData();
    } catch (err) {
      setError(err.response?.data?.message || 'فشل ربط الحساب');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateRepo = async () => {
    setActionLoading(true);
    setError('');
    try {
      const res = await createGitLabProject(boardId, {
        project_name: repoName || undefined,
        visibility: repoVisibility,
      });
      setGitlabProject(res.data.data);
      setShowCreateModal(false);
      setRepoName('');
      setRepoVisibility('private');
      loadProjectData(boardId);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to create repository');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddMember = async () => {
    if (!newMemberUsername.trim()) return;
    setActionLoading(true);
    setError('');
    try {
      await addBoardMember(boardId, newMemberUsername.trim(), newMemberLevel);
      setShowAddMemberModal(false);
      setNewMemberUsername('');
      const res = await getBoardMembers(boardId);
      setMembers(res.data.data || []);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to add member');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveMember = async (gitlabUserId) => {
    if (!window.confirm('Are you sure you want to remove this member?')) return;
    setError('');
    try {
      await removeBoardMember(boardId, gitlabUserId);
      const res = await getBoardMembers(boardId);
      setMembers(res.data.data || []);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to remove member');
    }
  };

  const handleSyncCommits = async () => {
    setError('');
    setSyncing(true);
    try {
      const res = await syncCommits(boardId);
      const activity = res.data?.data || {};
      setGitlabProject((current) => current ? { ...current, ...activity } : current);
      await Promise.all([loadCommits(boardId), loadProjectData(boardId)]);
      const rawMessage = res.data?.message || 'تمت مزامنة بيانات المستودع بنجاح.';
      const countMatch = String(rawMessage).match(/(\d+)\s*(?:new\s*)?commits?/i);
      const newCommits = countMatch ? Number(countMatch[1]) : null;
      setSyncNotice({
        type: 'success',
        title: 'تمت المزامنة بنجاح',
        message: newCommits === null
          ? rawMessage
          : `تم العثور على ${newCommits} تحديث${newCommits === 1 ? ' جديد' : 'ات جديدة'}، وتم تحديث إحصائيات المستودع.`,
      });
      window.setTimeout(() => setSyncNotice(null), 4500);
    } catch (err) {
      const message = err.response?.data?.message || 'تعذرت مزامنة بيانات المستودع. يرجى المحاولة مرة أخرى.';
      setError(message);
      setSyncNotice({ type: 'error', title: 'فشلت المزامنة', message });
      window.setTimeout(() => setSyncNotice(null), 5000);
    } finally {
      setSyncing(false);
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'commits' && gitlabProject) {
      loadCommits(boardId);
    }
  };

  const handleOpenGitLab = (projectUrl) => {
    if (!projectUrl) {
      setError('رابط مستودع GitLab غير متوفر. جرّب مزامنة بيانات المستودع أولًا.');
      return;
    }

    // افتح المستودع مباشرة مع الحفاظ على جلسة GitLab الحالية.
    // تسجيل الخروج قبل الفتح كان يجعل المستودعات الخاصة تظهر كصفحة 404.
    window.open(projectUrl, '_blank', 'noopener,noreferrer');
  };

  // ── Loading ──
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <div className="w-10 h-10 border-[3px] border-violet-500/20 border-t-violet-500 rounded-full animate-spin" />
        <p className="text-[15px] text-gray-500 dark:text-gray-400 m-0">Loading GitLab data...</p>
      </div>
    );
  }

  // ── Error Alert ──
  const ErrorAlert = () => error ? (
    <div className="flex items-center gap-2 py-2.5 px-3.5 bg-red-500/10 border border-red-500/20 rounded-lg text-[13px] text-red-600 mb-4">
      <AlertCircle size={14} />
      {error}
    </div>
  ) : null;

  // ── No GitLab Project ──
  if (!gitlabProject) {
    return (
      <div className="max-w-[960px] mx-auto p-5">
        <ErrorAlert />

        <div className="flex flex-col items-center justify-center py-16 px-6 bg-white dark:bg-gray-800 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-600 text-center">
          <div className="w-16 h-16 rounded-2xl bg-violet-500/10 flex items-center justify-center mb-4">
            <GitBranch size={28} className="text-violet-500" />
          </div>
          <h3 className="text-[18px] font-bold text-gray-900 dark:text-white m-0 mb-2">No GitLab repository linked</h3>
          <p className="text-[14px] text-gray-500 dark:text-gray-400 m-0 mb-6 max-w-[380px]">Create a GitLab repository to track code and collaborate with your team</p>

          {!accountStatus?.is_linked ? (
            <button className="inline-flex items-center gap-2 py-2.5 px-5 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all shadow-sm" onClick={() => setShowLinkModal(true)}>
              <Link2 size={15} /> Link GitLab Account
            </button>
          ) : (
            <button className="inline-flex items-center gap-2 py-2.5 px-5 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all shadow-sm" onClick={() => setShowCreateModal(true)}>
              <Plus size={15} /> Create New Repository
            </button>
          )}
        </div>

        {accountStatus?.is_linked && (
          <div className="mt-4 py-2.5 px-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-[13px] text-emerald-700 flex items-center gap-2">
            <CheckCircle2 size={14} />
            <span className="font-semibold">Linked</span>
            <span>— {accountStatus.data.gitlab_username}</span>
          </div>
        )}

        {/* Link Modal */}
        {showLinkModal && (
          <Modal onClose={() => setShowLinkModal(false)}>
            <h3 className="text-[18px] font-bold text-gray-900 dark:text-white m-0 mb-3 flex items-center gap-2">
              <Link2 size={20} className="text-violet-500" /> Link GitLab Account
            </h3>
            <p className="text-[13px] text-gray-500 dark:text-gray-400 m-0 mb-3">Enter your Personal Access Token from the university GitLab.</p>
            <TokenSteps gitlabUrl={gitlabUrl} />

            <div className="mt-4 flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Personal Access Token</label>
              <input
                type="password"
                autoComplete="new-password"
                className="w-full py-2.5 px-3 text-sm border-[1.5px] border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none"
                value={tokenInput}
                onChange={(e) => { setTokenInput(e.target.value); setTokenVerified(null); setTokenError(''); }}
                placeholder="glpat-..."
              />
              <button
                className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors disabled:opacity-50"
                onClick={handleVerifyToken}
                disabled={!tokenInput.trim() || actionLoading}
              >
                {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />}
                {actionLoading ? 'Verifying...' : 'Verify'}
              </button>
            </div>

            {tokenVerified && verifiedInfo && (
              <div className="mt-3 py-3 px-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                <p className="text-[13px] text-emerald-700 m-0 mb-1 flex items-center gap-1.5 font-semibold">
                  <CheckCircle2 size={14} /> Token is valid
                </p>
                <p className="text-[13px] text-emerald-700 m-0 mb-3">
                  User: <strong>{verifiedInfo.username}</strong> ({verifiedInfo.name})
                </p>
                <button className="inline-flex items-center gap-1.5 py-2 px-4 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all" onClick={handleLinkAccount}>
                  Link Account
                </button>
              </div>
            )}

            {tokenVerified === false && (
              <div className="mt-3 py-3 px-4 bg-red-500/10 border border-red-500/20 rounded-lg text-[13px] text-red-600 flex items-center gap-1.5">
                <XCircle size={14} /> {tokenError || 'Invalid Token. Please check and try again.'}
              </div>
            )}

            <button className="mt-4 inline-flex items-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onClick={() => setShowLinkModal(false)}>Cancel</button>
          </Modal>
        )}

        {/* Create Repo Modal */}
        {showCreateModal && (
          <Modal onClose={() => setShowCreateModal(false)}>
            <h3 className="text-[18px] font-bold text-gray-900 dark:text-white m-0 mb-3 flex items-center gap-2">
              <Plus size={20} className="text-violet-500" /> Create New Repository
            </h3>
            <p className="text-[13px] text-gray-500 dark:text-gray-400 m-0 mb-4">
              A GitLab repository will be created and linked to this project.
              {gitlabUrl && (
                <> You can open GitLab from{' '}
                  <a href={gitlabUrl} target="_blank" rel="noopener noreferrer" className="text-violet-600 hover:underline font-semibold">{gitlabUrl} ↗</a>
                </>
              )}
            </p>

            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Repository Name (optional)</label>
                <input type="text" className="w-full py-2.5 px-3 text-sm border-[1.5px] border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none" value={repoName} onChange={(e) => setRepoName(e.target.value)} placeholder="Project name will be used if left empty" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[12px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Repository Visibility</label>
                <select className="w-full py-2.5 px-3 text-sm border-[1.5px] border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none" value={repoVisibility} onChange={(e) => setRepoVisibility(e.target.value)}>
                  <option value="private">Private</option>
                  <option value="internal">Internal</option>
                  <option value="public">Public</option>
                </select>
              </div>
            </div>

            {error && (
              <div className="mt-3 py-2.5 px-3.5 bg-red-500/10 border border-red-500/20 rounded-lg text-[13px] text-red-600">{error}</div>
            )}

            <div className="mt-5 flex gap-2 justify-end">
              <button className="inline-flex items-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onClick={() => setShowCreateModal(false)}>Cancel</button>
              <button className="inline-flex items-center gap-1.5 py-2 px-5 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all disabled:opacity-50" onClick={handleCreateRepo} disabled={actionLoading}>
                {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                {actionLoading ? 'Creating...' : 'Create Repository'}
              </button>
            </div>
          </Modal>
        )}
      </div>
    );
  }

  // ── GitLab Project Exists ──
  const TAB_ITEMS = [
    { key: 'overview', label: 'نظرة عامة', icon: BarChart3 },
    { key: 'commits', label: 'التحديثات', icon: FileCode },
    { key: 'members', label: 'الأعضاء', icon: Users },
  ];

  const visibilityLabel = { private: 'خاص', internal: 'داخلي', public: 'عام' };
  const repositoryUrl = gitlabProject.web_url || gitlabUrl;
  const totalChanges = (stats?.total_lines_added || 0) + (stats?.total_lines_removed || 0);
  const authorMax = Math.max(...((stats?.authors || []).map((author) => author.commit_count || 0)), 1);

  return (
    <div className="w-full max-w-[1320px] mx-auto px-4 sm:px-6 py-5" dir="rtl">
      {syncNotice && (
        <div className="fixed top-24 right-6 z-[1400] w-[calc(100%-3rem)] max-w-[680px]" role="status" aria-live="polite">
          <div
            className={`relative overflow-hidden rounded-2xl border shadow-[0_18px_55px_rgba(15,23,42,0.18)] ${syncNotice.type === 'success' ? 'border-emerald-200' : 'border-rose-200'}`}
            style={{ backgroundColor: '#ffffff', opacity: 1 }}
          >
            <div className={`absolute inset-y-0 right-0 w-1.5 ${syncNotice.type === 'success' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <div className="flex items-center gap-4 px-5 py-4 pr-7">
              <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full ${syncNotice.type === 'success' ? 'bg-emerald-100 text-emerald-600' : 'bg-rose-100 text-rose-600'}`}>
                {syncNotice.type === 'success' ? <CheckCircle2 size={30} /> : <AlertCircle size={30} />}
              </div>
              <div className="min-w-0 flex-1">
                <h4 className="m-0 text-[17px] font-black" style={{ color: '#111827', opacity: 1 }}>{syncNotice.title}</h4>
                <p className="mb-0 mt-1 text-[14px] leading-7" style={{ color: '#4b5563', opacity: 1 }}>{syncNotice.message}</p>
                {syncNotice.type === 'success' && (
                  <p className="mb-0 mt-0.5 text-[13px] font-medium" style={{ color: '#059669', opacity: 1 }}>تمت مزامنة بيانات المستودع بنجاح.</p>
                )}
              </div>
              <button type="button" onClick={() => setSyncNotice(null)} className="self-start rounded-full p-2 text-emerald-700 transition-colors hover:bg-emerald-100" aria-label="إغلاق الإشعار">
                <X size={18} />
              </button>
            </div>
          </div>
        </div>
      )}

      <ErrorAlert />

      <section className="mb-5 rounded-3xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border border-violet-100 bg-white shadow-sm">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-orange-400 via-orange-500 to-rose-500 text-white shadow-md">
                <GitBranch size={29} />
              </div>
            </div>
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-700">
                  {gitlabProject.visibility === 'private' ? <Lock size={12} /> : <Globe size={12} />}
                  {visibilityLabel[gitlabProject.visibility] || gitlabProject.visibility}
                </span>
              </div>
              <h3 className="m-0 truncate text-xl font-black text-gray-950 dark:text-white sm:text-2xl" dir="ltr">
                {gitlabProject.project_name || gitlabProject.gitlab_project_path}
              </h3>
              <p className="mt-1 truncate text-sm font-medium text-violet-600" dir="ltr">{gitlabProject.gitlab_project_path}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-600 dark:text-gray-300">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1.5"><GitBranch size={13} /> الفرع: <strong dir="ltr">{gitlabProject.default_branch || 'main'}</strong></span>
                {accountStatus?.is_linked && <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1.5"><Users size={13} /> الحساب: <strong dir="ltr">{accountStatus.data.gitlab_username}</strong></span>}
                <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1.5"><Clock3 size={13} /> آخر مزامنة: منذ لحظات</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 lg:justify-end">
            <button onClick={() => handleOpenGitLab(repositoryUrl)} className="inline-flex items-center gap-2 rounded-xl border border-violet-500 bg-white px-5 py-3 text-sm font-bold text-violet-700 transition-all hover:bg-violet-50">
              <ExternalLink size={16} /> فتح في GitLab
            </button>
            <button onClick={handleSyncCommits} disabled={syncing} className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-5 py-3 text-sm font-bold text-white shadow-md shadow-violet-600/20 transition-all hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-70">
              {syncing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              {syncing ? 'جارٍ المزامنة...' : 'مزامنة الآن'}
            </button>
          </div>
        </div>
      </section>

      <div className="mb-5 flex max-w-full items-center gap-7 overflow-x-auto border-b border-gray-200 dark:border-gray-700">
        {TAB_ITEMS.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button key={tab.key} onClick={() => handleTabChange(tab.key)} className={`relative inline-flex min-w-max items-center gap-2 px-1 py-3.5 text-sm font-bold transition-colors ${activeTab === tab.key ? 'text-violet-700' : 'text-gray-500 hover:text-violet-600'}`}>
              <TabIcon size={17} /> {tab.label}
              {activeTab === tab.key && <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-violet-600" />}
            </button>
          );
        })}
      </div>

      <div className="min-h-[260px]">
        {activeTab === 'overview' && (
          <div>
            {stats && stats.has_gitlab_project ? (
              <>
                <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
                  {[
                    { value: stats.total_commits || 0, label: 'إجمالي Commits', icon: GitCommitHorizontal, cls: 'bg-violet-100 text-violet-600' },
                    { value: stats.total_authors || 0, label: 'المساهمون', icon: Users, cls: 'bg-blue-100 text-blue-600' },
                    { value: `+${stats.total_lines_added || 0}`, label: 'الأسطر المضافة', icon: Code2, cls: 'bg-emerald-100 text-emerald-600' },
                    { value: `-${stats.total_lines_removed || 0}`, label: 'الأسطر المحذوفة', icon: FileCode, cls: 'bg-rose-100 text-rose-600' },
                    { value: gitlabProject.branches_count || 1, label: 'الفروع', icon: GitBranch, cls: 'bg-violet-100 text-violet-600' },
                    { value: gitlabProject.open_merge_requests_count ?? gitlabProject.merge_requests_count ?? 0, label: 'طلبات الدمج المفتوحة', icon: Link2, cls: 'bg-orange-100 text-orange-600' },
                    { value: gitlabProject.open_issues_count || 0, label: 'المشكلات المفتوحة', icon: AlertCircle, cls: 'bg-amber-100 text-amber-600' },
                  ].map((item) => {
                    const ItemIcon = item.icon;
                    return (
                      <div key={item.label} className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md dark:border-gray-700 dark:bg-gray-800">
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <div className="text-2xl font-black text-gray-950 dark:text-white" dir="ltr">{item.value}</div>
                            <div className="mt-1 text-xs font-medium text-gray-500">{item.label}</div>
                          </div>
                          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${item.cls}`}><ItemIcon size={20} /></div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="mb-5 grid grid-cols-1 gap-5 xl:grid-cols-2">
                  <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
                    <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 dark:border-gray-700">
                      <h4 className="m-0 inline-flex items-center gap-2 text-base font-black text-gray-950 dark:text-white"><GitBranch size={18} className="text-violet-600" /> الفروع</h4>
                      <span className="rounded-full bg-violet-100 px-2.5 py-1 text-xs font-black text-violet-700">{gitlabProject.branches_count || 0}</span>
                    </div>
                    <div className="flex flex-wrap gap-2 p-5">
                      {gitlabProject.branches?.length ? gitlabProject.branches.map((branch) => (
                        <span key={branch.name} className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-2 text-xs font-bold ${branch.default ? 'border-violet-200 bg-violet-50 text-violet-700' : 'border-gray-200 bg-gray-50 text-gray-700 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200'}`}>
                          <GitBranch size={13} /> <span dir="ltr">{branch.name}</span>{branch.default && <span className="text-[10px]">افتراضي</span>}
                        </span>
                      )) : <p className="m-0 text-sm text-gray-500">لا توجد فروع ظاهرة.</p>}
                    </div>
                  </section>

                  <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
                    <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 dark:border-gray-700">
                      <h4 className="m-0 inline-flex items-center gap-2 text-base font-black text-gray-950 dark:text-white"><Link2 size={18} className="text-orange-600" /> طلبات الدمج</h4>
                      <span className="rounded-full bg-orange-100 px-2.5 py-1 text-xs font-black text-orange-700">{gitlabProject.open_merge_requests_count ?? 0} مفتوح</span>
                    </div>
                    <div className="divide-y divide-gray-100 dark:divide-gray-700">
                      {gitlabProject.merge_requests?.length ? gitlabProject.merge_requests.slice(0, 5).map((mr) => (
                        <a key={mr.iid} href={mr.web_url} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between gap-3 px-5 py-3.5 text-inherit no-underline transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-black text-gray-950 dark:text-white">!{mr.iid} {mr.title}</div>
                            <div className="mt-1 text-xs text-gray-500"><span dir="ltr">{mr.source_branch}</span> ← <span dir="ltr">{mr.target_branch}</span></div>
                          </div>
                          <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-black ${mr.state === 'opened' ? 'bg-emerald-100 text-emerald-700' : mr.state === 'merged' ? 'bg-violet-100 text-violet-700' : 'bg-gray-100 text-gray-600'}`}>{mr.state === 'opened' ? 'مفتوح' : mr.state === 'merged' ? 'مُدمج' : 'مغلق'}</span>
                        </a>
                      )) : <p className="m-0 p-5 text-sm text-gray-500">لا توجد طلبات دمج حتى الآن.</p>}
                    </div>
                  </section>
                </div>

                <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                  <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
                    <div className="border-b border-gray-100 px-5 py-4 dark:border-gray-700"><h4 className="m-0 text-lg font-black text-gray-950 dark:text-white">آخر Commit</h4></div>
                    {stats.last_commit ? (
                      <div className="p-5">
                        <div className="flex items-start gap-3">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-600"><CheckCircle2 size={18} /></div>
                          <div className="min-w-0 flex-1">
                            <h5 className="m-0 break-words text-base font-black text-gray-950 dark:text-white">{stats.last_commit.message}</h5>
                            <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-gray-500">
                              <span className="inline-flex items-center gap-2"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-600 font-bold text-white">{(stats.last_commit.author || '?').charAt(0).toUpperCase()}</span>{stats.last_commit.author}</span>
                              <span>{stats.last_commit.date ? new Date(stats.last_commit.date).toLocaleString('ar-SY') : '—'}</span>
                            </div>
                            <div className="mt-4 rounded-xl bg-gray-100 px-4 py-3 text-sm text-gray-700 dark:bg-gray-700 dark:text-gray-200">أحدث عملية تحديث محفوظة في مستودع المشروع.</div>
                            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                              <button onClick={() => handleOpenGitLab(repositoryUrl)} className="inline-flex items-center gap-2 rounded-lg border border-violet-500 px-4 py-2 text-sm font-bold text-violet-700 hover:bg-violet-50"><ExternalLink size={14} /> عرض في GitLab</button>
                              <code className="rounded-lg bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700" dir="ltr">{stats.last_commit.sha}</code>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : <p className="p-5 text-sm text-gray-500">لا توجد تحديثات بعد.</p>}
                  </section>

                  <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
                    <div className="border-b border-gray-100 px-5 py-4 dark:border-gray-700"><h4 className="m-0 text-lg font-black text-gray-950 dark:text-white">المساهمون</h4></div>
                    <div className="p-5">
                      {stats.authors && stats.authors.length > 0 ? stats.authors.map((author, index) => {
                        const percent = Math.round(((author.commit_count || 0) / authorMax) * 100);
                        return (
                          <div key={`${author.author_name}-${index}`} className="mb-4 last:mb-0">
                            <div className="mb-3 flex items-center gap-3">
                              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-violet-600 font-bold text-white">{(author.author_name || '?').trim().charAt(0).toUpperCase()}</div>
                              <div className="min-w-0 flex-1"><strong className="block truncate text-sm text-gray-950 dark:text-white">{author.author_name}</strong><span className="text-xs text-gray-500">{author.commit_count || 0} Commits</span></div>
                              <strong className="text-sm text-gray-950 dark:text-white">{percent}%</strong>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700"><div className="h-full rounded-full bg-violet-600" style={{ width: `${percent}%` }} /></div>
                          </div>
                        );
                      }) : <p className="m-0 text-sm text-gray-500">لا يوجد مساهمون حتى الآن.</p>}
                    </div>
                  </section>
                </div>

                <section className="mt-5 rounded-2xl border border-emerald-200 bg-gradient-to-l from-emerald-50 to-white p-5 shadow-sm dark:border-emerald-800/60 dark:from-emerald-950/30 dark:to-gray-800">
                  <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div className="flex items-center gap-4">
                      <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-600"><RefreshCw size={27} className={syncing ? 'animate-spin' : ''} /></div>
                      <div>
                        <h4 className="m-0 text-lg font-black text-gray-950 dark:text-white">مزامنة البيانات</h4>
                        <p className="mb-0 mt-1 text-sm leading-6 text-gray-600 dark:text-gray-300">حدّث بيانات التحديثات والمساهمين للحصول على أحدث إحصائيات المستودع.</p>
                      </div>
                    </div>
                    <div className="flex flex-col items-stretch gap-2 md:items-end">
                      <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600"><CheckCircle2 size={14} /> آخر مزامنة: منذ لحظات</span>
                      <button onClick={handleSyncCommits} disabled={syncing} className="inline-flex min-w-[180px] items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 text-sm font-black text-white shadow-sm transition-all hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-70">
                        {syncing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}{syncing ? 'جارٍ المزامنة...' : 'مزامنة الآن'}
                      </button>
                    </div>
                  </div>
                </section>
              </>
            ) : (
              <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-10 text-center dark:border-gray-700 dark:bg-gray-800"><BarChart3 size={34} className="mx-auto mb-3 text-violet-500" /><h4 className="m-0 font-bold text-gray-900 dark:text-white">لا توجد إحصائيات بعد</h4><p className="mb-0 mt-2 text-sm text-gray-500">ابدأ العمل على المشروع ثم قم بالمزامنة لإظهار النشاط.</p></div>
            )}
          </div>
        )}

        {activeTab === 'commits' && (
          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center justify-between border-b border-gray-100 p-5 dark:border-gray-700"><div><h4 className="m-0 font-bold text-gray-900 dark:text-white">سجل التحديثات</h4><p className="mb-0 mt-1 text-xs text-gray-400">آخر التغييرات المسجلة في المستودع</p></div><button onClick={handleSyncCommits} className="inline-flex items-center gap-2 rounded-lg bg-violet-50 px-3 py-2 text-sm font-semibold text-violet-600 hover:bg-violet-100"><RefreshCw size={14} /> تحديث</button></div>
            <div className="space-y-3 p-4">{commits.length === 0 ? <div className="py-12 text-center"><GitCommitHorizontal size={32} className="mx-auto mb-3 text-gray-300" /><p className="m-0 text-sm text-gray-500">لا توجد تحديثات بعد.</p></div> : commits.map((commit) => <div key={commit.id} className="rounded-xl border border-gray-100 p-4 transition-colors hover:border-violet-200 dark:border-gray-700"><div className="flex items-start gap-3"><code className="shrink-0 rounded-lg bg-violet-600 px-2.5 py-1 text-xs font-mono text-white" dir="ltr">{commit.short_sha}</code><div className="min-w-0 flex-1"><p className="m-0 break-words text-sm font-semibold text-gray-900 dark:text-white">{commit.short_message}</p><div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-400"><span>{commit.author_name}</span><span>{commit.authored_date ? new Date(commit.authored_date).toLocaleDateString('ar-SY') : ''}</span></div></div></div></div>)}</div>
          </div>
        )}

        {activeTab === 'members' && (
          <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-center justify-between border-b border-gray-100 p-5 dark:border-gray-700"><div><h4 className="m-0 font-bold text-gray-900 dark:text-white">أعضاء المستودع</h4><p className="mb-0 mt-1 text-xs text-gray-400">الأشخاص الذين لديهم صلاحية الوصول إلى المشروع</p></div>{canManage && <button onClick={() => setShowAddMemberModal(true)} className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-3 py-2 text-sm font-semibold text-white hover:bg-violet-700"><UserPlus size={14} /> إضافة عضو</button>}</div>
            <div className="grid grid-cols-1 gap-3 p-4 lg:grid-cols-2">{members.length === 0 ? <p className="col-span-full m-0 py-10 text-center text-sm text-gray-500">لا يوجد أعضاء بعد.</p> : members.map((member) => { const levelInfo = ACCESS_LEVELS[member.access_level] || { label: member.access_level, style: 'bg-gray-100 text-gray-500' }; return <div key={member.id} className="flex items-center gap-3 rounded-xl border border-gray-100 p-4 transition-colors hover:border-violet-200 dark:border-gray-700"><div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 font-bold text-white">{member.avatar_url ? <img src={member.avatar_url} alt={member.username} className="h-full w-full object-cover" /> : (member.name || member.username)[0].toUpperCase()}</div><div className="min-w-0"><strong className="block truncate text-sm text-gray-900 dark:text-white">{member.name}</strong><span className="text-xs text-gray-400" dir="ltr">@{member.username}</span></div><span className={`mr-auto rounded-full px-2.5 py-1 text-[11px] font-semibold ${levelInfo.style}`}>{levelInfo.label}</span>{canManage && member.access_level < 50 && <button className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500" onClick={() => handleRemoveMember(member.id)} title="إزالة العضو"><X size={15} /></button>}</div>; })}</div>
          </div>
        )}
      </div>

      {/* Link Account Modal */}
      {showLinkModal && (
        <Modal onClose={() => setShowLinkModal(false)}>
          <h3 className="text-[18px] font-bold text-gray-900 dark:text-white m-0 mb-3 flex items-center gap-2">
            <Link2 size={20} className="text-violet-500" /> Link GitLab Account
          </h3>
          <p className="text-[13px] text-gray-500 dark:text-gray-400 m-0 mb-3">Enter your Personal Access Token from the university GitLab.</p>
          <TokenSteps gitlabUrl={gitlabUrl} />

          <div className="mt-4 flex flex-col gap-1.5">
            <label className="text-[12px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Personal Access Token</label>
            <input type="password" className="w-full py-2.5 px-3 text-sm border-[1.5px] border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none" value={tokenInput} onChange={(e) => { setTokenInput(e.target.value); setTokenVerified(null); setTokenError(''); }} placeholder="glpat-..." />
            <button className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors disabled:opacity-50" onClick={handleVerifyToken} disabled={!tokenInput.trim() || actionLoading}>
              {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />}
              {actionLoading ? 'Verifying...' : 'Verify'}
            </button>
          </div>

          {tokenVerified && verifiedInfo && (
            <div className="mt-3 py-3 px-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
              <p className="text-[13px] text-emerald-700 m-0 mb-1 flex items-center gap-1.5 font-semibold"><CheckCircle2 size={14} /> Token is valid</p>
              <p className="text-[13px] text-emerald-700 m-0 mb-3">User: <strong>{verifiedInfo.username}</strong> ({verifiedInfo.name})</p>
              <button className="inline-flex items-center gap-1.5 py-2 px-4 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all" onClick={handleLinkAccount}>Link Account</button>
            </div>
          )}

          {tokenVerified === false && (
            <div className="mt-3 py-3 px-4 bg-red-500/10 border border-red-500/20 rounded-lg text-[13px] text-red-600 flex items-center gap-1.5">
              <XCircle size={14} /> {tokenError || 'Invalid Token. Please check and try again.'}
            </div>
          )}

          <button className="mt-4 inline-flex items-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onClick={() => setShowLinkModal(false)}>Cancel</button>
        </Modal>
      )}

      {/* Add Member Modal */}
      {showAddMemberModal && (
        <Modal onClose={() => setShowAddMemberModal(false)}>
          <h3 className="text-[18px] font-bold text-gray-900 dark:text-white m-0 mb-4 flex items-center gap-2">
            <UserPlus size={20} className="text-violet-500" /> Add Member
          </h3>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">GitLab Username</label>
              <input type="text" className="w-full py-2.5 px-3 text-sm border-[1.5px] border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none" value={newMemberUsername} onChange={(e) => setNewMemberUsername(e.target.value)} placeholder="gitlab_username" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-[12px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Access Level</label>
              <select className="w-full py-2.5 px-3 text-sm border-[1.5px] border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none" value={newMemberLevel} onChange={(e) => setNewMemberLevel(Number(e.target.value))}>
                <option value={10}>Guest</option>
                <option value={20}>Reporter</option>
                <option value={30}>Developer</option>
                <option value={40}>Maintainer</option>
              </select>
            </div>
          </div>
          <div className="mt-5 flex gap-2 justify-end">
            <button className="inline-flex items-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onClick={() => setShowAddMemberModal(false)}>Cancel</button>
            <button className="inline-flex items-center gap-1.5 py-2 px-5 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all disabled:opacity-50" onClick={handleAddMember} disabled={actionLoading}>
              {actionLoading ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
              {actionLoading ? 'Adding...' : 'Add'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
