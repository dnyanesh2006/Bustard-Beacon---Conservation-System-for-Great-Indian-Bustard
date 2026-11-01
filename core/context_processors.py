from django.conf import settings
from .models import Notification, ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER

def global_context(request):
    unread_notifications_count = 0
    user_role = None
    user_profile = None

    if request.user.is_authenticated:
        try:
            user_profile = request.user.profile
        except Exception:
            user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        user_role = user_profile.role if user_profile else (ROLE_ADMIN if request.user.is_superuser else None)

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
