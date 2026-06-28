import React, { useState, useEffect } from 'react';
import {
  ArrowRight, Search, Download, Users, FileText,
  Calendar, MapPin, User, RefreshCw, AlertTriangle, Repeat, X,
} from 'lucide-react';
import { fetchProjectsAssignment, exportProjectsAssignment, fetchAvailableCommitteesForSwap, swapProject } from '../../api';
import './ProjectsAssignment.css';

/**
 * ProjectsAssignment - جدول توزيع المشاريع على اللجان
 * يعرض: الطالب، المشروع، اللجنة، التاريخ، المكان
 */
export default function ProjectsAssignment({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('all'); // all, seminar_1, seminar_2, technical, final_discussion
  const [exporting, setExporting] = useState(false);
  
  // Swap modal state
  const [swapModal, setSwapModal] = useState(null); // { project, committee, availableCommittees }
  const [swapping, setSwapping] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchProjectsAssignment();
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'فشل تحميل البيانات');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const res = await exportProjectsAssignment();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `projects_assignment_${new Date().toISOString().slice(0,10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('فشل تصدير الملف. حاول مرة أخرى.');
    } finally {
      setExporting(false);
    }
  };

  const handleSwapClick = async (project) => {
    try {
      const res = await fetchAvailableCommitteesForSwap(
        project.committee_id,
        project.project_source,
        project.project_id
      );
      setSwapModal({
        project,
        currentCommittee: res.data.current_committee,
        availableCommittees: res.data.available_committees || [],
      });
    } catch (err) {
      setError('فشل تحميل اللجان المتاحة');
    }
  };

  const handleSwapConfirm = async (toCommitteeId) => {
    if (!swapModal || swapping) return;
    setSwapping(true);
    try {
      await swapProject(swapModal.project.committee_id, {
        source: swapModal.project.project_source,
        project_id: swapModal.project.project_id,
        to_committee_id: toCommitteeId,
      });
      setSwapModal(null);
      await loadData(); // Reload data
    } catch (err) {
      setError('فشل نقل المشروع. حاول مرة أخرى.');
    } finally {
      setSwapping(false);
    }
  };

  // Filter data
  const filteredProjects = data?.projects?.filter((p) => {
    const matchesSearch = 
      !searchTerm ||
      // Search in all team members
      p.students?.some(s => s.name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
      p.project_title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      // Search in all supervisors
      p.supervisors?.some(s => s.name?.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesType = 
      filterType === 'all' || p.committee_type === filterType;

    return matchesSearch && matchesType;
  }) || [];

  if (loading) {
    return (
      <div className="pa-loading">
        <div className="pa-spinner" />
        <p>جارٍ تحميل توزيع المشاريع...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pa-page">
        <button className="pa-back-btn" onClick={onBack}>
          <ArrowRight size={16} /> رجوع
        </button>
        <div className="pa-error">
          <AlertTriangle size={20} />
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="pa-page">
      {/* Header */}
      <div className="pa-header">
        <div className="pa-header-left">
          <button className="pa-back-btn" onClick={onBack}>
            <ArrowRight size={16} /> رجوع
          </button>
          <div>
            <h1 className="pa-title">جدول توزيع المشاريع على اللجان</h1>
            <p className="pa-subtitle">
              عرض شامل لجميع المشاريع الموزعة مع تفاصيل اللجان والطلاب
            </p>
          </div>
        </div>
        <div className="pa-header-right">
          <button 
            className="pa-export-btn" 
            onClick={handleExport}
            disabled={exporting}
          >
            <Download size={16} />
            {exporting ? 'جارٍ التصدير...' : 'تصدير Excel'}
          </button>
          <div className="pa-stat-badge">
            <FileText size={16} />
            <span>{data?.total_projects || 0} مشروع موزع</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="pa-filters">
        <div className="pa-search">
          <Search size={18} />
          <input
            type="text"
            placeholder="ابحث بالطالب، المشروع، أو المشرف..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="pa-filter-tabs">
          <button
            className={`pa-tab ${filterType === 'all' ? 'active' : ''}`}
            onClick={() => setFilterType('all')}
          >
            الكل ({data?.total_projects || 0})
          </button>
          <button
            className={`pa-tab ${filterType === 'seminar_1' ? 'active' : ''}`}
            onClick={() => setFilterType('seminar_1')}
          >
            سيمينار 1
          </button>
          <button
            className={`pa-tab ${filterType === 'seminar_2' ? 'active' : ''}`}
            onClick={() => setFilterType('seminar_2')}
          >
            سيمينار 2
          </button>
          <button
            className={`pa-tab ${filterType === 'technical' ? 'active' : ''}`}
            onClick={() => setFilterType('technical')}
          >
            لجنة فنية
          </button>
          <button
            className={`pa-tab ${filterType === 'final_discussion' ? 'active' : ''}`}
            onClick={() => setFilterType('final_discussion')}
          >
            مناقشة نهائية
          </button>
        </div>

        <button className="pa-refresh-btn" onClick={loadData}>
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Table */}
      {filteredProjects.length === 0 ? (
        <div className="pa-empty">
          <FileText size={48} />
          <h3>لا توجد مشاريع</h3>
          <p>لم يتم توزيع أي مشاريع بعد أو لا توجد نتائج للبحث</p>
        </div>
      ) : (
        <div className="pa-table-container">
          <table className="pa-table">
            <thead>
              <tr>
                <th>#</th>
                <th>الطلاب</th>
                <th>المشروع</th>
                <th>المشرفين</th>
                <th>اللجنة</th>
                <th>نوع اللجنة</th>
                <th>القسم</th>
                <th>أعضاء اللجنة</th>
                <th>التاريخ</th>
                <th>الوقت</th>
                <th>المكان</th>
                <th>الإجراءات</th>
              </tr>
            </thead>
            <tbody>
              {filteredProjects.map((project, index) => (
                <tr key={`${project.committee_id}-${project.project_id}-${index}`}>
                  <td>{index + 1}</td>
                  <td>
                    <div className="pa-students-cell">
                      {project.students && project.students.length > 0 ? (
                        project.students.map((student, idx) => (
                          <div key={idx} className="pa-student-item">
                            <span className={`pa-student-badge ${student.is_leader ? 'pa-student-leader' : 'pa-student-member'}`}>
                              {student.is_leader ? '👤' : '•'} {student.name}
                            </span>
                          </div>
                        ))
                      ) : (
                        <span>—</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <div className="pa-project-cell">
                      <span className="pa-project-title">{project.project_title}</span>
                      <span className="pa-project-source">{project.project_source}</span>
                    </div>
                  </td>
                  <td>
                    <div className="pa-supervisors-cell">
                      {project.supervisors && project.supervisors.length > 0 ? (
                        project.supervisors.map((supervisor, idx) => (
                          <div key={idx} className="pa-supervisor-item">
                            <span className={`pa-supervisor-badge ${supervisor.is_main ? 'pa-supervisor-main' : 'pa-supervisor-co'}`}>
                              {supervisor.is_main ? '👤' : '•'} {supervisor.name}
                            </span>
                          </div>
                        ))
                      ) : (
                        <span>—</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className="pa-committee-name">{project.committee_name}</span>
                  </td>
                  <td>
                    <span className={`pa-badge pa-badge-${project.committee_type}`}>
                      {project.committee_type_ar}
                    </span>
                  </td>
                  <td>
                    <span className={`pa-badge pa-badge-dept`}>
                      {project.department_ar}
                    </span>
                  </td>
                  <td>
                    <div className="pa-members-cell">
                      {project.committee_members && project.committee_members.length > 0 ? (
                        project.committee_members.map((member, idx) => (
                          <div key={idx} className="pa-member-item">
                            <span className={`pa-member-badge ${member.role === 'chair' ? 'pa-member-chair' : 'pa-member-regular'}`}>
                              {member.role === 'chair' ? '👤' : '•'} {member.name}
                            </span>
                          </div>
                        ))
                      ) : '—'}
                    </div>
                  </td>
                  <td>
                    {project.date ? (
                      <div className="pa-date-cell">
                        <Calendar size={13} />
                        <span>{project.date}</span>
                      </div>
                    ) : '—'}
                  </td>
                  <td>
                    {project.time || '—'}
                  </td>
                  <td>
                    {project.location ? (
                      <div className="pa-location-cell">
                        <MapPin size={13} />
                        <span>{project.location}</span>
                      </div>
                    ) : '—'}
                  </td>
                  <td>
                    <button
                      className="pa-swap-btn"
                      onClick={() => handleSwapClick(project)}
                      title="استبدال اللجنة"
                    >
                      <Repeat size={14} />
                      استبدال
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Swap Modal */}
      {swapModal && (
        <>
          <div className="pa-modal-backdrop" onClick={() => !swapping && setSwapModal(null)} />
          <div className="pa-swap-modal">
            <div className="pa-modal-header">
              <h3>استبدال اللجنة</h3>
              <button
                className="pa-modal-close"
                onClick={() => !swapping && setSwapModal(null)}
                disabled={swapping}
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="pa-modal-body">
              <div className="pa-project-info">
                <h4>{swapModal.project.project_title}</h4>
                <p className="pa-current-committee">
                  اللجنة الحالية: <strong>{swapModal.currentCommittee.name}</strong>
                </p>
              </div>

              <div className="pa-available-list">
                <h4>اللجان المتاحة:</h4>
                {swapModal.availableCommittees.length === 0 ? (
                  <p className="pa-no-committees">لا توجد لجان متاحة للنقل</p>
                ) : (
                  swapModal.availableCommittees.map((committee) => (
                    <div key={committee.id} className="pa-committee-card">
                      <div className="pa-committee-card-header">
                        <h5>{committee.name}</h5>
                        <span className="pa-projects-badge">
                          {committee.projects_count} مشروع
                        </span>
                      </div>
                      
                      <div className="pa-committee-card-body">
                        <div className="pa-committee-info-row">
                          <User size={14} />
                          <span>الرئيس: {committee.chair}</span>
                        </div>
                        {committee.members.length > 0 && (
                          <div className="pa-committee-info-row">
                            <Users size={14} />
                            <span>الأعضاء: {committee.members.join('، ')}</span>
                          </div>
                        )}
                        {committee.date && (
                          <div className="pa-committee-info-row">
                            <Calendar size={14} />
                            <span>{committee.date} {committee.time && `- ${committee.time}`}</span>
                          </div>
                        )}
                        {committee.location && (
                          <div className="pa-committee-info-row">
                            <MapPin size={14} />
                            <span>{committee.location}</span>
                          </div>
                        )}
                      </div>

                      <button
                        className="pa-select-committee-btn"
                        onClick={() => handleSwapConfirm(committee.id)}
                        disabled={swapping}
                      >
                        {swapping ? 'جارٍ النقل...' : 'نقل إلى هذه اللجنة'}
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Footer Info */}
      <div className="pa-footer">
        <p>عدد المشاريع المعروضة: <strong>{filteredProjects.length}</strong></p>
        <p>آخر تحديث: {new Date().toLocaleString('ar-SY')}</p>
      </div>
    </div>
  );
}
