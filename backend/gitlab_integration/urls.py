from django.urls import path
from . import views
from .webhook_views import GitLabWebhookView

app_name = 'gitlab_integration'

urlpatterns = [
    # ===== Webhook (no auth required) =====
    path('webhook/', GitLabWebhookView.as_view(), name='gitlab-webhook'),
    
    # ===== Health Check =====
    path('health/', views.GitLabHealthView.as_view(), name='gitlab-health'),

    # ===== GitLab Config =====
    path('config/', views.GitLabConfigView.as_view(), name='gitlab-config'),
    
    # ===== Account Linking =====
    path('verify-token/', views.VerifyGitLabTokenView.as_view(), name='verify-token'),
    path('link-account/', views.LinkGitLabAccountView.as_view(), name='link-account'),
    path('unlink-account/', views.UnlinkGitLabAccountView.as_view(), name='unlink-account'),
    path('account-status/', views.GitLabAccountStatusView.as_view(), name='account-status'),
    
    # ===== Per-Board: Project =====
    path('board/<int:board_id>/create-project/', views.CreateGitLabProjectView.as_view(), name='create-project'),
    path('board/<int:board_id>/', views.BoardGitLabInfoView.as_view(), name='board-gitlab-info'),
    path('board/<int:board_id>/fix-access/', views.FixBoardGitLabAccessView.as_view(), name='fix-board-access'),
    
    # ===== Per-Board: Members =====
    path('board/<int:board_id>/members/', views.BoardGitLabMembersView.as_view(), name='board-members'),
    path('board/<int:board_id>/members/add/', views.AddBoardMemberView.as_view(), name='add-member'),
    path('board/<int:board_id>/members/remove/', views.RemoveBoardMemberView.as_view(), name='remove-member'),
    
    # ===== Per-Board: Commits =====
    path('board/<int:board_id>/commits/', views.BoardCommitsView.as_view(), name='board-commits'),
    path('board/<int:board_id>/commits/<int:commit_id>/', views.BoardCommitDetailView.as_view(), name='commit-detail'),
    path('board/<int:board_id>/stats/', views.BoardCommitStatsView.as_view(), name='commit-stats'),
    path('board/<int:board_id>/sync/', views.SyncCommitsView.as_view(), name='sync-commits'),
    
    # ===== All Boards Stats (HoD/Dean) =====
    path('stats/', views.AllBoardsStatsView.as_view(), name='all-boards-stats'),
]