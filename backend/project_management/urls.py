from django.urls import path
from .views import (
    my_board, supervisor_boards, update_board,
    create_task, update_task, delete_task,
    task_comments, delete_comment,
    upload_attachment, delete_attachment,
    board_activity,
    hod_boards, hod_stats,
)

urlpatterns = [
    # Board
    path('api/project-management/board/',
         my_board, name='my_board'),
    path('api/project-management/board/<int:board_id>/update/',
         update_board, name='update_board'),
    path('api/project-management/supervisor/boards/',
         supervisor_boards, name='supervisor_boards'),
    path('api/project-management/hod/boards/',
         hod_boards, name='hod_boards'),
    path('api/project-management/hod/stats/',
         hod_stats, name='hod_stats'),

    # Tasks
    path('api/project-management/board/<int:board_id>/tasks/',
         create_task, name='create_task'),
    path('api/project-management/board/<int:board_id>/tasks/<int:task_id>/',
         update_task, name='update_task'),
    path('api/project-management/board/<int:board_id>/tasks/<int:task_id>/delete/',
         delete_task, name='delete_task'),

    # Comments
    path('api/project-management/board/<int:board_id>/tasks/<int:task_id>/comments/',
         task_comments, name='task_comments'),
    path('api/project-management/board/<int:board_id>/tasks/<int:task_id>/comments/<int:comment_id>/delete/',
         delete_comment, name='delete_comment'),

    # Attachments
    path('api/project-management/board/<int:board_id>/tasks/<int:task_id>/attachments/',
         upload_attachment, name='upload_attachment'),
    path('api/project-management/board/<int:board_id>/tasks/<int:task_id>/attachments/<int:attachment_id>/delete/',
         delete_attachment, name='delete_attachment'),

    # Activity
    path('api/project-management/board/<int:board_id>/activity/',
         board_activity, name='board_activity'),
]
