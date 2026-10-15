from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from ..models import UserProfile, Notification, ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER
from ..services.audit_service import log_activity

def login_view(request):
    initial_role = (request.GET.get('role') or request.GET.get('login_role') or 'admin').lower()
    if initial_role not in ['admin', 'officer', 'ranger', 'medical', 'researcher']:
        initial_role = 'admin'

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
                return render(request, 'login.html', {'initial_role': requested_role.lower() if requested_role else 'admin'})

            login(request, user)
            
            # Map the authenticated user to the isolated role session
            role_sessions = request.session.get('role_sessions', {})
            role_sessions[actual_role] = {'user_id': user.id, 'hash': user.get_session_auth_hash()}
            request.session['role_sessions'] = role_sessions
            request.session.modified = True
            
            if request.POST.get('remember_me'):
                request.session.set_expiry(1209600) # 2 weeks
            else:
                request.session.set_expiry(0) # Browser close
                
            log_activity(user, "LOGIN", f"User {user.username} logged in successfully.", request=request)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")

            # Role-based landing redirect
            if actual_role == ROLE_RANGER:
                return redirect('ranger_field_mode')
            elif actual_role == ROLE_FOREST_OFFICER:
                return redirect('officer_dashboard')
            elif actual_role == ROLE_MEDICAL_TEAM:
                return redirect('medical_dashboard')
            elif actual_role == ROLE_RESEARCHER:
                return redirect('research_dashboard')
            elif actual_role == ROLE_ADMIN:
                return redirect('admin_dashboard')
            return redirect('dashboard')
        else:
            # Check if user exists but is deactivated (must check password to prevent username enumeration)
            from django.contrib.auth.models import User
            try_user = User.objects.filter(username=username).first()
            if try_user and not try_user.is_active and try_user.check_password(password):
                messages.error(request, "Your account has been deactivated. Please contact the administrator.")
            else:
                messages.error(request, "Invalid username or password. Please try again.")

    return render(request, 'login.html', {'initial_role': initial_role})

@login_required
def logout_view(request):
    log_activity(request.user, "LOGOUT", f"User {request.user.username} logged out.", request=request)
    
    # Selectively logout the active role context
    active_role = request.GET.get('active_role') or request.POST.get('active_role')
    if active_role:
        role_sessions = request.session.get('role_sessions', {})
        if active_role in role_sessions:
            del role_sessions[active_role]
            request.session['role_sessions'] = role_sessions
            request.session.modified = True
            
        # If no other roles are logged in, clear the whole Django session
        if not role_sessions:
            logout(request)
    else:
        # Fallback to complete logout if active_role is missing
        logout(request)
        
    messages.info(request, "You have been logged out.")
    return redirect('landing')

@login_required
def dashboard_redirect_view(request):
    """
    Intelligent role-based dashboard router
    """
    profile = request.user.profile if hasattr(request.user, 'profile') else None
    if profile:
        if profile.role == ROLE_RANGER:
            return redirect('ranger_field_mode')
        elif profile.role == ROLE_FOREST_OFFICER:
            return redirect('officer_dashboard')
        elif profile.role == ROLE_MEDICAL_TEAM:
            return redirect('medical_dashboard')
        elif profile.role == ROLE_RESEARCHER:
            return redirect('research_dashboard')
        elif profile.role == ROLE_ADMIN:
            return redirect('admin_dashboard')

    if request.user.is_superuser:
        return redirect('admin_dashboard')

    return redirect('live_map')

@login_required
def profile_view(request):
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        badge_number = request.POST.get('badge_number', '').strip()
        is_field_mode = request.POST.get('is_active_field_mode') == 'on'

        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()

        profile.phone_number = phone_number
        profile.badge_number = badge_number
        profile.is_active_field_mode = is_field_mode
        profile.save()

        log_activity(user, "UPDATE", f"User {user.username} updated profile.", model_name="UserProfile", object_id=profile.id, request=request)
        messages.success(request, "Profile updated successfully.")

    return render(request, 'profile.html', {'profile': profile})

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
            
            # Update our isolated session hash if an active role exists
            active_role = request.GET.get('active_role') or request.POST.get('active_role')
            if active_role:
                role_sessions = request.session.get('role_sessions', {})
                if active_role in role_sessions:
                    role_sessions[active_role]['hash'] = user.get_session_auth_hash()
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
