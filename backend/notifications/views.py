from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    notifs = Notification.objects.filter(recipient=request.user)[:50]
    return Response(NotificationSerializer(notifs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return Response({'count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_read(request, notif_id):
    try:
        n = Notification.objects.get(pk=notif_id, recipient=request.user)
        n.is_read = True
        n.save(update_fields=['is_read'])
    except Notification.DoesNotExist:
        pass
    return Response({'ok': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return Response({'ok': True})
