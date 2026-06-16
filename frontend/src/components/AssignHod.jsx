import React, { useEffect, useState } from 'react';
import { fetchDoctors, fetchDepartments, assignHod } from '../api';

const DEPT_LABELS = {
  software_engineering:   'Software Engineering',
  artificial_intelligence:'Artificial Intelligence',
  information_security:   'Information Security',
  communications:         'Communications',
  control_robotics:       'Control & Robotics',
};

/* SVG Icons */
const Icons = {
  Building: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/></svg>,
  UserCheck: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><polyline points="17 11 19 13 23 9"/></svg>,
  User: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
  
  // Department Icons
  software_engineering: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>,
  artificial_intelligence: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>,
  information_security: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><circle cx="12" cy="11" r="3"/></svg>,
  communications: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></svg>,
  control_robotics: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  ArrowLeft: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
};

export default function AssignHod({ onBack }) {
  const [departments, setDepartments] = useState([]);
  const [doctors, setDoctors]         = useState([]);
  const [search, setSearch]           = useState('');
  const [selected, setSelected]       = useState({ dept: null, doctorId: null });
  const [loading, setLoading]         = useState(false);
  const [message, setMessage]         = useState(null); // {type, text}

  useEffect(() => {
    fetchDepartments().then(r => setDepartments(r.data));
    fetchDoctors().then(r => setDoctors(r.data));
  }, []);

  const filtered = doctors.filter(d => {
    const name = `${d.first_name} ${d.last_name} ${d.username}`.toLowerCase();
    return name.includes(search.toLowerCase());
  });

  const handleAssign = async () => {
    if (!selected.dept || !selected.doctorId) return;
    setLoading(true);
    setMessage(null);
    try {
      const res = await assignHod(selected.doctorId, selected.dept);
      setMessage({ type: 'success', text: res.data.message });
      const updated = await fetchDepartments();
      setDepartments(updated.data);
      const updatedDocs = await fetchDoctors();
      setDoctors(updatedDocs.data);
      setSelected({ dept: null, doctorId: null });
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.error || 'Assignment failed.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="premium-dashboard">
      {onBack && (
        <button className="back-btn" onClick={onBack} aria-label="Back to dashboard">
          {Icons.ArrowLeft} Back to Dashboard
        </button>
      )}

      <div className="page-header">
        <h1>Assign Department Heads</h1>
        <p>Select a department and assign a qualified doctor to act as HoD.</p>
      </div>

      {message && (
        <div className={`alert ${message.type === 'success' ? 'alert-success' : 'alert-error'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-[1fr_1.5fr] gap-8 items-start max-[800px]:grid-cols-1">
        {/* Left Column: Departments */}
        <section className="flex flex-col gap-4">
          <h2 className="pd-section-title">1. Select Department</h2>
          <div className="flex flex-col gap-2.5" role="list">
            {departments.map(dept => (
              <div
                key={dept.key}
                className={`flex items-center gap-3.5 bg-white dark:bg-gray-800 border-[1.5px] border-gray-200 dark:border-gray-700 rounded-xl p-4 cursor-pointer transition-all duration-200 hover:bg-gray-50 dark:hover:bg-gray-700/50 hover:border-violet-500 hover:translate-x-1 focus-visible:outline focus-visible:outline-3 focus-visible:outline-violet-300 ${selected.dept === dept.key ? 'bg-violet-50 dark:bg-violet-900/20 border-violet-500 shadow-[0_4px_12px_rgba(124,58,237,0.15)]' : ''}`}
                role="listitem"
                onClick={() => setSelected(s => ({ ...s, dept: dept.key }))}
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && setSelected(s => ({ ...s, dept: dept.key }))}
              >
                <div className="w-11 h-11 flex items-center justify-center bg-gray-100 dark:bg-gray-700 rounded-lg text-violet-600 dark:text-violet-400 shrink-0">
                  {Icons[dept.key] || Icons.Building}
                </div>
                <div className="flex flex-col gap-[3px]">
                  <span className="text-sm font-bold text-gray-900 dark:text-white">{dept.label}</span>
                  {dept.hod ? (
                    <span className="text-[13px] text-emerald-600 dark:text-emerald-400 font-semibold">Current: {dept.hod.full_name}</span>
                  ) : (
                    <span className="text-[13px] text-gray-400 dark:text-gray-500 italic">No HoD assigned</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Right Column: Doctors */}
        <section className="flex flex-col gap-4">
          <h2 className="pd-section-title">
            2. Select Doctor
            {selected.dept && <span className="text-violet-600 dark:text-violet-400 font-bold text-sm"> for {DEPT_LABELS[selected.dept]}</span>}
          </h2>

          <div className="card rounded-2xl shadow-md border border-gray-200 dark:border-gray-700">
            <div className="card-body">
              <div className="form-group mb-4">
                <input
                  className="form-control text-[15px]"
                  type="search"
                  placeholder="Search faculty by name or ID…"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  disabled={!selected.dept}
                />
              </div>

              <div className={`max-h-[480px] overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-xl mb-6 bg-white dark:bg-gray-800 ${!selected.dept ? 'opacity-50 pointer-events-none' : ''}`} role="listbox">
                {(!selected.dept) && (
                  <div className="empty-state" style={{ padding: '40px 24px' }}>
                    <p>Please select a department first.</p>
                  </div>
                )}
                {selected.dept && filtered.length === 0 && (
                  <div className="empty-state" style={{ padding: '40px 24px' }}>
                    <p>No matching faculty found.</p>
                  </div>
                )}
                {selected.dept && filtered.map(doc => {
                  const fullName = `${doc.first_name} ${doc.last_name}`.trim() || doc.username;
                  const isHod = doc.role === 'hod';
                  return (
                    <div
                      key={doc.id}
                      className={`flex items-center gap-3.5 py-3.5 px-4 border-b border-gray-100 dark:border-gray-700 last:border-b-0 cursor-pointer transition-all duration-200 hover:bg-gray-50 dark:hover:bg-gray-700/50 ${selected.doctorId === doc.id ? 'bg-violet-50 dark:bg-violet-900/20' : ''}`}
                      onClick={() => setSelected(s => ({ ...s, doctorId: doc.id }))}
                    >
                      <div className="w-10 h-10 flex items-center justify-center bg-gray-100 dark:bg-gray-700 text-violet-600 dark:text-violet-400 rounded-full border border-gray-200 dark:border-gray-600 shrink-0">
                        {isHod ? Icons.UserCheck : Icons.User}
                      </div>
                      <div className="flex-1 flex flex-col gap-0.5">
                        <span className="text-sm font-bold text-gray-900 dark:text-white">{fullName}</span>
                        <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">ID: {doc.username}</span>
                      </div>
                      {isHod && (
                        <span className="badge badge-warning">
                          HoD · {DEPT_LABELS[doc.department] || doc.department}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>

              <button
                className="btn btn-primary btn-lg w-full mt-2"
                onClick={handleAssign}
                disabled={!selected.dept || !selected.doctorId || loading}
              >
                {loading ? 'Assigning…' : 'Confirm Assignment'}
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}