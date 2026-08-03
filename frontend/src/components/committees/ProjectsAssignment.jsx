import React, { useState, useEffect } from 'react';
import {
  ArrowRight, Search, Download, Users, FileText,
  Calendar, MapPin, User, RefreshCw, AlertTriangle, Repeat, X,
  Save, Edit3, Check, Clock,
} from 'lucide-react';
import { fetchProjectsAssignment, exportProjectsAssignment, fetchAvailableCommitteesForSwap, swapProject, updateProjectSchedules, fetchRooms } from '../../api';
import './ProjectsAssignment.css';

/**
 * ProjectsAssignment - Projects Distribution Table
 * Displays: Student, Project, Committee, Date, Location
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

  // Bulk edit state
  const [selectedRows, setSelectedRows] = useState(new Set());
  const [editMode, setEditMode] = useState(false);
  const [bulkEditModal, setBulkEditModal] = useState(false);
  const [bulkValues, setBulkValues] = useState({ date: '', start_time: '', room_id: '' });
  const [rooms, setRooms] = useState([]);
  const [saving, setSaving] = useState(false);

  // Individual edits
  const [editedProjects, setEditedProjects] = useState({});

  useEffect(() => {
    loadData();
    fetchRooms({ is_active: true })
      .then((res) => setRooms(Array.isArray(res.data) ? res.data : (res.data?.results || [])))
      .catch(() => setRooms([]));
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchProjectsAssignment();
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'تعذر تحميل البيانات');
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
      setError('فشل التصدير. حاول مرة أخرى.');
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
      setError('تعذر تحميل اللجان المتاحة');
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
      setError(
        err.response?.data?.detail
        || 'فشل نقل المشروع. حاول مرة أخرى.'
      );
    } finally {
      setSwapping(false);
    }
  };

  // Selection handlers
  const toggleSelectAll = () => {
    if (selectedRows.size === sortedProjects.length) {
      setSelectedRows(new Set());
    } else {
      setSelectedRows(new Set(sortedProjects.map((_, idx) => idx)));
    }
  };

  const toggleSelectRow = (index) => {
    const newSelected = new Set(selectedRows);
    if (newSelected.has(index)) {
      newSelected.delete(index);
    } else {
      newSelected.add(index);
    }
    setSelectedRows(newSelected);
  };

  // Edit handlers
  const handleEditChange = (index, field, value) => {
    setEditedProjects(prev => ({
      ...prev,
      [index]: {
        ...prev[index],
        [field]: value
      }
    }));
  };

  const handleBulkEdit = () => {
    if (selectedRows.size === 0) {
      setError('يرجى تحديد مشروع واحد على الأقل');
      return;
    }
    setBulkEditModal(true);
  };

  const applyBulkEdit = () => {
    const newEdited = { ...editedProjects };
    selectedRows.forEach(index => {
      newEdited[index] = {
        ...newEdited[index],
        ...(bulkValues.date && { date: bulkValues.date }),
        ...(bulkValues.start_time && { start_time: bulkValues.start_time }),
        ...(bulkValues.room_id && { room_id: Number(bulkValues.room_id) }),
      };
    });
    setEditedProjects(newEdited);
    setBulkEditModal(false);
    setBulkValues({ date: '', start_time: '', room_id: '' });
  };

  const saveChanges = async () => {
    if (Object.keys(editedProjects).length === 0) {
      setError('لا توجد تغييرات للحفظ');
      return;
    }
    
    setSaving(true);
    try {
      // Prepare updates array
      const updates = Object.entries(editedProjects).map(([index, values]) => {
        const project = sortedProjects[parseInt(index)];
        
        // Clean up discussion_duration - convert to integer or null
        const cleanedValues = { ...values };
        if ('discussion_duration' in cleanedValues) {
          cleanedValues.discussion_duration = cleanedValues.discussion_duration 
            ? parseInt(cleanedValues.discussion_duration) 
            : null;
        }
        
        return {
          committee_id: project.committee_id,
          project_source: project.project_source,
          project_id: project.project_id,
          ...cleanedValues
        };
      });

      await updateProjectSchedules(updates);
      
      setEditMode(false);
      setEditedProjects({});
      setSelectedRows(new Set());
      setError(''); // Clear any previous errors
      await loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'فشل حفظ التغييرات. يرجى المحاولة مرة أخرى.');
    } finally {
      setSaving(false);
    }
  };

  // Filter data
  const filteredProjects = data?.projects?.filter((p) => {
    const matchesSearch = 
      !searchTerm ||
      // Search in ACTIVE team members only
      p.active_students?.some(s => s.name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
      p.project_title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      // Search in all supervisors
      p.supervisors?.some(s => s.name?.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesType = 
      filterType === 'all' || p.committee_type === filterType;

    return matchesSearch && matchesType;
  }) || [];

  // Sort by date (nearest first), then by start time
  const sortedProjects = [...filteredProjects].sort((a, b) => {
    const dateA = a.scheduled_date || a.date || '9999';
    const dateB = b.scheduled_date || b.date || '9999';
    if (dateA !== dateB) return dateA.localeCompare(dateB);
    // Same date, sort by time
    const timeA = a.scheduled_start || a.start_time || '99:99';
    const timeB = b.scheduled_start || b.start_time || '99:99';
    return timeA.localeCompare(timeB);
  });

  // Get display value (edited or original)
  const getDisplayValue = (index, project, field) => {
    if (editedProjects[index]?.[field] !== undefined) {
      return editedProjects[index][field];
    }
    return project[field] || '';
  };

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
      <div className="pa-page" dir="rtl">
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
    <div className="pa-page" dir="rtl">
      {/* Header */}
      <div className="pa-header">
        <div className="pa-header-left">
          <button className="pa-back-btn" onClick={onBack}>
            <ArrowRight size={16} /> رجوع
          </button>
          <div>
            <h1 className="pa-title">جدول توزيع المشاريع</h1>
            <p className="pa-subtitle">
              عرض شامل لجميع المشاريع الموزعة مع تفاصيل اللجان والطلاب
            </p>
          </div>
        </div>
        <div className="pa-header-right">
          {editMode ? (
            <>
              <button 
                className="pa-btn pa-btn-success" 
                onClick={saveChanges}
                disabled={saving || Object.keys(editedProjects).length === 0}
              >
                <Save size={16} />
                {saving ? 'جارٍ الحفظ...' : `حفظ التغييرات (${Object.keys(editedProjects).length})`}
              </button>
              <button 
                className="pa-btn pa-btn-secondary" 
                onClick={() => {
                  setEditMode(false);
                  setEditedProjects({});
                  setSelectedRows(new Set());
                }}
                disabled={saving}
              >
                <X size={16} />
                إلغاء
              </button>
            </>
          ) : (
            <button 
              className="pa-btn pa-btn-primary" 
              onClick={() => setEditMode(true)}
            >
              <Edit3 size={16} />
              تعديل الجدول
            </button>
          )}
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
            <span>{data?.total_projects || 0} مشروع موزّع</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="pa-filters">
        <div className="pa-search">
          <Search size={18} />
          <input
            type="text"
            placeholder="ابحث باسم الطالب أو المشروع أو المشرف..."
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
            اللجنة الفنية
          </button>
          <button
            className={`pa-tab ${filterType === 'final_discussion' ? 'active' : ''}`}
            onClick={() => setFilterType('final_discussion')}
          >
            المناقشة النهائية
          </button>
        </div>

        <button className="pa-refresh-btn" onClick={loadData}>
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Bulk Actions Bar */}
      {editMode && selectedRows.size > 0 && (
        <div className="pa-bulk-actions">
          <span className="pa-bulk-selected">
            {selectedRows.size} project{selectedRows.size > 1 ? 's' : ''} selected
          </span>
          <button className="pa-btn pa-btn-primary" onClick={handleBulkEdit}>
            <Edit3 size={14} />
            تعديل المحدد
          </button>
          <button className="pa-btn pa-btn-secondary" onClick={() => setSelectedRows(new Set())}>
            إلغاء التحديد
          </button>
        </div>
      )}

      {/* Table */}
      {sortedProjects.length === 0 ? (
        <div className="pa-empty">
          <FileText size={48} />
          <h3>لا توجد مشاريع</h3>
          <p>لم يتم توزيع مشاريع بعد أو لا توجد نتائج بحث</p>
        </div>
      ) : (
        <div className="pa-table-container">
          <table className="pa-table">
            <thead>
              <tr>
                {editMode && (
                  <th style={{ width: '40px' }}>
                    <input
                      type="checkbox"
                      checked={selectedRows.size === sortedProjects.length && sortedProjects.length > 0}
                      onChange={toggleSelectAll}
                    />
                  </th>
                )}
                <th>#</th>
                <th>الطلاب</th>
                <th>المشروع</th>
                <th>المشرفون</th>
                <th>اللجنة</th>
                <th>نوع اللجنة</th>
                <th>القسم</th>
                <th>أعضاء اللجنة</th>
                <th>التاريخ</th>
                <th>وقت بداية المناقشة</th>
                <th>وقت نهاية المناقشة</th>
                <th>الموقع</th>
                {!editMode && <th>الإجراءات</th>}
              </tr>
            </thead>
            <tbody>
              {sortedProjects.map((project, index) => {
                const isSelected = selectedRows.has(index);
                const isEdited = editedProjects[index];
                
                return (
                  <tr key={`${project.committee_id}-${project.project_id}-${index}`} className={isEdited ? 'pa-row-edited' : ''}>
                    {editMode && (
                      <td>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectRow(index)}
                        />
                      </td>
                    )}
                    <td>{index + 1}</td>
                    <td>
                      <div className="pa-students-cell">
                        {project.active_students && project.active_students.length > 0 ? (
                          project.active_students.map((student, idx) => (
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
                      {editMode ? (
                        <input
                          type="date"
                          className="pa-inline-input"
                          value={editedProjects[index]?.date ?? project.scheduled_date ?? project.date ?? ''}
                          onChange={(e) => handleEditChange(index, 'date', e.target.value)}
                        />
                      ) : (
                        project.scheduled_date ? (
                          <div className="pa-date-cell">
                            <Calendar size={13} />
                            <span>{project.scheduled_date}</span>
                          </div>
                        ) : '—'
                      )}
                    </td>
                    <td className="pa-schedule-cell">
                      {editMode ? (
                        <input
                          type="time"
                          className="pa-inline-input"
                          value={editedProjects[index]?.start_time ?? project.scheduled_start ?? project.scheduled_start_time ?? ''}
                          onChange={(e) => handleEditChange(index, 'start_time', e.target.value)}
                        />
                      ) : (project.scheduled_start || project.scheduled_start_time || '—')}
                    </td>
                    <td className="pa-schedule-cell">
                      {project.scheduled_end || project.scheduled_end_time || '—'}
                    </td>
                    <td>
                      {editMode ? (
                        <select
                          className="pa-inline-input"
                          value={editedProjects[index]?.room_id ?? project.room_id ?? ''}
                          onChange={(e) => handleEditChange(index, 'room_id', e.target.value ? Number(e.target.value) : '')}
                        >
                          <option value="">اختر القاعة</option>
                          {rooms.map((room) => (
                            <option key={room.id} value={room.id}>{room.name}</option>
                          ))}
                        </select>
                      ) : (
                        project.room_name ? (
                          <div className="pa-location-cell" >
                            <MapPin size={13} />
                            <span>🚪 {project.room_name}</span>
                          </div>
                        ) : '—'
                      )}
                    </td>
                    {!editMode && (
                      <td>
                        <button
                          className="pa-swap-btn"
                          onClick={() => handleSwapClick(project)}
                          title="تبديل اللجنة"
                        >
                          <Repeat size={14} />
                          تبديل
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
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
              <h3>تبديل اللجنة</h3>
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
                          {committee.projects_count} مشاريع
                        </span>
                      </div>
                      
                      <div className="pa-committee-card-body">
                        <div className="pa-committee-info-row">
                          <User size={14} />
                          <span>الرئيس: {committee.chair ? (committee.chair.full_name || committee.chair.username || `#${committee.chair.id}`) : '—'}</span>
                        </div>
                        {committee.members.length > 0 && (
                          <div className="pa-committee-info-row">
                            <Users size={14} />
                            <span>الأعضاء: {committee.members.map(m => m.full_name || m.username).join(', ')}</span>
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

      {/* Bulk Edit Modal */}
      {bulkEditModal && (
        <>
          <div className="pa-modal-backdrop" onClick={() => setBulkEditModal(false)} />
          <div className="pa-bulk-edit-modal">
            <div className="pa-modal-header">
              <h3>تعديل الجدول جماعيًا</h3>
              <button className="pa-modal-close" onClick={() => setBulkEditModal(false)}>
                <X size={20} />
              </button>
            </div>
            
            <div className="pa-modal-body">
              <p className="pa-modal-description">
                تطبيق التغييرات التالية على <strong>{selectedRows.size}</strong> مشروع محدد:
              </p>

              <div className="pa-form-group">
                <label>
                  <Calendar size={16} />
                  التاريخ
                </label>
                <input
                  type="date"
                  className="pa-form-input"
                  value={bulkValues.date}
                  onChange={(e) => setBulkValues(prev => ({ ...prev, date: e.target.value }))}
                />
                <small>اترك الحقل فارغًا للإبقاء على القيم الحالية</small>
              </div>

              <div className="pa-form-group">
                <label>
                  <Clock size={16} />
                  الوقت
                </label>
                <input
                  type="time"
                  className="pa-form-input"
                  value={bulkValues.start_time}
                  onChange={(e) => setBulkValues(prev => ({ ...prev, start_time: e.target.value }))}
                />
                <small>اترك الحقل فارغًا للإبقاء على القيم الحالية</small>
              </div>

              <div className="pa-form-group">
                <label>
                  <MapPin size={16} />
                  الموقع
                </label>
                <select
                  className="pa-form-input"
                  value={bulkValues.room_id}
                  onChange={(e) => setBulkValues(prev => ({ ...prev, room_id: e.target.value }))}
                >
                  <option value="">الإبقاء على القاعة الحالية</option>
                  {rooms.map((room) => (
                    <option key={room.id} value={room.id}>{room.name}</option>
                  ))}
                </select>
                <small>اترك الحقل فارغًا للإبقاء على القيم الحالية</small>
              </div>

              <div className="pa-modal-footer">
                <button className="pa-btn pa-btn-secondary" onClick={() => setBulkEditModal(false)}>
                  إلغاء
                </button>
                <button 
                  className="pa-btn pa-btn-primary" 
                  onClick={applyBulkEdit}
                  disabled={!bulkValues.date && !bulkValues.start_time && !bulkValues.room_id}
                >
                  <Check size={16} />
                  تطبيق على {selectedRows.size} مشروع
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Footer Info */}
      <div className="pa-footer">
        <p>عدد المشاريع المعروضة: <strong>{sortedProjects.length}</strong></p>
        <p>آخر تحديث: {new Date().toLocaleString('ar-IQ')}</p>
      </div>
    </div>
  );
}
