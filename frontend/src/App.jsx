import React, { useState, useEffect } from 'react';
import usePageHistory from './hooks/usePageHistory';
import './index.css';
import UploadReference from './components/UploadReference';
import { logoutUser, clearAccessToken, fetchCurrentUser } from './api';
import Login from './components/Login';
import SelfRegister from './components/SelfRegister';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import ImportUsers from './components/ImportUsers';
import StudentDashboard from './components/StudentDashboard';
import DoctorDashboard from './components/DoctorDashboard';
import HodDashboard from './components/HodDashboard';
import DeanDashboard from './components/DeanDashboard';
import AssignHod from './components/AssignHod';
import ChangePassword from './components/ChangePassword';
import ChangeUsername from './components/ChangeUsername';
import ForgotPassword from './components/ForgotPassword';


function AppInner() {
  const [user, setUser]     = useState(null);
  const [page, setPage, goBack] = usePageHistory('dashboard');
  const [screen, setScreen] = useState('login'); // login | register | forgot-password
  const [bootstrapped, setBootstrapped] = useState(false);

  // ── Restore session on app mount ──
  // If the HttpOnly JWT cookies are still valid, fetch the current user
  // from the backend so the user is not bounced to the login screen on
  // every page refresh.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchCurrentUser();
        if (!cancelled && res.data) {
          setUser(res.data);
        }
      } catch {
        // Not authenticated — that's fine, stay on the login screen.
      } finally {
        if (!cancelled) setBootstrapped(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleLogin      = (u) => { setUser(u); setPage('dashboard'); setScreen('login'); };
  const handleRegistered = (u) => { setUser(u); setPage('dashboard'); };
  const handlePasswordChanged = () => setUser({ ...user, must_change_password: false });
  const handleUsernameChanged = (newUsername) => setUser({ ...user, username: newUsername, must_change_username: false });
  const handleLogout = async () => {
    try { await logoutUser(); } catch { /* proceed */ }
    clearAccessToken();  // ← مسح الـ token من الذاكرة
    setUser(null);
    setScreen('login');
    setPage('dashboard');
  };



  // Show a minimal loader while we check if the session is still valid.
  if (!bootstrapped) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
      </div>
    );
  }

  if (!user) {
    if (screen === 'forgot-password')
      return <ForgotPassword onBack={() => setScreen('login')} />;
    if (screen === 'register')
      return <SelfRegister onRegistered={handleRegistered} onBack={() => setScreen('login')} />;
    return <Login onLogin={handleLogin} onRegister={() => setScreen('register')} onForgotPassword={() => setScreen('forgot-password')} />;
  }

  if (user.must_change_password)
    return <ChangePassword user={user} onSuccess={handlePasswordChanged} />;

  // Imported doctors choose a permanent username after completing the
  // mandatory first-login password change. HoDs are included because an
  // imported doctor may be promoted before their first login.
  if (user.must_change_username && ['doctor', 'hod'].includes(user.role))
    return <ChangeUsername user={user} onSuccess={handleUsernameChanged} />;

  if (user.role === 'student') return <StudentDashboard user={user} onLogout={handleLogout} />;
  if (user.role === 'doctor')  return <DoctorDashboard  user={user} onLogout={handleLogout} />;
  if (user.role === 'hod')     return <HodDashboard     user={user} onLogout={handleLogout} />;
  if (user.role === 'dean')    return <DeanDashboard    user={user} onLogout={handleLogout} />;

  // Fallback for admin and unknown roles
  const canImport = user.role === 'admin' || user.role === 'dean';
  const isAdmin = user.role === 'admin';

  return (
    <div>
      <Navbar user={user} onLogout={handleLogout} currentPage={page} />
      <div className="app-layout" style={{ display: 'flex', minHeight: 'calc(100vh - 64px)' }}>
        <main style={{ flex: 1, background: 'var(--bg-primary)', overflow: 'auto' }}>
          {page === 'dashboard'       && <Dashboard user={user} onNavigate={setPage} />}
          {page === 'import'          && canImport && <ImportUsers onBack={goBack} />}
          {page === 'assign-hod'      && canImport && <AssignHod onBack={goBack} />}
          {page === 'upload-reference' && isAdmin   && <UploadReference onBack={goBack} />}
          {!['dashboard','import','assign-hod','upload-reference'].includes(page) && (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <h2>Page Not Found</h2>
              <p>The page you requested does not exist or you don't have access.</p>
              <button onClick={() => setPage('dashboard')} style={{ marginTop: '1rem', cursor: 'pointer' }}>Back to Dashboard</button>
            </div>
          )}
        </main>

        <aside className="sidebar-container" role="navigation" aria-label="Sidebar">
          <nav className="sidebar-nav">
            <SidebarItem
              icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>}
              label="Dashboard"
              active={page === 'dashboard'}
              onClick={() => setPage('dashboard')}
            />
            {canImport && (
              <SidebarItem
                icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>}
                label="Import Users"
                active={page === 'import'}
                onClick={() => setPage('import')}
              />
            )}
            {canImport && (
              <SidebarItem
                icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>}
                label="Assign HoD"
                active={page === 'assign-hod'}
                onClick={() => setPage('assign-hod')}
              />
            )}
            {isAdmin && (
              <SidebarItem
                icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>}
                label="Upload Reference"
                active={page === 'upload-reference'}
                onClick={() => setPage('upload-reference')}
              />
            )}
          </nav>
        </aside>
      </div>
    </div>
  );
}

function SidebarItem({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`sidebar-item ${active ? 'active' : ''}`}
      aria-current={active ? 'page' : undefined}
    >
      <span aria-hidden="true" className="sidebar-item-icon">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

export default function App() {
  return <AppInner />;
}