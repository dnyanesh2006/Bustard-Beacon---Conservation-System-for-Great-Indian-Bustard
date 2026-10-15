from django.conf import settings
from .models import Notification, ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER

def global_context(request):
    unread_notifications_count = 0
    user_role = None
    user_profile = None

    if request.user.is_authenticated:
        if hasattr(request.user, 'profile'):
            user_profile = request.user.profile
            user_role = user_profile.role
        elif request.user.is_superuser:
            user_role = ROLE_ADMIN

        unread_notifications_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()

    return {
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
        'unread_notifications_count': unread_notifications_count,
        'user_role': user_role,
        'user_profile': user_profile,
        'ROLE_ADMIN': ROLE_ADMIN,
        'ROLE_FOREST_OFFICER': ROLE_FOREST_OFFICER,
        'ROLE_RANGER': ROLE_RANGER,
        'ROLE_MEDICAL_TEAM': ROLE_MEDICAL_TEAM,
        'ROLE_RESEARCHER': ROLE_RESEARCHER,
    }
