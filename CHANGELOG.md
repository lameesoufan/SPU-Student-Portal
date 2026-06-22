# Changelog

## [Unreleased]

### Added
- **GitHub Repository Link**: Students can now add and manage a GitHub repository link directly from their project board.
  - Added a dynamic input UI in the student's `MyProject` view.
  - Supervisors, HoDs, and Deans can view the linked GitHub repository via quick-access links in their respective `SupervisorProjects` and `HodProjects` dashboards.
- **Project Classification Feature**: Introduced a required `project_type` classification across the system.
  - Three new types supported: `Seasonal`, `Graduation 1`, and `Graduation 2`.
- **Database Models**: 
  - Added `project_type` field to `ProjectIdea`, `StudentIdeaProposal`, and `IdeaApplication` models.
  - Updated API Serializers to correctly parse and expose the `project_type`.
- **Frontend Submission**:
  - `SubmitIdea.jsx` now requires Doctor/Faculty to specify the Project Type.
  - `ProposeIdea.jsx` now requires Student to specify the Project Type when submitting custom proposals.
  - `BrowseIdeas.jsx` Apply modal now prompts the student to specify their intended Project Type when applying to an existing idea.
- **Frontend UI/UX Enhancements**:
  - Implemented sleek badges to display Project Types dynamically across views:
    - **Student View**: Highlighted in `BrowseIdeas` on idea cards.
    - **Doctor View**: Displayed in `MyIdeas` dashboard.
    - **HoD View**: Displayed in `HodIdeaReview`, `HodApplicationReview`, and `HodProjects`.
    - **Supervisor View**: Displayed in `SupervisorReview` and `SupervisorProjects`.
- **Notification Integration**:
  - Notifications dynamically extract and format the project type, so stakeholders immediately know whether a new request is for a Seasonal or Graduation project.

### Changed
- **Services/Business Logic**: 
  - Modified `create_project_idea`, `create_student_proposal`, and `apply_on_idea` to securely save the `project_type`.
- **API Serializers**: 
  - Updated `ProjectBoardSerializer` to expose the parent proposal/application `project_type` so the Kanban board can render it seamlessly.

### Fixed
- Fixed missing project classification constraints preventing clear boundaries between short-term seasonal tasks and official graduation projects.
