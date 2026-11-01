from django.contrib.auth import logout, get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
import logging
from .models import Notification, UserProfile, ROLE_ADMIN

logger = logging.getLogger(__name__)

class MultiRoleAuthMiddleware:
    """
    Provides isolated authentication contexts per role using the same Django session.
    Overrides request.user based on the active role derived from the URL or query params.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        active_role = request.GET.get('active_role') or request.POST.get('active_role')
        if active_role:
            active_role = active_role.upper()
            if active_role in ['OFFICER', 'FOREST_OFFICER']:
                active_role = 'FOREST_OFFICER'
            elif active_role in ['MEDICAL', 'VET', 'MEDICAL_TEAM']:
                active_role = 'MEDICAL_TEAM'
            elif active_role == 'ADMIN':
                active_role = 'ADMIN'
            elif active_role == 'RANGER':
                active_role = 'RANGER'
            elif active_role == 'RESEARCHER':
                active_role = 'RESEARCHER'
        
        if not active_role:
            if '/admin-panel/' in path:
                active_role = 'ADMIN'
            elif '/ranger/' in path:
                active_role = 'RANGER'
            elif '/officer/' in path:
                role_sessions = request.session.get('role_sessions', {})
                if '/officer/tourism/' in path and 'FOREST_OFFICER' not in role_sessions and 'ADMIN' in role_sessions:
                    active_role = 'ADMIN'
                else:
                    active_role = 'FOREST_OFFICER'
            elif '/medical/' in path:
                active_role = 'MEDICAL_TEAM'
            elif '/research/' in path:
                role_sessions = request.session.get('role_sessions', {})
                if '/research/reports/generate/' in path and 'RESEARCHER' not in role_sessions:
                    if 'ADMIN' in role_sessions:
                        active_role = 'ADMIN'
                    elif 'FOREST_OFFICER' in role_sessions:
                        active_role = 'FOREST_OFFICER'
                    else:
                        active_role = 'RESEARCHER'
                else:
                    active_role = 'RESEARCHER'

        # If still not set, inspect HTTP_REFERER for multi-tab link opening
        if not active_role and path not in ['/login/', '/logout/', '/']:
            referer = request.META.get('HTTP_REFERER', '')
            if '/admin-panel/' in referer:
                active_role = 'ADMIN'
            elif '/ranger/' in referer:
                active_role = 'RANGER'
            elif '/officer/' in referer:
                active_role = 'FOREST_OFFICER'
            elif '/medical/' in referer:
                active_role = 'MEDICAL_TEAM'
            elif '/research/' in referer:
                active_role = 'RESEARCHER'
            elif 'active_role=' in referer:
                import urllib.parse
                parsed = urllib.parse.urlparse(referer)
                qs = urllib.parse.parse_qs(parsed.query)
                ref_role = qs.get('active_role', [None])[0]
                if ref_role:
                    active_role = ref_role.upper()
            if not active_role and 'last_active_role' in request.session:
                active_role = request.session.get('last_active_role')

        # If we have an active role, override request.user for true isolation
        if active_role:
            original_user = request.user
            request.user = AnonymousUser()
            role_sessions = request.session.get('role_sessions', {})
            session_data = role_sessions.get(active_role)
            
            if session_data:
                User = get_user_model()
                try:
                    user = User.objects.get(pk=session_data['user_id'])
                    auth_hash = session_data.get('hash')
                    if auth_hash is None or user.get_session_auth_hash() == auth_hash:
                        request.user = user
                    else:
                        del request.session['role_sessions'][active_role]
                        request.session.modified = True
                except User.DoesNotExist:
                    pass
            elif original_user.is_authenticated:
                # Fallback for testing (force_login) or single-session compatibility
                profile = original_user.profile if hasattr(original_user, 'profile') else None
                if (profile and profile.role == active_role) or (original_user.is_superuser and active_role == 'ADMIN'):
                    request.user = original_user

        elif path == '/login/':
            role_param = (request.GET.get('role') or request.GET.get('login_role') or '').lower()
            role_map = {
                'admin': 'ADMIN',
                'officer': 'FOREST_OFFICER',
                'ranger': 'RANGER',
                'medical': 'MEDICAL_TEAM',
                'researcher': 'RESEARCHER',
            }
            target_role = role_map.get(role_param)
            role_sessions = request.session.get('role_sessions', {})
            if target_role and target_role in role_sessions:
                User = get_user_model()
                session_data = role_sessions[target_role]
                try:
                    user = User.objects.get(pk=session_data['user_id'])
                    auth_hash = session_data.get('hash')
                    if auth_hash is None or user.get_session_auth_hash() == auth_hash:
                        request.user = user
                except User.DoesNotExist:
                    pass

        response = self.get_response(request)
        if request.user.is_authenticated or path.startswith(('/admin-panel/', '/ranger/', '/officer/', '/medical/', '/research/', '/profile/', '/password-change/')):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response

class EnforceActiveUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_active:
            logout(request)
            messages.error(request, "Your account has been deactivated. Please contact the administrator.")
            return redirect('login')
        return self.get_response(request)

class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Check if user needs to change password
            profile = request.user.profile if hasattr(request.user, 'profile') else None
            if profile and profile.force_password_change:
                # Allow access to password change page and logout, block everything else
                allowed_paths = [reverse('password_change'), reverse('logout')]
                if request.path not in allowed_paths and not request.path.startswith('/static/'):
                    active_role = request.GET.get('active_role') or request.POST.get('active_role') or profile.role
                    return redirect(f"{reverse('password_change')}?active_role={active_role}")

        response = self.get_response(request)
        return response

class ExceptionNotificationMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        try:
            error_type = type(exception).__name__
            error_message = str(exception)
            
            admins = UserProfile.objects.filter(role=ROLE_ADMIN).select_related('user')
            for admin_profile in admins:
                Notification.objects.create(
                    recipient=admin_profile.user,
                    title=f"Critical Application Error: {error_type}",
                    message=f"A technical error occurred in the application: {error_message[:300]}. Please check server logs for details.",
                    category="SYSTEM_ERROR"
                )
        except Exception as e:
            logger.error(f"Failed to create Admin notification for exception: {e}")
        return None
