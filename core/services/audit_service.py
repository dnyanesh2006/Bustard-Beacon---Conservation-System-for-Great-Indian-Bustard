from ..models import ActivityLog
from django.utils import timezone

def log_activity(user, action, description, model_name="", object_id="", request=None):
    ip_address = None
    user_display = "Anonymous / System"

    if user and user.is_authenticated:
        user_display = f"{user.get_full_name() or user.username} ({user.username})"
    elif isinstance(user, str):
        user_display = user

    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')

    return ActivityLog.objects.create(
        user=user if (user and hasattr(user, 'is_authenticated') and user.is_authenticated) else None,
        user_display=user_display,
        action=action,
        model_name=model_name,
        object_id=str(object_id),
        description=description,
        ip_address=ip_address,
        timestamp=timezone.now()
    )
