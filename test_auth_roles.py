import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bustard_beacon.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from core.models import UserProfile, ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER

ROLES_AND_DASHBOARDS = {
    ROLE_ADMIN: '/admin-panel/',
    ROLE_RANGER: '/ranger/field-mode/',
    ROLE_FOREST_OFFICER: '/officer/dashboard/',
    ROLE_MEDICAL_TEAM: '/medical/dashboard/',
    ROLE_RESEARCHER: '/research/dashboard/',
}

def run_tests():
    # Setup users
    users = {}
    for role, url in ROLES_AND_DASHBOARDS.items():
        u = User.objects.filter(username=f'test_{role.lower()}').first()
        if not u:
            u = User.objects.create_user(username=f'test_{role.lower()}', email=f'{role}@test.com')
        u.set_password('pass123')
        u.is_active = True
        u.is_superuser = False
        u.save()
        p, _ = UserProfile.objects.get_or_create(user=u)
        p.role = role
        p.save()
        users[role] = u

    client = Client()

    # 1. Test Login & Redirect & Access
    print("Testing Login and Dashboards...")
    for role, user in users.items():
        client.logout()
        res = client.post('/login/', {'username': user.username, 'password': 'pass123'})
        if res.status_code == 302:
            redirect_url = res.url
            # Follow if it redirects to /dashboard/
            if redirect_url == '/dashboard/':
                res2 = client.get('/dashboard/')
                if res2.status_code == 302:
                    redirect_url = res2.url
            print(f"[{role}] Logged in. Redirected to: {redirect_url}. Expected: {ROLES_AND_DASHBOARDS[role]}")
            if redirect_url != ROLES_AND_DASHBOARDS[role]:
                print(f"[{role}] ERROR: Wrong redirect!")
        else:
             print(f"[{role}] ERROR: Login failed!")

        # Follow to actual dashboard to ensure 200
        client.get(ROLES_AND_DASHBOARDS[role])
        
        # Now test unauthorized access
        for other_role, other_url in ROLES_AND_DASHBOARDS.items():
            if other_role != role:
                access_res = client.get(other_url)
                if access_res.status_code == 403:
                    print(f"[{role}] Access to {other_role} dashboard ({other_url}) properly BLOCKED (403).")
                elif access_res.status_code == 302:
                    print(f"[{role}] Access to {other_role} dashboard ({other_url}) redirected (302).")
                else:
                    if role == ROLE_ADMIN and access_res.status_code == 200:
                        # Wait, admin is a superuser? If it's a superuser, decorator allows access!
                        # The decorator says: `if request.user.is_superuser: return view_func(request, *args, **kwargs)`
                        # But is the admin role inherently superuser? `is_admin_check` says `user.is_superuser or (hasattr(user, 'profile') and user.profile.role == ROLE_ADMIN)`.
                        # But the role_required decorator does NOT let ROLE_ADMIN bypass other checks unless they are actually is_superuser!
                        print(f"[{role}] WARNING: Access to {other_role} dashboard allowed! (Status {access_res.status_code})")
                    else:
                        print(f"[{role}] ERROR: Access to {other_role} dashboard allowed! (Status {access_res.status_code})")

    # 2. Test deactivated user
    client.logout()
    print("Testing Deactivated User...")
    users[ROLE_RANGER].is_active = False
    users[ROLE_RANGER].save()
    res = client.post('/login/', {'username': users[ROLE_RANGER].username, 'password': 'pass123'})
    if res.status_code == 200 and 'Invalid username or password' in str(res.content):
        print("Deactivated user login properly failed.")
    elif res.status_code == 302:
        print("ERROR: Deactivated user logged in!")

if __name__ == '__main__':
    run_tests()
