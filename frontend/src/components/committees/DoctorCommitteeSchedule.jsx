import React, { useState, useEffect, useCallback } from 'react';
import { Calendar, Clock, MapPin, Users, FileText, Inbox, Loader } from 'lucide-react';
import { fetchMyCommitteeSchedule } from '../../api';
import './DoctorCommitteeSchedule.css';

export default function DoctorCommitteeSchedule({ onBack }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchMyCommitteeSchedule();
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'تعذّر تحميل جدول المناقشات.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="dcs-loading">
        <Loader size={28} style={{ animation: 'spin 1s linear infinite' }} />
        <p style={{ marginTop: 10 }}>جاري التحميل...</p>
      </div>
    );
  }

  const committees = data?.committees || [];

  return (
    <div className="dcs-wrap" dir="rtl">
      <div className="dcs-header">
        <FileText size={24} color="#667eea" />
        <div>
          <div className="dcs-title">جدول المناقشات</div>
          <div className="dcs-subtitle">
            اللجان المسندة إليك ({committees.length} لجنة)
          </div>
        </div>
      </div>

      {error && <div className="dcs-error">{error}</div>}

      {committees.length === 0 && !error && (
        <div className="dcs-empty">
          <Inbox size={48} />
          <p>لا توجد لجان مسندة إليك حالياً.</p>
        </div>
      )}

      {committees.map((c) => (
        <CommitteeCard key={c.id} committee={c} />
      ))}
    </div>
  );
}

function CommitteeCard({ committee: c }) {
  const isScheduled = c.date && c.start_time;

  return (
    <div className="dcs-committee-card">
      {/* Header */}
      <div className="dcs-committee-head">
        <span className="dcs-committee-name">
          {c.committee_type_ar} — {c.department_ar} — {c.project_type_ar}
        </span>
        <span className={`dcs-badge ${c.my_role === 'chair' ? 'is-chair' : ''}`}>
          {c.my_role_ar}
        </span>
        {isScheduled && (
          <span className="dcs-badge is-scheduled">مجدول</span>
        )}
        {c.semester && (
          <span className="dcs-badge">{c.semester}</span>
        )}
      </div>

      {/* Meta: date / time / location */}
      <div className="dcs-meta">
        {c.date ? (
          <span className="dcs-meta-item">
            <Calendar size={13} /> {c.date}
          </span>
        ) : (
          <span className="dcs-meta-item" style={{ color: '#bbb' }}>
            <Calendar size={13} /> لم يُحدَّد التاريخ
          </span>
        )}
        {c.start_time && c.end_time && (
          <span className="dcs-meta-item">
            <Clock size={13} /> {c.start_time} – {c.end_time}
          </span>
        )}
        {c.location && (
          <span className="dcs-meta-item">
            <MapPin size={13} /> {c.location}
          </span>
        )}
        {c.discussion_duration && (
          <span className="dcs-meta-item">
            <Clock size={13} /> مدة المناقشة: {c.discussion_duration} دقيقة
          </span>
        )}
      </div>

      {/* Members */}
      {c.doctors && c.doctors.length > 0 && (
        <div className="dcs-members">
          <Users size={13} />
          <span className="dcs-members-label">أعضاء اللجنة:</span>
          {c.doctors.map((d, i) => (
            <span
              key={i}
              className={`dcs-member-chip ${d.role === 'chair' ? 'is-chair' : ''}`}
            >
              {d.role === 'chair' ? '👑 ' : ''}{d.name}
            </span>
          ))}
        </div>
      )}

      {/* Projects */}
      <div className="dcs-projects">
        <div className="dcs-projects-title">
          المشاريع ({c.projects_count})
        </div>
        {c.projects.length === 0 ? (
          <div style={{ padding: '12px 18px', color: '#aaa', fontSize: '0.83rem' }}>
            لا توجد مشاريع مسندة لهذه اللجنة بعد.
          </div>
        ) : (
          c.projects.map((p, idx) => (
            <div key={`${p.source}-${p.id}`} className="dcs-project-row">
              <div className="dcs-project-idx">{idx + 1}</div>
              <div className="dcs-project-info">
                <div className="dcs-project-title">{p.title || `مشروع #${p.id}`}</div>
                {p.students?.length > 0 && (
                  <div className="dcs-project-students">
                    طلاب: {p.students.map((s) => s.name + (s.is_leader ? ' ★' : '')).join('، ')}
                  </div>
                )}
                {p.supervisors?.length > 0 && (
                  <div className="dcs-project-supervisors">
                    المشرف: {p.supervisors.join('، ')}
                  </div>
                )}
              </div>
              {p.scheduled_start && p.scheduled_end ? (
                <div className="dcs-project-time">
                  {p.scheduled_start} – {p.scheduled_end}
                </div>
              ) : (
                <div className="dcs-project-time" style={{ color: '#bbb' }}>
                  —
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
