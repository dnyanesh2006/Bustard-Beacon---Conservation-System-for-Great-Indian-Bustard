from functools import wraps

from django.core.exceptions import PermissionDenied


def role_required(*allowed_roles):
    """Require an authenticated user with one of the supplied profile roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            profile = request.user.profile if hasattr(request.user, 'profile') else None
            if profile is None or profile.role not in allowed_roles:
                raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return wrapped
    return decorator