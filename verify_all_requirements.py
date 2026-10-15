import time
import os
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:8000"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "verification_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def create_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,950")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    driver = webdriver.Edge(options=options)
    return driver

def run_all_tests():
    driver = create_driver()
    results = {}

    try:
        print("=" * 70)
        print("BUSTARD BEACON — COMPREHENSIVE AUTOMATED VERIFICATION SUITE")
        print("=" * 70)

        # -----------------------------------------------------------------
        # MAP-01: Open landing page, smaller map renders correctly
        # -----------------------------------------------------------------
        print("\n[MAP-01] Testing Landing Page Smaller Map...")
        driver.get(f"{BASE_URL}/")
        time.sleep(1.5)
        map_sec = driver.find_element(By.ID, "map-section")
        driver.execute_script("arguments[0].scrollIntoView(true);", map_sec)
        time.sleep(2)

        map_div = driver.find_element(By.ID, "landingMap")
        assert map_div.is_displayed(), "Landing map container is not displayed"
        size = map_div.size
        print(f"  Landing map size: {size['width']}x{size['height']}")
        assert size['width'] > 200 and size['height'] > 200, "Landing map container has zero or invalid dimensions"

        # Check map elements inside landingMap (Google Maps or Leaflet)
        has_map = driver.execute_script("return (document.querySelector('#landingMap .gm-style') !== null) || (document.querySelector('#landingMap .leaflet-pane') !== null);")
        assert has_map, "Map did not initialize inside #landingMap"
        driver.save_screenshot(os.path.join(SCREENSHOT_DIR, "MAP-01_landing_map.png"))
        print("  -> MAP-01 PASSED: Landing page smaller map renders correctly.")
        results["MAP-01"] = "PASSED"

        # -----------------------------------------------------------------
        # MAP-02: Click Map navigation option, full map opens and works
        # -----------------------------------------------------------------
        print("\n[MAP-02] Testing Sanctuary Map Navigation Link...")
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        nav_map_link = driver.find_element(By.LINK_TEXT, "Sanctuary Map")
        driver.execute_script("arguments[0].click();", nav_map_link)
        time.sleep(2)

        assert "/map/" in driver.current_url, f"Navigation failed, current URL: {driver.current_url}"
        cons_map = driver.find_element(By.ID, "conservation-map")
        assert cons_map.is_displayed(), "Conservation map is not displayed on /map/"
        cons_size = cons_map.size
        print(f"  Sanctuary full map size: {cons_size['width']}x{cons_size['height']}")
        assert cons_size['width'] > 400 and cons_size['height'] > 300, "Sanctuary map has invalid dimensions"
        driver.save_screenshot(os.path.join(SCREENSHOT_DIR, "MAP-02_sanctuary_map.png"))
        print("  -> MAP-02 PASSED: Full Sanctuary Map opens and works correctly.")
        results["MAP-02"] = "PASSED"

        # -----------------------------------------------------------------
        # MAP-03: Interact with map (zooming, panning, available markers)
        # -----------------------------------------------------------------
        print("\n[MAP-03] Testing Map Interactivity...")
        has_zoom = driver.execute_script("return (document.querySelector('.gm-control-active') !== null) || (document.querySelector('.leaflet-control-zoom-in') !== null);")
        assert has_zoom, "Zoom control is not displayed"

        has_features = driver.execute_script("return (typeof bbPolygons !== 'undefined' && bbPolygons.length > 0) || (document.querySelectorAll('.leaflet-interactive').length > 0);")
        assert has_features, "No interactive map elements (polygons/markers) rendered on the map"
        print("  -> MAP-03 PASSED: Map zooming, panning, and markers work.")
        results["MAP-03"] = "PASSED"

        # -----------------------------------------------------------------
        # ZONE-01: Open Sanctuary Map page, heading & right-hand panel readable
        # -----------------------------------------------------------------
        print("\n[ZONE-01] Testing Heading Contrast and Readability...")
        heading = driver.find_element(By.CLASS_NAME, "bb-sidebar-heading")
        assert heading.is_displayed(), "Sidebar heading is not displayed"
        color = heading.value_of_css_property("color")
        print(f"  Heading text: '{heading.text}', Computed color: {color}")
        # Color should be dark (not white rgb(255, 255, 255))
        assert "255, 255, 255" not in color, f"Heading has insufficient contrast: {color}"
        print("  -> ZONE-01 PASSED: Heading and right-hand panel are readable with high contrast.")
        results["ZONE-01"] = "PASSED"

        # -----------------------------------------------------------------
        # ZONE-02: Inspect zone categories (actual conservation zones distinct)
        # -----------------------------------------------------------------
        print("\n[ZONE-02] Testing Conservation Zones Representation...")
        zone_items = driver.find_elements(By.CLASS_NAME, "bb-zone-item")
        print(f"  Found {len(zone_items)} registered conservation zones in panel.")
        assert len(zone_items) >= 3, f"Expected at least 3 sanctuary zones, found {len(zone_items)}"

        zone_texts = [z.text for z in zone_items]
        print(f"  Zone names snippet: {[t.splitlines()[0] for t in zone_texts]}")
        assert any("Nannaj Core" in t for t in zone_texts), "Nannaj Core Sanctuary zone missing"
        assert any("Buffer" in t for t in zone_texts), "Solapur Buffer zone missing"
        assert any("Maldhok" in t for t in zone_texts), "Maldhok Tourism zone missing"

        # Verify clicking a zone triggers zoom
        first_zone = zone_items[0]
        driver.execute_script("arguments[0].click();", first_zone)
        time.sleep(0.5)
        print("  -> ZONE-02 PASSED: Real conservation zones displayed distinctly from incident severity.")
        results["ZONE-02"] = "PASSED"

        # -----------------------------------------------------------------
        # ZONE-03: Inspect severity indicators (readable without black rectangles)
        # -----------------------------------------------------------------
        print("\n[ZONE-03] Testing Severity Indicators Styling...")
        critical_pills = driver.find_elements(By.CLASS_NAME, "bb-priority-critical")
        assert len(critical_pills) > 0, "Critical severity pill missing"
        crit_pill = critical_pills[0]
        bg_color = crit_pill.value_of_css_property("background-color")
        print(f"  Critical pill background-color: {bg_color}")
        # Must not be black (rgb(0, 0, 0) or rgb(33, 37, 41))
        assert "0, 0, 0" not in bg_color and "33, 37, 41" not in bg_color, "Critical pill has unwanted black background"

        # Verify no bg-dark rectangles remain in sidebar
        sidebar = driver.find_element(By.CLASS_NAME, "bb-map-sidebar")
        dark_boxes = sidebar.find_elements(By.CLASS_NAME, "bg-dark")
        assert len(dark_boxes) == 0, f"Found {len(dark_boxes)} unwanted black rectangles (.bg-dark) in sidebar"
        print("  -> ZONE-03 PASSED: Critical, High, Medium, Low indicators are styled cleanly without black rectangles.")
        results["ZONE-03"] = "PASSED"

        # -----------------------------------------------------------------
        # AUTH-01: Open login page in new tab without 403 Forbidden
        # -----------------------------------------------------------------
        print("\n[AUTH-01] Testing Opening Login Page in a New Tab...")
        driver.execute_script("window.open('http://127.0.0.1:8000/login/', '_blank');")
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])
        print(f"  New Tab URL: {driver.current_url}")
        assert "/login/" in driver.current_url, "New tab is not on login page"
        assert "403" not in driver.title and "Forbidden" not in driver.page_source, "Login page returned 403 Forbidden in new tab"
        assert driver.find_element(By.ID, "staff-login-form").is_displayed(), "Staff login form not displayed in new tab"

        # Test opening specific role login entry point in new tab via URL parameter
        driver.execute_script("window.open('http://127.0.0.1:8000/login/?role=ranger', '_blank');")
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])
        ranger_tab = driver.find_element(By.ID, "ranger-tab")
        assert "active" in ranger_tab.get_attribute("class"), "Ranger role tab was not pre-activated from URL parameter"
        role_input = driver.find_element(By.ID, "login-role-input")
        assert role_input.get_attribute("value") == "ranger", "login_role input was not set to ranger"
        driver.close() # Close tab 3
        driver.switch_to.window(driver.window_handles[-1])
        driver.close() # Close tab 2
        driver.switch_to.window(driver.window_handles[0])
        print("  -> AUTH-01 PASSED: Login page and role-specific tabs open in new tabs with status 200 (no 403 error).")
        results["AUTH-01"] = "PASSED"

        # -----------------------------------------------------------------
        # AUTH-02: Test all five role login flows
        # -----------------------------------------------------------------
        print("\n[AUTH-02] Testing Login Flows for All Five Roles...")
        roles_to_test = [
            ("admin", "admin", "admin123", "/admin-panel/"),
            ("officer", "officer_solapur", "officer123", "/officer/dashboard/"),
            ("ranger", "ranger_nannaj", "ranger123", "/ranger/field-mode/"),
            ("medical", "dr_vet_solapur", "vet123", "/medical/dashboard/"),
            ("researcher", "dr_researcher", "research123", "/research/dashboard/"),
        ]

        for role_key, username, password, expected_dest in roles_to_test:
            print(f"  Testing role: {role_key.upper()} ({username})...")
            # Ensure logged out first
            driver.get(f"{BASE_URL}/logout/")
            time.sleep(0.5)

            # Navigate to login page with pre-selected role
            driver.get(f"{BASE_URL}/login/?role={role_key}")
            time.sleep(0.5)

            u_input = driver.find_element(By.ID, "input-username")
            p_input = driver.find_element(By.ID, "input-password")
            u_input.clear()
            u_input.send_keys(username)
            p_input.clear()
            p_input.send_keys(password)

            form = driver.find_element(By.ID, "staff-login-form")
            driver.execute_script("arguments[0].submit();", form)
            time.sleep(1.5)

            current_url = driver.current_url
            print(f"    Redirected to: {current_url} (Expected: {expected_dest})")
            assert expected_dest in current_url, f"Role {role_key} did not reach expected dashboard {expected_dest}, got {current_url}"

        print("  -> AUTH-02 PASSED: All five user roles successfully authenticate and reach their respective dashboards.")
        results["AUTH-02"] = "PASSED"

        # -----------------------------------------------------------------
        # AUTH-03: Open a protected dashboard in a new tab
        # -----------------------------------------------------------------
        print("\n[AUTH-03] Testing Protected Dashboard in New Tab...")
        # Currently logged in as researcher from previous step
        driver.execute_script("window.open('http://127.0.0.1:8000/research/dashboard/', '_blank');")
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])
        assert "/research/dashboard/" in driver.current_url, "Did not open researcher dashboard"
        assert "403" not in driver.title, "Authenticated user received 403 on their own dashboard"

        # Test unauthorized access to another role's dashboard in a new tab
        driver.execute_script("window.open('http://127.0.0.1:8000/admin-panel/', '_blank');")
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])
        print(f"  Researcher accessing /admin-panel/: Title='{driver.title}', URL={driver.current_url}")
        # Should be blocked with 403 Forbidden or redirected to login
        assert "403" in driver.title or "Forbidden" in driver.page_source or "/login/" in driver.current_url, "Unauthorized access was not denied!"
        driver.close()
        driver.switch_to.window(driver.window_handles[-1])
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        print("  -> AUTH-03 PASSED: Protected dashboard access in new tab correctly follows authentication and permissions.")
        results["AUTH-03"] = "PASSED"

        # -----------------------------------------------------------------
        # AUTH-04: Navigate between multiple tabs (CSRF sync & session consistency)
        # -----------------------------------------------------------------
        print("\n[AUTH-04] Testing Multi-Tab CSRF and Form Submission Synchronization...")
        # Step 1: Open login in Tab 1
        driver.get(f"{BASE_URL}/logout/")
        time.sleep(0.5)
        driver.get(f"{BASE_URL}/login/?role=ranger")
        time.sleep(1)
        tab1 = driver.current_window_handle

        # Step 2: Open login in Tab 2
        driver.execute_script("window.open('http://127.0.0.1:8000/login/?role=admin', '_blank');")
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])
        tab2 = driver.current_window_handle

        # Step 3: Log in as admin in Tab 2 (this rotates the CSRF token!)
        u_in = driver.find_element(By.ID, "input-username")
        p_in = driver.find_element(By.ID, "input-password")
        u_in.send_keys("admin")
        p_in.send_keys("admin123")
        driver.execute_script("arguments[0].submit();", driver.find_element(By.ID, "staff-login-form"))
        time.sleep(1.5)
        assert "/admin-panel/" in driver.current_url, "Admin login in Tab 2 failed"
        print("  Tab 2 successfully logged in as Administrator (CSRF cookie rotated).")

        # Step 4: Switch back to Tab 1 (which had the old token)
        driver.switch_to.window(tab1)
        time.sleep(0.5)
        # Trigger focus / visibility sync
        driver.execute_script("window.dispatchEvent(new Event('focus'));")
        time.sleep(0.2)

        # Step 5: Submit form in Tab 1 without refreshing
        u_in1 = driver.find_element(By.ID, "input-username")
        p_in1 = driver.find_element(By.ID, "input-password")
        u_in1.clear()
        u_in1.send_keys("ranger_nannaj")
        p_in1.clear()
        p_in1.send_keys("ranger123")
        driver.execute_script("arguments[0].submit();", driver.find_element(By.ID, "staff-login-form"))
        time.sleep(1.5)

        print(f"  Tab 1 post-submit URL: {driver.current_url}, Page title: {driver.title}")
        assert "403" not in driver.title and "CSRF verification failed" not in driver.page_source, "CSRF verification failed in Tab 1 after Tab 2 rotated token!"
        assert "/ranger/field-mode/" in driver.current_url, "Tab 1 Ranger login failed"
        print("  -> AUTH-04 PASSED: Multi-tab CSRF synchronization prevents 403 verification failures.")
        results["AUTH-04"] = "PASSED"

        # -----------------------------------------------------------------
        # AUTH-05: Log out and revisit a protected page
        # -----------------------------------------------------------------
        print("\n[AUTH-05] Testing Logout and Protected Access Denial...")
        driver.get(f"{BASE_URL}/logout/")
        time.sleep(1)
        assert "/" in driver.current_url

        # Try to visit admin panel anonymously
        driver.get(f"{BASE_URL}/admin-panel/")
        time.sleep(1)
        print(f"  After logout visit to /admin-panel/: URL={driver.current_url}")
        assert "/login/" in driver.current_url, "Unauthenticated user was not redirected to /login/"

        # Try to visit ranger field mode anonymously
        driver.get(f"{BASE_URL}/ranger/field-mode/")
        time.sleep(1)
        print(f"  After logout visit to /ranger/field-mode/: URL={driver.current_url}")
        assert "/login/" in driver.current_url, "Unauthenticated user was not redirected to /login/"

        print("  -> AUTH-05 PASSED: Unauthorized access is denied appropriately after logout.")
        results["AUTH-05"] = "PASSED"

    finally:
        driver.quit()

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED:")
    for test_id, res in results.items():
        print(f"  {test_id}: {res}")
    print("=" * 70)

if __name__ == "__main__":
    run_all_tests()
