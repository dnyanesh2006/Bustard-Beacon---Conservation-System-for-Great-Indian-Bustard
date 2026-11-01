from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from ..models import UserProfile, Notification, ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER
from ..services.audit_service import log_activity
from ..validators import validate_indian_mobile, validate_email_address

ROLE_MAP = {
    'admin': ROLE_ADMIN,
    'officer': ROLE_FOREST_OFFICER,
    'ranger': ROLE_RANGER,
    'medical': ROLE_MEDICAL_TEAM,
    'researcher': ROLE_RESEARCHER,
}

DASHBOARD_ROUTES = {
    ROLE_ADMIN: 'admin_dashboard',
    ROLE_FOREST_OFFICER: 'officer_dashboard',
    ROLE_RANGER: 'ranger_field_mode',
    ROLE_MEDICAL_TEAM: 'medical_dashboard',
    ROLE_RESEARCHER: 'research_dashboard',
}


def is_user_authorized_for_path(user, path):
    """Check if the given authenticated user is authorized to access the given path."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if not profile:
        return False
    role = profile.role
    if path.startswith('/admin-panel/'):
        return role == ROLE_ADMIN
    if path.startswith('/officer/'):
        if path.startswith('/officer/tourism/'):
            return role in (ROLE_FOREST_OFFICER, ROLE_ADMIN)
        return role == ROLE_FOREST_OFFICER
    if path.startswith('/ranger/'):
        return role == ROLE_RANGER
    if path.startswith('/medical/'):
        return role == ROLE_MEDICAL_TEAM
    if path.startswith('/research/'):
        return role in (ROLE_RESEARCHER, ROLE_FOREST_OFFICER, ROLE_ADMIN)
    return True

def get_role_from_path(path):
    """Derive the suggested role from a redirect target path."""
    if not path:
        return None
    if path.startswith('/admin-panel/'):
        return 'admin'
    if path.startswith('/officer/'):
        return 'officer'
    if path.startswith('/ranger/'):
        return 'ranger'
    if path.startswith('/medical/'):
        return 'medical'
    if path.startswith('/research/'):
        return 'researcher'
    return None

def login_view(request):
    raw_role = (request.GET.get('role') or request.GET.get('login_role') or '').lower()
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    
    # Infer initial role from query parameter, or from next_url if available
    inferred_role_from_next = get_role_from_path(next_url) if next_url else None
    if raw_role in ROLE_MAP:
        initial_role = raw_role
    elif inferred_role_from_next in ROLE_MAP:
        initial_role = inferred_role_from_next
    else:
        initial_role = 'admin'

    # If GET request:
    if request.method == 'GET':
        # If user is already authenticated AND requested a next_url they are already authorized to view:
        if request.user.is_authenticated and next_url and next_url.startswith('/') and not next_url.startswith('//'):
            if is_user_authorized_for_path(request.user, next_url):
                if 'active_role=' not in next_url:
                    profile = getattr(request.user, 'profile', None)
                    actual_role = profile.role if profile else ('ADMIN' if request.user.is_superuser else None)
                    if actual_role:
                        sep = '&' if '?' in next_url else '?'
                        next_url += f"{sep}active_role={actual_role}"
                return redirect(next_url)

        # In all other cases (visiting /login/, opening in new tab, or switching accounts):
        # Render the login page cleanly. Do not bounce unexpectedly to an active session dashboard.
        entered_username = request.GET.get('entered_username', '')
        return render(request, 'login.html', {
            'initial_role': initial_role,
            'entered_username': entered_username,
        })

    if request.method == 'POST':
        username = (
            request.POST.get('username') or
            request.POST.get('username_admin') or
            request.POST.get('username_officer') or
            request.POST.get('username_ranger') or
            request.POST.get('username_medical') or
            request.POST.get('username_researcher') or ''
        ).strip()
        password = (
            request.POST.get('password') or
            request.POST.get('password_admin') or
            request.POST.get('password_officer') or
            request.POST.get('password_ranger') or
            request.POST.get('password_medical') or
            request.POST.get('password_researcher') or ''
        )

        if not username and not password:
            messages.error(request, "Please enter your username and password.")
            return render(request, 'login.html', {'initial_role': initial_role, 'entered_username': ''})
        if not username:
            messages.error(request, "Please enter your username.")
            return render(request, 'login.html', {'initial_role': initial_role, 'entered_username': ''})
        if not password:
            messages.error(request, "Please enter your password.")
            return render(request, 'login.html', {'initial_role': initial_role, 'entered_username': username})

        user = authenticate(request, username=username, password=password)

        if user is not None:
            requested_role = request.POST.get('login_role', '').upper()
            if requested_role in ['OFFICER', 'FOREST_OFFICER']: requested_role = ROLE_FOREST_OFFICER
            elif requested_role in ['MEDICAL', 'VET', 'MEDICAL_TEAM']: requested_role = ROLE_MEDICAL_TEAM
            elif requested_role == 'ADMIN': requested_role = ROLE_ADMIN
            elif requested_role == 'RANGER': requested_role = ROLE_RANGER
            elif requested_role == 'RESEARCHER': requested_role = ROLE_RESEARCHER

            profile = user.profile if hasattr(user, 'profile') else None
            actual_role = profile.role if profile else (ROLE_ADMIN if user.is_superuser else None)

            if requested_role and actual_role != requested_role:
                # Reject cross-role login
                from ..models import ROLE_CHOICES
                display_role = dict(ROLE_CHOICES).get(actual_role, 'Administrator' if user.is_superuser else 'Unknown')
                messages.error(request, f"These credentials belong to the {display_role} role. Please switch to the correct tab.")
                return render(request, 'login.html', {'initial_role': requested_role.lower() if requested_role else 'admin', 'entered_username': username})

            # Preserve existing role sessions across Django login flush
            saved_role_sessions = dict(request.session.get('role_sessions', {}))
            login(request, user)
            
            # Map the authenticated user to the isolated role session
            saved_role_sessions[actual_role] = {'user_id': user.id, 'hash': user.get_session_auth_hash()}
            request.session['role_sessions'] = saved_role_sessions
            request.session['last_active_role'] = actual_role
            request.session.modified = True
            
            if request.POST.get('remember_me'):
                request.session.set_expiry(1209600) # 2 weeks
            else:
                request.session.set_expiry(0) # Browser close
                
            log_activity(user, "LOGIN", f"User {user.username} logged in successfully.", request=request)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")

            # Honor next redirect if present, safe, and authorized
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                if is_user_authorized_for_path(user, next_url):
                    if 'active_role=' not in next_url:
                        sep = '&' if '?' in next_url else '?'
                        next_url += f"{sep}active_role={actual_role}"
                    return redirect(next_url)

            # Role-based landing redirect
            dest_url = reverse(DASHBOARD_ROUTES.get(actual_role, 'dashboard'))
            return redirect(dest_url)
        else:
            # Check if user exists but is deactivated (must check password to prevent username enumeration)
            from django.contrib.auth.models import User
            from django.db.models import Q
            try_user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
            if try_user and not try_user.is_active and try_user.check_password(password):
                messages.error(request, "Your account has been deactivated. Please contact the administrator.")
            else:
                messages.error(request, "Invalid username or password. Please try again.")
            return render(request, 'login.html', {'initial_role': initial_role, 'entered_username': username})

    return render(request, 'login.html', {'initial_role': initial_role})

def logout_view(request):
    log_activity(request.user, "LOGOUT", f"User {request.user.username} logged out.", request=request)
    logout(request)
    request.session.flush()
    messages.info(request, "You have been logged out.")
    response = redirect('landing')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def dashboard_redirect_view(request):
    """
    Intelligent role-based dashboard router
    """
    profile = request.user.profile if hasattr(request.user, 'profile') else None
    active_role = request.GET.get('active_role') or request.POST.get('active_role')
    
    if not active_role and profile:
        active_role = profile.role

    if active_role:
        dest_view = DASHBOARD_ROUTES.get(active_role)
        if dest_view:
            return redirect(f"{reverse(dest_view)}?active_role={active_role}")

    if request.user.is_superuser:
        return redirect(f"{reverse('admin_dashboard')}?active_role=ADMIN")

    return redirect('live_map')

@login_required
def profile_view(request):
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Handle remove image
        if action == 'remove_image' or request.POST.get('remove_profile_image') == '1':
            if profile.profile_image:
                try:
                    profile.profile_image.delete(save=False)
                except Exception:
                    pass
                profile.profile_image = None
                profile.save()
            log_activity(user, "UPDATE", f"User {user.username} removed profile image.", model_name="UserProfile", object_id=profile.id, request=request)
            messages.success(request, "Profile image removed successfully.")
            active_role = request.GET.get('active_role') or request.POST.get('active_role', '')
            redirect_url = f"/profile/?active_role={active_role}" if active_role else "/profile/"
            return redirect(redirect_url)

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        badge_number = request.POST.get('badge_number', '').strip()

        errors = []
        if email:
            email_err = validate_email_address(email)
            if email_err:
                errors.append(email_err)
            else:
                existing = User.objects.filter(email__iexact=email).exclude(id=user.id).first()
                if existing:
                    errors.append(f"Email '{email}' is already in use by another account.")
                else:
                    user.email = email.strip()
        else:
            user.email = ''

        if phone_number:
            phone_err = validate_indian_mobile(phone_number)
            if phone_err:
                errors.append(phone_err)
            else:
                profile.phone_number = phone_number.strip()
        else:
            profile.phone_number = ''

        # Handle Profile Image Upload (cropped base64 or direct file)
        cropped_image_data = request.POST.get('cropped_image_data', '').strip()
        if cropped_image_data and ';base64,' in cropped_image_data:
            import base64
            from django.core.files.base import ContentFile
            try:
                format, imgstr = cropped_image_data.split(';base64,')
                ext = 'jpg' if 'jpeg' in format.lower() else ('png' if 'png' in format.lower() else 'jpg')
                img_data = base64.b64decode(imgstr)
                if len(img_data) > 5 * 1024 * 1024:
                    errors.append("Profile image must be less than 5 MB.")
                else:
                    filename = f"avatar_{user.id}_{int(timezone.now().timestamp())}.{ext}"
                    if profile.profile_image:
                        try:
                            profile.profile_image.delete(save=False)
                        except Exception:
                            pass
                    profile.profile_image.save(filename, ContentFile(img_data), save=False)
            except Exception as e:
                errors.append(f"Invalid image format: {e}")
        elif 'profile_image' in request.FILES:
            uploaded_file = request.FILES['profile_image']
            if uploaded_file.size > 5 * 1024 * 1024:
                errors.append("Profile image must be less than 5 MB.")
            else:
                if profile.profile_image:
                    try:
                        profile.profile_image.delete(save=False)
                    except Exception:
                        pass
                profile.profile_image = uploaded_file

        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, 'profile.html', {'profile': profile, 'user_profile': profile})

        user.first_name = first_name
        user.last_name = last_name
        user.save()

        profile.badge_number = badge_number
        profile.save()

        log_activity(user, "UPDATE", f"User {user.username} updated profile.", model_name="UserProfile", object_id=profile.id, request=request)
        messages.success(request, "Profile updated successfully.")
        active_role = request.GET.get('active_role') or request.POST.get('active_role', '')
        redirect_url = f"/profile/?active_role={active_role}" if active_role else "/profile/"
        return redirect(redirect_url)

    return render(request, 'profile.html', {'profile': profile, 'user_profile': profile})

@login_required
def notifications_view(request):
    profile = getattr(request.user, 'profile', None)

    # Ensure existing submitted research reports intended for Forest Officer or Admin are identifiable
    if profile:
        from ..models import ConservationReport
        if profile.role == ROLE_FOREST_OFFICER:
            for rep in ConservationReport.objects.filter(status='FINALIZED', submitted_to_fo=True):
                notif_link = f"/reports/pdf/?type=CONSERVATION_ANALYSIS_REPORT&report_id={rep.id}"
                if not Notification.objects.filter(recipient=request.user, link_url=notif_link).exists():
                    Notification.objects.create(
                        recipient=request.user,
                        title="Monthly Conservation Analysis Report Submitted",
                        message=f"The Researcher has submitted the conservation analysis report for {rep.period_start.strftime('%B %Y')}.",
                        category="RESEARCH_REPORT",
                        link_url=notif_link
                    )
        elif profile.role == ROLE_ADMIN:
            for rep in ConservationReport.objects.filter(status='FINALIZED', submitted_to_admin=True):
                notif_link = f"/reports/pdf/?type=CONSERVATION_ANALYSIS_REPORT&report_id={rep.id}"
                if not Notification.objects.filter(recipient=request.user, link_url=notif_link).exists():
                    Notification.objects.create(
                        recipient=request.user,
                        title="Monthly Conservation Analysis Report Submitted",
                        message=f"The Researcher has submitted the conservation analysis report for {rep.period_start.strftime('%B %Y')}.",
                        category="RESEARCH_REPORT",
                        link_url=notif_link
                    )

    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_all_read':
            notifications.filter(is_read=False).update(is_read=True)
            messages.success(request, "All notifications marked as read.")
            return redirect('notifications')
        elif action == 'mark_read':
            notif_id = request.POST.get('notification_id')
            n = get_object_or_404(Notification, id=notif_id, recipient=request.user)
            n.is_read = True
            n.save()
            if n.link_url:
                url = n.link_url
                if profile and 'active_role=' not in url:
                    separator = '&' if '?' in url else '?'
                    url += f"{separator}active_role={profile.role}"
                return redirect(url)
            return redirect('notifications')

    # Deduplicate notifications for clean display without redundant entries
    seen_keys = set()
    unique_notifications = []
    for notif in notifications:
        key = (notif.title, notif.link_url) if notif.link_url else notif.id
        if key not in seen_keys:
            seen_keys.add(key)
            unique_notifications.append(notif)

    return render(request, 'notifications.html', {'notifications': unique_notifications})

import os
from django.conf import settings
from django.contrib.auth.models import User
import requests

def google_login_view(request):
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    redirect_uri = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', '')
    if not client_id:
        messages.error(request, "Google login is not configured.")
        return redirect('login')
    
    scope = "openid email profile"
    url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&response_type=code&scope={scope}&redirect_uri={redirect_uri}&access_type=offline"
    return redirect(url)

def google_callback_view(request):
    code = request.GET.get('code')
    if not code:
        messages.error(request, "Google login failed.")
        return redirect('login')
        
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    redirect_uri = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', '')
    
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    
    res = requests.post(token_url, data=data)
    if not res.ok:
        messages.error(request, "Failed to authenticate with Google.")
        return redirect('login')
        
    token_data = res.json()
    access_token = token_data.get('access_token')
    
    user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    user_info_res = requests.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"})
    if not user_info_res.ok:
        messages.error(request, "Failed to fetch user info from Google.")
        return redirect('login')
        
    user_info = user_info_res.json()
    email = user_info.get('email')
    
    if not email:
        messages.error(request, "Google account does not have an email.")
        return redirect('login')
        
    # Check if user exists
    user = User.objects.filter(email=email).first()
    if not user:
        request.session['pending_google_email'] = email
        request.session['pending_google_first_name'] = user_info.get('given_name', '')
        request.session['pending_google_last_name'] = user_info.get('family_name', '')
        return redirect('google_register')
        
    if not user.is_active:
        messages.error(request, "Your account is deactivated.")
        return redirect('login')
        
    login(request, user)
    log_activity(user, "LOGIN", f"User {user.username} logged in via Google.", request=request)
    messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
    
    return redirect('dashboard')

def google_register_view(request):
    email = request.session.get('pending_google_email')
    if not email:
        return redirect('login')

    if request.method == 'POST':
        first_name = request.session.get('pending_google_first_name', '')
        last_name = request.session.get('pending_google_last_name', '')
        
        # Generate unique username
        base_username = email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name[:30],
            last_name=last_name[:30],
            is_active=False # Pending admin approval
        )
        user.set_unusable_password()
        user.save()
        
        UserProfile.objects.create(user=user, role=ROLE_RESEARCHER) # Default role, admin sets correct one
        
        del request.session['pending_google_email']
        
        messages.success(request, f"Account creation requested for {email}. It is currently pending Admin approval.")
        return redirect('login')
        
    return render(request, 'google_register.html', {'email': email})

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

@login_required
def password_change_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            
            # Update role_sessions hashes for this user across all roles they occupy
            new_hash = user.get_session_auth_hash()
            role_sessions = request.session.get('role_sessions', {})
            modified = False
            for r_key, r_data in role_sessions.items():
                if r_data.get('user_id') == user.id:
                    r_data['hash'] = new_hash
                    modified = True
            if modified:
                request.session['role_sessions'] = role_sessions
                request.session.modified = True
            
            profile = user.profile if hasattr(user, 'profile') else None
            if profile and profile.force_password_change:
                profile.force_password_change = False
                profile.save()
                
            messages.success(request, 'Your password was successfully updated!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'password_change.html', {
        'form': form
    })

from django.http import JsonResponse

@login_required
def api_unread_notifications_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread_count': count})


from django import forms
from django.conf import settings
from django.contrib.auth import views as django_auth_views, get_user_model
from django.contrib.auth.forms import PasswordResetForm, _unicode_ci_compare
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse_lazy
import logging

reset_logger = logging.getLogger(__name__)


class BustardPasswordResetForm(PasswordResetForm):
    """
    Custom password reset form that:
    1. Validates that an active account exists for the entered email address,
       preventing false-positive 'instructions sent' screens for unknown emails.
    2. Allows active users who registered via OAuth or have unusable passwords
       to receive reset instructions and establish a password for dual login.
    """
    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        user_model = get_user_model()
        email_field = user_model.get_email_field_name()

        matching = user_model._default_manager.filter(**{
            f'{email_field}__iexact': email
        })
        if not matching.exists():
            raise forms.ValidationError(
                "No registered staff account was found matching this email address. "
                "Please verify the email address or contact an administrator."
            )
        active_matching = matching.filter(is_active=True)
        if not active_matching.exists():
            raise forms.ValidationError(
                "This staff account is currently inactive. Please contact an administrator."
            )
        return email

    def get_users(self, email):
        user_model = get_user_model()
        email_field = user_model.get_email_field_name()
        active_users = user_model._default_manager.filter(**{
            f'{email_field}__iexact': email,
            'is_active': True,
        })
        return [
            u for u in active_users
            if _unicode_ci_compare(email, getattr(u, email_field))
        ]


class SafePasswordResetView(django_auth_views.PasswordResetView):
    form_class = BustardPasswordResetForm
    template_name = 'password_reset.html'
    email_template_name = 'password_reset_email.html'
    html_email_template_name = 'password_reset_email_html.html'
    subject_template_name = 'password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def form_valid(self, form):
        email = form.cleaned_data.get('email', '').strip()
        mailers_config = getattr(settings, 'MAILERS', {}).get('default', {})
        backend_name = mailers_config.get('BACKEND', '') or getattr(settings, 'EMAIL_BACKEND', '')
        is_console = 'console' in backend_name.lower()

        try:
            opts = {
                'use_https': self.request.is_secure(),
                'token_generator': self.token_generator,
                'from_email': self.from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                'email_template_name': self.email_template_name,
                'subject_template_name': self.subject_template_name,
                'request': self.request,
                'html_email_template_name': self.html_email_template_name,
                'extra_email_context': self.extra_email_context,
            }
            form.save(**opts)
        except Exception as mail_err:
            reset_logger.error("Password reset email delivery failed for %s: %s", email, mail_err.__class__.__name__)
            messages.error(
                self.request,
                "Unable to deliver the password reset email due to an outgoing mail server issue. "
                "Please verify network connectivity or contact an administrator."
            )
            return self.render_to_response(self.get_context_data(form=form))

        # Store confirmed recipient email in session for confirmation screen
        self.request.session['password_reset_sent_to'] = email

        if is_console:
            dev_links = []
            for u in form.get_users(email):
                uid = urlsafe_base64_encode(force_bytes(u.pk))
                token = default_token_generator.make_token(u)
                link = f"{self.request.scheme}://{self.request.get_host()}/reset/{uid}/{token}/"
                dev_links.append({'username': u.username, 'link': link})
            self.request.session['dev_recovery_links'] = dev_links

        return redirect(self.get_success_url())


class SafePasswordResetDoneView(django_auth_views.PasswordResetDoneView):
    template_name = 'password_reset_done.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sent_email'] = self.request.session.pop('password_reset_sent_to', None)
        context['dev_recovery_links'] = self.request.session.pop('dev_recovery_links', None)
        return context


class SafePasswordResetConfirmView(django_auth_views.PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.user
        profile = getattr(user, 'profile', None)
        if profile and profile.force_password_change:
            profile.force_password_change = False
            profile.save()
        return response
