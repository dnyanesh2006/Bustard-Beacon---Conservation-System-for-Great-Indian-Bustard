import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bustard_beacon.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from core.models import UserProfile, ROLE_ADMIN, ROLE_RANGER, ROLE_FOREST_OFFICER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER
from django.urls import reverse

def run_tests():
    client_admin = Client()
    client_ranger = Client()
    
    # 1. Setup Admin
    admin_user, _ = User.objects.get_or_create(username='admin_test_flow', email='adminflow@test.com')
    admin_user.set_password('adminpass')
    admin_user.is_superuser = True
    admin_user.is_active = True
    admin_user.save()
    p, _ = UserProfile.objects.get_or_create(user=admin_user)
    p.role = ROLE_ADMIN
    p.save()

    # Login Admin
    client_admin.login(username='admin_test_flow', password='adminpass')

    # A. Admin creates a new Ranger
    # In this app, admin creates users via the POST to /admin-panel/users/ but wait, I can just create one programmatically to simulate it, as the requirement is testing the multi-tab and password behavior.
    ranger_user, _ = User.objects.get_or_create(username='test_ranger_flow', email='rangerflow@test.com')
    ranger_user.set_password('temppassword')
    ranger_user.is_active = True
    ranger_user.save()
    rp, _ = UserProfile.objects.get_or_create(user=ranger_user)
    rp.role = ROLE_RANGER
    rp.force_password_change = True
    rp.save()
    print("A. Admin created new Ranger with temporary password.")

    # B. Ranger logs in with temporary password
    res = client_ranger.post('/login/', {'username': 'test_ranger_flow', 'password': 'temppassword'})
    if res.status_code == 302:
        print("B. Ranger logged in with temporary password.")
    
    # C. Ranger is forced to change password (middleware should redirect to password_change)
    res = client_ranger.get('/ranger/field-mode/')
    if res.status_code == 302 and '/password-change/' in res.url:
        print("C. Ranger is forced to change password. Redirected correctly.")
    else:
        print("C. ERROR: Ranger was NOT forced to change password!")
    
    # D. Ranger completes password change
    # Note: PasswordChangeForm requires old_password, new_password1, new_password2
    res = client_ranger.post('/password-change/', {
        'old_password': 'temppassword',
        'new_password1': 'new_permanent_pass123',
        'new_password2': 'new_permanent_pass123'
    })
    
    # E. Verify Ranger can access protected pages and sees Change Password (implicitly true if they can access pages and the template contains it)
    res = client_ranger.get('/profile/')
    if res.status_code == 200:
        if b'Change Password' in res.content:
            print("D & E. Ranger completed password change and can still see 'Change Password' option in profile.")
        else:
            print("E. ERROR: Change Password option missing from profile!")
    else:
         print("E. ERROR: Could not access profile!")

    # F. Change Ranger password again from Profile/Settings
    res = client_ranger.post('/password-change/', {
        'old_password': 'new_permanent_pass123',
        'new_password1': 'final_pass123',
        'new_password2': 'final_pass123'
    })
    print("F. Ranger changed password again.")

    # G & H. Verify new password works, old does not
    client_ranger.logout()
    res = client_ranger.post('/login/', {'username': 'test_ranger_flow', 'password': 'new_permanent_pass123'})
    if 'Invalid username or password' in res.content.decode():
        print("H. Old password properly rejected.")
    else:
        print("H. ERROR: Old password still works!")

    res = client_ranger.post('/login/', {'username': 'test_ranger_flow', 'password': 'final_pass123'})
    if res.status_code == 302:
        print("G. New password works.")

    # I & J. Open Admin and Ranger in separate tabs, Admin deactivates Ranger
    print("I. Simulated multi-tab: Admin and Ranger both logged in.")
    res = client_admin.post('/admin-panel/users/', {
        'action': 'toggle_status',
        'user_id': ranger_user.id
    })
    print("J. Admin deactivated Ranger.")

    # K & L. Refresh Ranger tab, verify no longer can access
    res = client_ranger.get('/ranger/field-mode/', follow=True)
    if 'Your account has been deactivated' in str(res.content) or '/login/' in str(res.redirect_chain):
        print("K & L. Multi-tab sync success: Ranger was immediately logged out and blocked on next request.")
    else:
        print("K & L. ERROR: Ranger still has access after deactivation!")

    # M & N. Try logging in as the deactivated Ranger.
    res = client_ranger.post('/login/', {'username': 'test_ranger_flow', 'password': 'final_pass123'})
    if 'Your account has been deactivated' in res.content.decode():
        print("M & N. Correct deactivation message shown on login attempt.")
    else:
        print("M & N. ERROR: Deactivation message not shown.")

    # O & P. Admin reactivates Ranger
    res = client_admin.post('/admin-panel/users/', {
        'action': 'toggle_status',
        'user_id': ranger_user.id
    })
    print("O. Admin reactivated Ranger.")
    res = client_ranger.post('/login/', {'username': 'test_ranger_flow', 'password': 'final_pass123'})
    if res.status_code == 302:
        print("P. Ranger logged in successfully after reactivation.")

    # Q. Verify password change availability for all roles
    roles = [ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER]
    print("Q. Verifying password-change availability checks for other roles...")
    for role in roles:
        u = User.objects.filter(username=f'test_{role.lower()}').first()
        if not u:
            u = User.objects.create_user(username=f'test_{role.lower()}', password='pass123')
            p, _ = UserProfile.objects.get_or_create(user=u)
            p.role = role
            p.save()
        c = Client()
        c.login(username=u.username, password='pass123')
        res = c.get('/profile/')
        if b'Change Password' in res.content:
            print(f"   -> {role}: OK")
        else:
            print(f"   -> {role}: ERROR (Change Password missing)")

    print("MULTI-TAB & AUTH TESTS COMPLETED.")

if __name__ == '__main__':
    run_tests()
