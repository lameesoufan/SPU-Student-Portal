import React, { useState, useEffect } from 'react';
import {
  ArrowRight, Search, Download, Users, FileText,
  Calendar, MapPin, User, RefreshCw, AlertTriangle, Repeat, X,
  Save, Edit3, Check, Clock,
} from 'lucide-react';
import { fetchProjectsAssignment, exportProjectsAssignment, fetchAvailableCommitteesForSwap, swapProject, updateProjectSchedules } from '../../api';
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
  const [bulkValues, setBulkValues] = useState({ date: '', time: '', location: '' });
  const [saving, setSaving] = useState(false);

  // Individual edits
  const [editedProjects, setEditedProjects] = useState({});

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
      setError(err.response?.data?.detail || 'Failed to load data');
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
      setError('Export failed. Try again.');
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
      setError('Failed to load available committees');
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
      setError('Failed to transfer project. Try again.');
    } finally {
      setSwapping(false);
    }
  };

  // Selection handlers
  const toggleSelectAll = () => {
    if (selectedRows.size === filteredProjects.length) {
      setSelectedRows(new Set());
    } else {
      setSelectedRows(new Set(filteredProjects.map((_, idx) => idx)));
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
      setError('Please select at least one project');
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
        ...(bulkValues.time && { time: bulkValues.time }),
        ...(bulkValues.location && { location: bulkValues.location }),
      };
    });
    setEditedProjects(newEdited);
    setBulkEditModal(false);
    setBulkValues({ date: '', time: '', location: '' });
  };

  const saveChanges = async () => {
    if (Object.keys(editedProjects).length === 0) {
      setError('No changes to save');
      return;
    }
    
    setSaving(true);
    try {
      // Prepare updates array
      const updates = Object.entries(editedProjects).map(([index, values]) => {
        const project = filteredProjects[parseInt(index)];
        return {
          committee_id: project.committee_id,
          project_source: project.project_source,
          project_id: project.project_id,
          ...values
        };
      });

      await updateProjectSchedules(updates);
      
      setEditMode(false);
      setEditedProjects({});
      setSelectedRows(new Set());
      setError(''); // Clear any previous errors
      await loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save changes. Please try again.');
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
        <p>Loading project distribution...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="pa-page">
        <button className="pa-back-btn" onClick={onBack}>
          <ArrowRight size={16} /> Back
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
            <ArrowRight size={16} /> Back
          </button>
          <div>
            <h1 className="pa-title">Projects Distribution Table</h1>
            <p className="pa-subtitle">
              Comprehensive view of all distributed projects with committee and student details
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
                {saving ? 'Saving...' : `Save Changes (${Object.keys(editedProjects).length})`}
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
                Cancel
              </button>
            </>
          ) : (
            <button 
              className="pa-btn pa-btn-primary" 
              onClick={() => setEditMode(true)}
            >
              <Edit3 size={16} />
              Edit Schedule
            </button>
          )}
          <button 
            className="pa-export-btn" 
            onClick={handleExport}
            disabled={exporting}
          >
            <Download size={16} />
            {exporting ? 'Exporting...' : 'Export Excel'}
          </button>
          <div className="pa-stat-badge">
            <FileText size={16} />
            <span>{data?.total_projects || 0} distributed projects</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="pa-filters">
        <div className="pa-search">
          <Search size={18} />
          <input
            type="text"
            placeholder="Search by student, project, or supervisor..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="pa-filter-tabs">
          <button
            className={`pa-tab ${filterType === 'all' ? 'active' : ''}`}
            onClick={() => setFilterType('all')}
          >
            All ({data?.total_projects || 0})
          </button>
          <button
            className={`pa-tab ${filterType === 'seminar_1' ? 'active' : ''}`}
            onClick={() => setFilterType('seminar_1')}
          >
            Seminar 1
          </button>
          <button
            className={`pa-tab ${filterType === 'seminar_2' ? 'active' : ''}`}
            onClick={() => setFilterType('seminar_2')}
          >
            Seminar 2
          </button>
          <button
            className={`pa-tab ${filterType === 'technical' ? 'active' : ''}`}
            onClick={() => setFilterType('technical')}
          >
            Technical Committee
          </button>
          <button
            className={`pa-tab ${filterType === 'final_discussion' ? 'active' : ''}`}
            onClick={() => setFilterType('final_discussion')}
          >
            Final Discussion
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
            Edit Selected
          </button>
          <button className="pa-btn pa-btn-secondary" onClick={() => setSelectedRows(new Set())}>
            Clear Selection
          </button>
        </div>
      )}

      {/* Table */}
      {filteredProjects.length === 0 ? (
        <div className="pa-empty">
          <FileText size={48} />
          <h3>No projects</h3>
          <p>No projects have been distributed yet or no search results</p>
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
                      checked={selectedRows.size === filteredProjects.length && filteredProjects.length > 0}
                      onChange={toggleSelectAll}
                    />
                  </th>
                )}
                <th>#</th>
                <th>Students</th>
                <th>Project</th>
                <th>Supervisors</th>
                <th>Committee</th>
                <th>Committee Type</th>
                <th>Department</th>
                <th>Committee Members</th>
                <th>Date</th>
                <th>Time</th>
                <th>Location</th>
                {!editMode && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {filteredProjects.map((project, index) => {
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
                          value={getDisplayValue(index, project, 'date')}
                          onChange={(e) => handleEditChange(index, 'date', e.target.value)}
                        />
                      ) : (
                        getDisplayValue(index, project, 'date') ? (
                          <div className="pa-date-cell">
                            <Calendar size={13} />
                            <span>{getDisplayValue(index, project, 'date')}</span>
                          </div>
                        ) : '—'
                      )}
                    </td>
                    <td>
                      {editMode ? (
                        <input
                          type="time"
                          className="pa-inline-input"
                          value={getDisplayValue(index, project, 'time')}
                          onChange={(e) => handleEditChange(index, 'time', e.target.value)}
                        />
                      ) : (
                        getDisplayValue(index, project, 'time') || '—'
                      )}
                    </td>
                    <td>
                      {editMode ? (
                        <input
                          type="text"
                          className="pa-inline-input"
                          placeholder="Enter location..."
                          value={getDisplayValue(index, project, 'location')}
                          onChange={(e) => handleEditChange(index, 'location', e.target.value)}
                        />
                      ) : (
                        getDisplayValue(index, project, 'location') ? (
                          <div className="pa-location-cell">
                            <MapPin size={13} />
                            <span>{getDisplayValue(index, project, 'location')}</span>
                          </div>
                        ) : '—'
                      )}
                    </td>
                    {!editMode && (
                      <td>
                        <button
                          className="pa-swap-btn"
                          onClick={() => handleSwapClick(project)}
                          title="Swap committee"
                        >
                          <Repeat size={14} />
                          Swap
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
              <h3>Swap Committee</h3>
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
                  Current committee: <strong>{swapModal.currentCommittee.name}</strong>
                </p>
              </div>

              <div className="pa-available-list">
                <h4>Available committees:</h4>
                {swapModal.availableCommittees.length === 0 ? (
                  <p className="pa-no-committees">No committees available for transfer</p>
                ) : (
                  swapModal.availableCommittees.map((committee) => (
                    <div key={committee.id} className="pa-committee-card">
                      <div className="pa-committee-card-header">
                        <h5>{committee.name}</h5>
                        <span className="pa-projects-badge">
                          {committee.projects_count} projects
                        </span>
                      </div>
                      
                      <div className="pa-committee-card-body">
                        <div className="pa-committee-info-row">
                          <User size={14} />
                          <span>Chair: {committee.chair ? (committee.chair.full_name || committee.chair.username || `#${committee.chair.id}`) : '—'}</span>
                        </div>
                        {committee.members.length > 0 && (
                          <div className="pa-committee-info-row">
                            <Users size={14} />
                            <span>Members: {committee.members.map(m => m.full_name || m.username).join(', ')}</span>
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
                        {swapping ? 'Transferring...' : 'Transfer to this committee'}
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
              <h3>Bulk Edit Schedule</h3>
              <button className="pa-modal-close" onClick={() => setBulkEditModal(false)}>
                <X size={20} />
              </button>
            </div>
            
            <div className="pa-modal-body">
              <p className="pa-modal-description">
                Apply the following changes to <strong>{selectedRows.size}</strong> selected project{selectedRows.size > 1 ? 's' : ''}:
              </p>

              <div className="pa-form-group">
                <label>
                  <Calendar size={16} />
                  Date
                </label>
                <input
                  type="date"
                  className="pa-form-input"
                  value={bulkValues.date}
                  onChange={(e) => setBulkValues(prev => ({ ...prev, date: e.target.value }))}
                />
                <small>Leave empty to keep existing values</small>
              </div>

              <div className="pa-form-group">
                <label>
                  <Clock size={16} />
                  Time
                </label>
                <input
                  type="time"
                  className="pa-form-input"
                  value={bulkValues.time}
                  onChange={(e) => setBulkValues(prev => ({ ...prev, time: e.target.value }))}
                />
                <small>Leave empty to keep existing values</small>
              </div>

              <div className="pa-form-group">
                <label>
                  <MapPin size={16} />
                  Location
                </label>
                <input
                  type="text"
                  className="pa-form-input"
                  placeholder="Enter location (e.g. Room 301, Building A)"
                  value={bulkValues.location}
                  onChange={(e) => setBulkValues(prev => ({ ...prev, location: e.target.value }))}
                />
                <small>Leave empty to keep existing values</small>
              </div>

              <div className="pa-modal-footer">
                <button className="pa-btn pa-btn-secondary" onClick={() => setBulkEditModal(false)}>
                  Cancel
                </button>
                <button 
                  className="pa-btn pa-btn-primary" 
                  onClick={applyBulkEdit}
                  disabled={!bulkValues.date && !bulkValues.time && !bulkValues.location}
                >
                  <Check size={16} />
                  Apply to {selectedRows.size} Project{selectedRows.size > 1 ? 's' : ''}
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Footer Info */}
      <div className="pa-footer">
        <p>Number of displayed projects: <strong>{filteredProjects.length}</strong></p>
        <p>Last updated: {new Date().toLocaleString('en-US')}</p>
      </div>
    </div>
  );
}
