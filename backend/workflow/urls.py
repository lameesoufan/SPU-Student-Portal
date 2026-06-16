from django.urls import path
from . import views

app_name = 'workflow'

urlpatterns = [
    # Workflow Templates Management
    path('templates/', views.list_workflow_templates, name='list_workflow_templates'),
    path('templates/<int:template_id>/', views.get_workflow_template, name='get_workflow_template'),
    path('templates/create/', views.create_workflow_template, name='create_workflow_template'),
    path('templates/<int:template_id>/update/', views.update_workflow_template, name='update_workflow_template'),
    path('templates/<int:template_id>/delete/', views.delete_workflow_template, name='delete_workflow_template'),
    
    # Apply Workflow to Project
    path('apply/', views.apply_workflow_to_project, name='apply_workflow_to_project'),
    path('apply-bulk/', views.apply_workflow_bulk, name='apply_workflow_bulk'),
    path('available-projects/', views.get_available_projects, name='get_available_projects'),
    path('projects-status/', views.get_projects_workflow_status, name='get_projects_workflow_status'),
    path('reviewable-projects/', views.get_reviewable_projects, name='get_reviewable_projects'),
    
    # Student: View and Submit
    path('project/<int:project_board_id>/', views.get_project_workflow, name='get_project_workflow'),
    path('project/<int:project_board_id>/replace/', views.replace_workflow_for_project, name='replace_workflow_for_project'),
    path('pending/', views.get_pending_stages, name='get_pending_stages'),
    path('stage/<int:stage_instance_id>/submit/', views.submit_workflow_stage, name='submit_workflow_stage'),
    path('cleanup-duplicates/', views.cleanup_duplicate_stages, name='cleanup_duplicate_stages'),
    # Review Submissions
    path('stage/<int:stage_instance_id>/review/', views.review_workflow_stage, name='review_workflow_stage'),
]