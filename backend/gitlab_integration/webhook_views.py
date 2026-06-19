import json
import logging
from rest_framework import status, views
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from . import services

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class GitLabWebhookView(views.APIView):
    """
    استقبال Push Events من GitLab Webhook.
    
    GitLab بيبعت POST request لهاد الرابط كل ما بيصير push على المستودع.
    
    ملاحظة مهمة: هاد الرابط ما بيحتاج JWT authentication - 
    GitLab بيبعت token بالهيدر X-Gitlab-Token للتأكد من هوية المرسل.
    
    POST /api/gitlab/webhook/
    Headers:
        X-Gitlab-Token: <webhook_secret>
        X-Gitlab-Event: Push Hook
    Body: JSON payload مع بيانات الـ commits
    """
    # Important: No authentication required - GitLab sends the token
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        Process a push webhook from GitLab.
        
        The webhook payload contains:
        - ref: branch name (e.g., "refs/heads/main")
        - before/after: commit SHAs
        - user_username: who pushed
        - project: {id, name, web_url, ...}
        - commits: [{id, message, author, added, removed, modified, url, ...}]
        - total_commits_count: number of commits
        """
        # Step 1: Verify the webhook is actually from GitLab
        token_header = request.headers.get('X-Gitlab-Token', '')
        payload_body = request.body
        
        if not services.verify_webhook_signature(payload_body, token_header):
            logger.warning(
                "Received webhook with invalid or missing token. "
                f"Source IP: {request.META.get('REMOTE_ADDR')}"
            )
            return Response(
                {'error': 'Token غير صالح'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Step 2: Check event type (we only care about push events)
        event_type = request.headers.get('X-Gitlab-Event', '')
        if event_type != 'Push Hook':
            logger.info(f"Ignoring non-push event: {event_type}")
            return Response(
                {'message': f'تم تجاهل الحدث: {event_type}'},
                status=status.HTTP_200_OK
            )
        
        # Step 3: Parse the JSON payload
        try:
            payload = json.loads(payload_body)
        except json.JSONDecodeError:
            logger.error("Received webhook with invalid JSON payload")
            return Response(
                {'error': 'JSON payload غير صالح'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Step 4: Process the push event and save commits
        try:
            result = services.process_push_webhook(payload)
            
            logger.info(
                f"Webhook processed successfully: "
                f"project={result['project_name']}, "
                f"pusher={result['pusher']}, "
                f"new_commits={result['new_commits']}/{result['total_commits']}"
            )
            
            return Response({
                'success': True,
                'message': f'تم استقبال {result["new_commits"]} commits جديدة',
                'data': result,
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            # Project not found in our database - not an error, just ignore
            logger.warning(f"Webhook for unregistered project: {e}")
            return Response(
                {'message': str(e)},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(
                f"Error processing webhook: {str(e)}",
                exc_info=True
            )
            return Response(
                {'error': 'حدث خطأ داخلي أثناء معالجة الـ webhook'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )