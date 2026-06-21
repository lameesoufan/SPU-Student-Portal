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
    try {
      const res = await syncCommits(boardId);
      loadCommits(boardId);
      loadProjectData(boardId);
      alert(res.data.message);
    } catch (err) {
      setError(err.response?.data?.message || 'Sync failed');
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === 'commits' && gitlabProject) {
      loadCommits(boardId);
    }
  };

  const handleOpenGitLab = (projectUrl) => {
    if (!gitlabUrl) {
      window.open(projectUrl, '_blank');
      return;
    }
    const logoutUrl = `${gitlabUrl}/users/sign_out`;
    const newWindow = window.open(logoutUrl, '_blank');
    if (newWindow) {
      setTimeout(() => {
        try {
          newWindow.location.href = projectUrl;
        } catch {
          window.open(projectUrl, '_blank');
        }
      }, 1500);
    } else {
      window.open(projectUrl, '_blank');
    }
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
    { key: 'overview', label: 'Overview', icon: BarChart3 },
    { key: 'commits', label: 'Commits', icon: FileCode },
    { key: 'members', label: 'Members', icon: Users },
  ];

  return (
    <div className="max-w-[960px] mx-auto p-5">
      <ErrorAlert />

      {/* Header */}
      <div className="flex justify-between items-center mb-4 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h3 className="text-[18px] font-bold text-gray-900 dark:text-white m-0 flex items-center gap-2">
            <GitBranch size={20} className="text-violet-500" />
            {gitlabProject.project_name || gitlabProject.gitlab_project_path}
          </h3>
          <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full uppercase ${VISIBILITY_STYLES[gitlabProject.visibility] || 'bg-gray-100 dark:bg-gray-700 text-gray-500'}`}>
            {gitlabProject.visibility}
          </span>
        </div>
        <div className="flex gap-2 items-center">
          <button onClick={() => handleOpenGitLab(gitlabUrl)} className="inline-flex items-center gap-1.5 py-2 px-3.5 text-[13px] font-semibold rounded-lg bg-violet-500/10 text-violet-600 border border-violet-500/20 hover:bg-violet-500/20 transition-colors">
            <ExternalLink size={13} /> Open in GitLab
          </button>
          <button className="inline-flex items-center gap-1.5 py-2 px-3 text-[13px] font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onClick={handleSyncCommits}>
            <RefreshCw size={13} /> Sync
          </button>
          {canManage && (
            <button className="inline-flex items-center gap-1.5 py-2 px-3 text-[13px] font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onClick={() => setShowAddMemberModal(true)}>
              <UserPlus size={13} /> Add Member
            </button>
          )}
        </div>
      </div>

      {/* Account Bar */}
      <div className="mb-4 py-2.5 px-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-[13px] flex items-center gap-2">
        {accountStatus?.is_linked ? (
          <span className="text-gray-900 dark:text-white">
            <span className="inline-flex items-center gap-1 bg-emerald-500 text-white px-2 py-0.5 rounded-full text-[11px] font-semibold mr-1.5">
              <CheckCircle2 size={10} /> Linked
            </span>
            to: <strong>{accountStatus.data.gitlab_username}</strong>
          </span>
        ) : (
          <span className="text-amber-600 flex items-center gap-1.5">
            <AlertCircle size={13} /> Your account is not linked to GitLab —
            <button className="text-violet-600 underline font-semibold bg-transparent border-none cursor-pointer text-[13px] p-0" onClick={() => setShowLinkModal(true)}>Link Account</button>
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b-2 border-gray-200 dark:border-gray-700 mb-5">
        {TAB_ITEMS.map(t => {
          const TabIcon = t.icon;
          return (
            <button key={t.key} className={`py-2.5 px-5 border-none bg-transparent text-[14px] font-medium cursor-pointer border-b-2 transition-all flex items-center gap-1.5 mb-[-2px] ${
              activeTab === t.key ? 'text-violet-600 border-b-violet-600 font-semibold' : 'text-gray-500 dark:text-gray-400 border-b-transparent hover:text-violet-600'
            }`} onClick={() => handleTabChange(t.key)}>
              <TabIcon size={15} /> {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="min-h-[200px]">
        {/* Overview */}
        {activeTab === 'overview' && (
          <div>
            {stats && stats.has_gitlab_project ? (
              <>
                <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-3 mb-6">
                  {[
                    { value: stats.total_commits, label: 'Total Commits', color: 'text-violet-600' },
                    { value: stats.total_authors, label: 'Contributors', color: 'text-blue-600' },
                    { value: `+${stats.total_lines_added}`, label: 'Lines Added', color: 'text-emerald-600' },
                    { value: `-${stats.total_lines_removed}`, label: 'Lines Removed', color: 'text-red-500' },
                  ].map((stat, i) => (
                    <div key={i} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 text-center">
                      <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
                      <div className="text-[12px] text-gray-500 dark:text-gray-400 mt-1">{stat.label}</div>
                    </div>
                  ))}
                </div>

                {stats.last_commit && (
                  <div className="mb-6">
                    <h4 className="text-[14px] text-gray-500 dark:text-gray-400 m-0 mb-2.5 font-semibold">Latest Commit</h4>
                    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <code className="bg-violet-600 text-white px-2 py-0.5 rounded text-[12px] font-mono">{stats.last_commit.sha}</code>
                        <span className="text-[13px] text-gray-900 dark:text-white">{stats.last_commit.message}</span>
                      </div>
                      <span className="block text-[12px] text-gray-400 mt-2">
                        {stats.last_commit.author} — {stats.last_commit.date ? new Date(stats.last_commit.date).toLocaleDateString('en-US') : ''}
                      </span>
                    </div>
                  </div>
                )}

                {stats.authors && stats.authors.length > 0 && (
                  <div>
                    <h4 className="text-[14px] text-gray-500 dark:text-gray-400 m-0 mb-2.5 font-semibold">Contributors</h4>
                    {stats.authors.map((a, i) => (
                      <div key={i} className="flex items-center gap-3 py-2 px-3 border-b border-gray-100 dark:border-gray-700/50 last:border-b-0">
                        <span className="text-[13px] font-semibold text-gray-900 dark:text-white min-w-[120px]">{a.author_name}</span>
                        <span className="text-[13px] text-gray-500 dark:text-gray-400">{a.commit_count} commits</span>
                        <div className="ml-auto flex gap-3 text-[13px] font-semibold">
                          <span className="text-emerald-600">+{a.added || 0}</span>
                          <span className="text-red-500">-{a.removed || 0}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <p className="text-gray-500 dark:text-gray-400 text-[14px]">No statistics yet. Start working on the project!</p>
            )}
          </div>
        )}

        {/* Commits */}
        {activeTab === 'commits' && (
          <div className="flex flex-col gap-2">
            {commits.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center">
                <p className="text-gray-500 dark:text-gray-400 text-[14px] mb-4">No commits yet</p>
                <button className="inline-flex items-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onClick={handleSyncCommits}>
                  <RefreshCw size={13} /> Sync from GitLab
                </button>
              </div>
            ) : (
              commits.map((commit) => (
                <div key={commit.id} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <code className="bg-violet-600 text-white px-2 py-0.5 rounded text-[12px] font-mono flex-shrink-0">{commit.short_sha}</code>
                    <span className="text-[13px] text-gray-900 dark:text-white truncate">{commit.short_message}</span>
                  </div>
                  <div className="flex gap-4 text-[12px] text-gray-400 items-center">
                    <span>{commit.author_name}</span>
                    <span>{commit.authored_date ? new Date(commit.authored_date).toLocaleDateString('en-US') : ''}</span>
                    <div className="ml-auto flex gap-3 font-semibold">
                      <span className="text-emerald-600">+{commit.added_lines}</span>
                      <span className="text-red-500">-{commit.removed_lines}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Members */}
        {activeTab === 'members' && (
          <div className="flex flex-col gap-2">
            {members.length === 0 ? (
              <p className="text-gray-500 dark:text-gray-400 text-[14px]">No members yet</p>
            ) : (
              members.map((member) => {
                const levelInfo = ACCESS_LEVELS[member.access_level] || { label: member.access_level, style: 'bg-gray-100 dark:bg-gray-700 text-gray-500' };
                return (
                  <div key={member.id} className="flex items-center gap-3 py-2.5 px-3.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white font-semibold text-[14px] flex-shrink-0 overflow-hidden">
                      {member.avatar_url ? (
                        <img src={member.avatar_url} alt={member.username} className="w-full h-full object-cover" />
                      ) : (
                        (member.name || member.username)[0].toUpperCase()
                      )}
                    </div>
                    <div className="flex flex-col">
                      <strong className="text-[14px] text-gray-900 dark:text-white">{member.name}</strong>
                      <span className="text-[12px] text-gray-400">@{member.username}</span>
                    </div>
                    <span className={`ml-auto text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${levelInfo.style}`}>
                      {levelInfo.label}
                    </span>
                    {canManage && member.access_level < 50 && (
                      <button className="p-1.5 rounded bg-transparent border-none cursor-pointer text-gray-400 hover:bg-red-500/10 hover:text-red-500 transition-colors" onClick={() => handleRemoveMember(member.id)}>
                        <X size={14} />
                      </button>
                    )}
                  </div>
                );
              })
            )}
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
