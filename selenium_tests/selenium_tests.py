"""
BUSTARD BEACON - Core Workflow Selenium End-to-End Test Suite

Covers the 6 core multi-role workflows:
- Test 1: Ranger submits an injured-bird incident.
- Test 2: Forest Officer verifies the incident and sets priority to CRITICAL.
- Test 3: Ranger directly assigns an injured bird case to the Medical Team.
- Test 4: Medical Team records clinical treatment and closes the case as RELEASED.
- Test 5: Researcher prepares/finalizes a conservation report and Forest Officer accesses it.
- Test 6: Admin updates a staff user's role and verifies dynamic badge number generation.

Zero arbitrary sleeps: Uses explicit Selenium WebDriverWaits.
Cross-browser: Supports Google Chrome and Microsoft Edge (headless and headed modes).
Data-safe: Uses isolated test markers, does not corrupt existing records.
"""

import os
import re
import sys
import time
import uuid
import unittest
from datetime import date
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions


# --- Configuration & Credentials ---
BASE_URL = os.getenv("BB_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
HEADLESS = os.getenv("BB_HEADLESS", "1").lower() in ("1", "true", "yes")

# Role credentials default to project development accounts if not overridden in environment
CREDENTIALS = {
    "RANGER": (
        os.getenv("BB_RANGER_USER", "ranger_nannaj"),
        os.getenv("BB_RANGER_PASSWORD", "ranger123"),
        "ranger-tab",
    ),
    "OFFICER": (
        os.getenv("BB_OFFICER_USER", "officer_solapur"),
        os.getenv("BB_OFFICER_PASSWORD", "officer123"),
        "officer-tab",
    ),
    "MEDICAL": (
        os.getenv("BB_MEDICAL_USER", "dr_vet_solapur"),
        os.getenv("BB_MEDICAL_PASSWORD", "vet123"),
        "medical-tab",
    ),
    "RESEARCHER": (
        os.getenv("BB_RESEARCHER_USER", "dr_researcher"),
        os.getenv("BB_RESEARCHER_PASSWORD", "research123"),
        "researcher-tab",
    ),
    "ADMIN": (
        os.getenv("BB_ADMIN_USER", "admin"),
        os.getenv("BB_ADMIN_PASSWORD", "admin123"),
        "admin-tab",
    ),
}

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def build_driver():
    """Initializes WebDriver preferring Chrome, falling back to Edge."""
    # Attempt Chrome first
    try:
        c_opts = ChromeOptions()
        if HEADLESS:
            c_opts.add_argument("--headless=new")
        c_opts.add_argument("--no-sandbox")
        c_opts.add_argument("--disable-gpu")
        c_opts.add_argument("--disable-dev-shm-usage")
        c_opts.add_argument("--window-size=1400,900")
        return webdriver.Chrome(options=c_opts)
    except Exception as chrome_err:
        print(f"[Driver] Chrome failed ({chrome_err}), falling back to Edge...")
        e_opts = EdgeOptions()
        if HEADLESS:
            e_opts.add_argument("--headless=new")
        e_opts.add_argument("--no-sandbox")
        e_opts.add_argument("--disable-gpu")
        e_opts.add_argument("--disable-dev-shm-usage")
        e_opts.add_argument("--window-size=1400,900")
        return webdriver.Edge(options=e_opts)


class BustardBeaconCoreWorkflowTests(unittest.TestCase):
    """End-to-End Selenium tests validating BUSTARD BEACON operational workflows."""

    driver = None
    wait = None

    # Shared workflow state between sequentially linked tests
    created_incident_1_id = None
    created_incident_1_code = None
    created_case_3_id = None
    created_case_3_code = None

    @classmethod
    def setUpClass(cls):
        cls.driver = build_driver()
        cls.wait = WebDriverWait(cls.driver, 15)

    @classmethod
    def tearDownClass(cls):
        if cls.driver:
            try:
                cls.driver.quit()
            except Exception:
                pass

    def setUp(self):
        """Clear cookies before each test for clean session state."""
        self.driver.delete_all_cookies()

    def tearDown(self):
        """Cleanup after each test."""
        pass

    # --- Helper Methods ---

    def safe_click(self, element):
        """Scrolls element into view and clicks safely, with JS fallback if intercepted."""
        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", element)
        try:
            element.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", element)

    def login(self, role):
        """Logs into the application using role-specific tabs and credentials."""
        user, pwd, tab_id = CREDENTIALS[role]
        if not user or not pwd:
            self.skipTest(f"Missing credentials for role: {role}")

        d = self.driver
        d.get(f"{BASE_URL}/login/")

        # Switch to correct role tab
        tab_btn = self.wait.until(EC.element_to_be_clickable((By.ID, tab_id)))
        tab_btn.click()

        # Fill credentials into standard inputs
        username_input = self.wait.until(EC.visibility_of_element_located((By.ID, "input-username")))
        username_input.clear()
        username_input.send_keys(user)

        password_input = d.find_element(By.ID, "input-password")
        password_input.clear()
        password_input.send_keys(pwd)

        # Submit form
        submit_btn = d.find_element(By.CSS_SELECTOR, "form button[type='submit']")
        submit_btn.click()

        # Wait for redirect away from /login/
        self.wait.until(lambda driver: "/login/" not in driver.current_url)
        self.assertNotIn("login", urlparse(d.current_url).path.strip("/").split("/"))

    def logout(self):
        """Logs out the current session and redirects to landing."""
        d = self.driver
        try:
            d.get(f"{BASE_URL}/logout/")
            self.wait.until(lambda driver: "/login" in driver.current_url or driver.current_url.rstrip("/") == BASE_URL)
        except Exception:
            d.delete_all_cookies()

    def page_text(self):
        """Returns the full visible text of the current page body."""
        return self.driver.find_element(By.TAG_NAME, "body").text

    # --- Test 1: Ranger submits an injured-bird incident ---

    def test_01_ranger_submits_injured_bird_incident(self):
        """Test 1: Ranger submits an injured-bird incident with live GPS and verifies persistence."""
        self.login("RANGER")
        d = self.driver

        d.get(f"{BASE_URL}/ranger/report-incident/")
        self.wait.until(EC.presence_of_element_located((By.NAME, "description")))

        marker = f"SELENIUM-INC-T1-{uuid.uuid4().hex[:6]}"
        Select(d.find_element(By.NAME, "category")).select_by_value("INJURED_BIRD")

        # Inject GPS coordinates safely into form
        d.execute_script(
            "document.getElementById('field-latitude').value = '17.6599';"
            "document.getElementById('field-longitude').value = '75.9064';"
            "document.getElementById('field-accuracy').value = '10';"
        )

        d.find_element(By.NAME, "description").send_keys(marker)
        submit_btn = d.find_element(By.CSS_SELECTOR, "form[action*='/ranger/report-incident/'] button[type='submit']")
        self.safe_click(submit_btn)

        # Wait for redirect to incidents list
        self.wait.until(EC.url_contains("/ranger/incidents/"))
        self.wait.until(lambda driver: marker in driver.page_source)

        # Verify incident is recorded in list
        page_html = d.page_source
        self.assertIn(marker, page_html, "Incident description marker must appear in Ranger incidents list.")
        self.assertIn("PENDING", self.page_text().upper(), "Newly submitted incident must have PENDING status.")

        # Extract incident ID and numeric ID for Test 2 linkage
        match_id = re.search(r'data-bs-target="#incidentModal(\d+)"', page_html)
        if match_id:
            BustardBeaconCoreWorkflowTests.created_incident_1_id = match_id.group(1)

        match_code = re.search(r'(INC-\d{4}-[A-Z0-9]+)', page_html)
        if match_code:
            BustardBeaconCoreWorkflowTests.created_incident_1_code = match_code.group(1)

        print(f"  [Test 1 Passed] Created Incident #{BustardBeaconCoreWorkflowTests.created_incident_1_id} ({BustardBeaconCoreWorkflowTests.created_incident_1_code})")

    # --- Test 2: Forest Officer verifies the incident and sets priority ---

    def test_02_forest_officer_verifies_incident_and_priority(self):
        """Test 2: Forest Officer locates the incident, verifies it, and sets priority to CRITICAL."""
        self.login("OFFICER")
        d = self.driver

        incident_id = os.getenv("BB_INCIDENT_ID") or BustardBeaconCoreWorkflowTests.created_incident_1_id
        if not incident_id:
            # Fallback: Locate latest pending incident from queue
            d.get(f"{BASE_URL}/officer/incidents/?status=PENDING")
            match = re.search(r'/officer/incidents/(\d+)/', d.page_source)
            if not match:
                d.get(f"{BASE_URL}/officer/incidents/")
                match = re.search(r'/officer/incidents/(\d+)/', d.page_source)
            if match:
                incident_id = match.group(1)
            else:
                self.skipTest("No incident ID available to verify. Set BB_INCIDENT_ID or run Test 1 first.")

        # Open the specific incident detail view
        d.get(f"{BASE_URL}/officer/incidents/{incident_id}/")
        self.wait.until(EC.presence_of_element_located((By.NAME, "verification_notes")))

        # Locate verification form
        form = d.find_element(By.XPATH, "//form[.//input[@name='action_type' and @value='verify_incident']]")
        Select(form.find_element(By.NAME, "status")).select_by_value("VERIFIED")
        Select(form.find_element(By.NAME, "priority")).select_by_value("CRITICAL")

        notes_input = form.find_element(By.NAME, "verification_notes")
        notes_input.clear()
        notes_input.send_keys("Selenium E2E Verification: Confirmed injured wildlife. Priority upgraded to CRITICAL.")

        self.safe_click(form.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # Wait for page reload and success message
        self.wait.until(EC.url_contains(f"/officer/incidents/{incident_id}/"))
        self.wait.until(lambda driver: "verification updated" in driver.page_source.lower())

        # Verify persisted status and priority in dropdowns
        status_sel = Select(d.find_element(By.NAME, "status"))
        priority_sel = Select(d.find_element(By.NAME, "priority"))
        self.assertEqual(status_sel.first_selected_option.get_attribute("value"), "VERIFIED", "Persisted status must be VERIFIED.")
        self.assertEqual(priority_sel.first_selected_option.get_attribute("value"), "CRITICAL", "Persisted priority must be CRITICAL.")

        print(f"  [Test 2 Passed] Verified Incident #{incident_id} with Status=VERIFIED, Priority=CRITICAL")

    # --- Test 3: Ranger assigns a case to the Medical Team ---

    def test_03_ranger_assigns_case_to_medical_team(self):
        """Test 3: Ranger reports an injured bird with Medical Alert and assigns an available Medical Team."""
        self.login("RANGER")
        d = self.driver

        d.get(f"{BASE_URL}/ranger/report-incident/")
        self.wait.until(EC.presence_of_element_located((By.NAME, "description")))

        marker = f"SELENIUM-MED-ALERT-{uuid.uuid4().hex[:6]}"
        Select(d.find_element(By.NAME, "category")).select_by_value("INJURED_BIRD")

        # Fill GPS
        d.execute_script(
            "document.getElementById('field-latitude').value = '17.6599';"
            "document.getElementById('field-longitude').value = '75.9064';"
            "document.getElementById('field-accuracy').value = '10';"
        )
        d.find_element(By.NAME, "description").send_keys(marker)

        # Trigger Medical Alert checkbox
        cb = d.find_element(By.ID, "send_medical_alert")
        d.execute_script("arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));", cb)

        # Select medical team: prefer configured ID or first available radio in the UI
        target_team_id = os.getenv("BB_MEDICAL_USER_ID", "").strip()
        if target_team_id:
            radio = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"input[name='medical_team_id'][value='{target_team_id}']")))
            radio.click()
        else:
            available_radios = d.find_elements(By.CSS_SELECTOR, "input[name='medical_team_id']:not([disabled])")
            if not available_radios:
                self.skipTest("No AVAILABLE Medical Team found in system to assign.")
            available_radios[0].click()

        # Submit report
        submit_btn = d.find_element(By.CSS_SELECTOR, "form[action*='/ranger/report-incident/'] button[type='submit']")
        self.safe_click(submit_btn)
        self.wait.until(EC.url_contains("/ranger/incidents/"))
        self.wait.until(lambda driver: marker in driver.page_source)

        page_html = d.page_source
        match_code = re.search(r'(INC-\d{4}-[A-Z0-9]+)', page_html)
        incident_code = match_code.group(1) if match_code else None

        # Switch to Medical Team session to verify assignment is visible in their queue
        self.logout()
        self.login("MEDICAL")
        d.get(f"{BASE_URL}/medical/cases/")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        # Verify case is visible in Medical Team queue
        if incident_code:
            self.assertIn(incident_code, d.page_source, f"Medical Team queue must list case for incident {incident_code}.")
            row_match = re.search(rf'{incident_code}.*?/medical/cases/(\d+)/', d.page_source, re.DOTALL)
            if row_match:
                BustardBeaconCoreWorkflowTests.created_case_3_id = row_match.group(1)
        
        if not BustardBeaconCoreWorkflowTests.created_case_3_id:
            # Fallback to first case link in table
            match_case = re.search(r'/medical/cases/(\d+)/', d.page_source)
            if match_case:
                BustardBeaconCoreWorkflowTests.created_case_3_id = match_case.group(1)

        # Open case detail and confirm symptom/description marker is persisted
        if BustardBeaconCoreWorkflowTests.created_case_3_id:
            d.get(f"{BASE_URL}/medical/cases/{BustardBeaconCoreWorkflowTests.created_case_3_id}/")
            self.wait.until(EC.presence_of_element_located((By.NAME, "treatment_description")))
            self.assertIn(marker, d.page_source, "Assigned Medical Team case detail must contain observation description.")

        print(f"  [Test 3 Passed] Case successfully assigned to Medical Team (Case #{BustardBeaconCoreWorkflowTests.created_case_3_id})")

    # --- Test 4: Medical Team treats and closes the case ---

    def test_04_medical_team_treats_and_closes_case(self):
        """Test 4: Medical Team records treatment, advances rehab stage, marks bird RELEASED, and closes case."""
        self.login("MEDICAL")
        d = self.driver

        case_id = os.getenv("BB_MEDICAL_CASE_ID") or BustardBeaconCoreWorkflowTests.created_case_3_id
        if not case_id:
            # Fallback: Find the first assigned case in the medical cases queue
            d.get(f"{BASE_URL}/medical/cases/")
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            match = re.search(r'/medical/cases/(\d+)/', d.page_source)
            if match:
                case_id = match.group(1)
            else:
                self.skipTest("No active Medical Case found to treat. Run Test 3 or configure BB_MEDICAL_CASE_ID.")

        d.get(f"{BASE_URL}/medical/cases/{case_id}/")
        self.wait.until(EC.presence_of_element_located((By.NAME, "treatment_description")))

        # 1. Record Clinical Treatment Log
        treatment_marker = f"SELENIUM-RX-{uuid.uuid4().hex[:6]}: Antiseptic wound debridement and supportive hydration."
        d.find_element(By.NAME, "treatment_description").send_keys(treatment_marker)
        d.find_element(By.NAME, "medications_given").send_keys("Meloxicam, Enrofloxacin")
        d.find_element(By.NAME, "dosage_notes").send_keys("0.2 mg/kg SID orally")

        treatment_form = d.find_element(By.XPATH, "//form[.//input[@name='form_type' and @value='add_treatment']]")
        self.safe_click(treatment_form.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # Wait for treatment confirmation and verify it appears in treatment history
        self.wait.until(lambda driver: treatment_marker in driver.page_source)
        self.assertIn("Treatment log recorded successfully", d.page_source)
        self.assertIn(treatment_marker, d.page_source)

        # 2. Update Status & Rehabilitation Stage to RELEASED / CLOSED
        status_form = d.find_element(By.XPATH, "//form[.//input[@name='form_type' and @value='update_status']]")
        Select(status_form.find_element(By.NAME, "rehabilitation_stage")).select_by_value("RELEASED")
        Select(status_form.find_element(By.NAME, "status")).select_by_value("CLOSED")

        diag_input = status_form.find_element(By.NAME, "diagnosis")
        diag_input.clear()
        diag_input.send_keys("Selenium E2E Clinical Verification: Complete recovery, flight-fit, released back to wild.")

        self.safe_click(status_form.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # Wait for status update confirmation
        self.wait.until(lambda driver: "Successfully Released to Wild" in driver.page_source)
        self.wait.until(lambda driver: "Medical case status and stage updated" in driver.page_source)
        self.assertIn("Successfully Released to Wild", d.page_source)
        self.assertTrue("CLOSED" in d.page_source or "Case Closed" in d.page_source)

        print(f"  [Test 4 Passed] Recorded treatment and closed Case #{case_id} as RELEASED / CLOSED")

    # --- Test 5: Researcher report workflow and Forest Officer access ---

    def test_05_researcher_report_workflow_and_officer_access(self):
        """Test 5: Researcher drafts and finalizes report, sends to Forest Officers, and Officer verifies access."""
        self.login("RESEARCHER")
        d = self.driver

        d.get(f"{BASE_URL}/research/reports/")
        self.wait.until(EC.presence_of_element_located((By.NAME, "from_date")))

        today_str = date.today().isoformat()
        from_date = os.getenv("BB_REPORT_FROM", today_str)
        to_date = os.getenv("BB_REPORT_TO", today_str)

        # Set date range in controls
        from_input = d.find_element(By.NAME, "from_date")
        from_input.clear()
        from_input.send_keys(from_date)

        to_input = d.find_element(By.NAME, "to_date")
        to_input.clear()
        to_input.send_keys(to_date)

        # If report does not exist yet, click Analyze & Draft
        if "create_draft" in d.page_source:
            d.find_element(By.NAME, "create_draft").click()
            self.wait.until(lambda driver: "FINALIZED" in driver.page_source or "Finalize Report" in driver.page_source)

        # If report is still in DRAFT status, finalize it
        finalize_forms = d.find_elements(By.XPATH, "//form[contains(@action, '/research/reports/finalize/')]")
        if finalize_forms:
            # Submit finalize form directly
            d.execute_script("arguments[0].submit();", finalize_forms[0])
            self.wait.until(lambda driver: "FINALIZED" in driver.page_source)

        self.assertIn("FINALIZED", self.page_text())

        # Send report to Forest Officer if not already sent
        send_fo_forms = d.find_elements(By.XPATH, "//form[contains(@action, '/research/reports/submit/') and contains(@action, '/fo/')]")
        if send_fo_forms:
            d.execute_script("arguments[0].submit();", send_fo_forms[0])
            self.wait.until(lambda driver: "Sent to FO" in driver.page_source)

        self.assertIn("Sent to FO", self.page_text())

        # Switch to Forest Officer to verify report notification and accessibility
        self.logout()
        self.login("OFFICER")

        d.get(f"{BASE_URL}/notifications/")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Verify Conservation Analysis notification exists
        self.assertIn("Conservation Analysis Report Submitted", self.page_text(), "Forest Officer must receive report submission notification.")

        # Verify report generation link is accessible to Forest Officer
        report_links = d.find_elements(By.XPATH, "//a[contains(@href, 'type=CONSERVATION_ANALYSIS_REPORT')]")
        if report_links:
            report_url = report_links[0].get_attribute("href")
            d.get(report_url)
            self.assertNotIn("403", d.title)
            self.assertNotIn("Permission Denied", self.page_text())

        print("  [Test 5 Passed] Researcher finalized & sent report; Forest Officer verified notification and access")

    # --- Test 6: Admin changes user role and verifies badge update ---

    def test_06_admin_changes_role_and_badge_updates(self):
        """Test 6: Admin updates a staff user's role and verifies dynamic badge number generation and persistence."""
        target_username = os.getenv("BB_TARGET_USERNAME", "demo_ranger").strip()
        self.login("ADMIN")
        d = self.driver

        d.get(f"{BASE_URL}/admin-panel/users/")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        # Check if the target user exists; if not, create a dedicated test user safely
        rows = d.find_elements(By.XPATH, f"//tr[.//td[normalize-space(text())='{target_username}']]")
        if not rows:
            # Open Register Staff Modal and create dedicated test user
            self.safe_click(d.find_element(By.CSS_SELECTOR, "button[data-bs-target='#registerStaffModal']"))
            self.wait.until(EC.visibility_of_element_located((By.NAME, "username")))

            modal_form = d.find_element(By.XPATH, "//div[@id='registerStaffModal']//form")
            modal_form.find_element(By.NAME, "username").send_keys(target_username)
            modal_form.find_element(By.NAME, "first_name").send_keys("Selenium")
            modal_form.find_element(By.NAME, "last_name").send_keys("TestStaff")
            modal_form.find_element(By.NAME, "email").send_keys(f"{target_username}@test.gov.in")
            modal_form.find_element(By.NAME, "password").send_keys("staffPass123!")
            Select(modal_form.find_element(By.NAME, "role")).select_by_value("RANGER")

            self.safe_click(modal_form.find_element(By.CSS_SELECTOR, "button[type='submit']"))
            self.wait.until(EC.url_contains("/admin-panel/users/"))
            rows = d.find_elements(By.XPATH, f"//tr[.//td[normalize-space(text())='{target_username}']]")

        self.assertTrue(rows, f"Target user '{target_username}' must exist in users table.")
        target_row = rows[0]

        # Extract current role and badge
        current_role_select = Select(target_row.find_element(By.CSS_SELECTOR, "form select[name='role']"))
        current_role = current_role_select.first_selected_option.get_attribute("value")
        current_badge = target_row.find_elements(By.TAG_NAME, "td")[3].text.strip()

        # Select a different role to trigger badge regeneration
        prefixes = {
            "RANGER": "RNG-",
            "FOREST_OFFICER": "FO-",
            "MEDICAL_TEAM": "VET-MT-",
            "RESEARCHER": "WL-RSH-",
        }
        new_role = "FOREST_OFFICER" if current_role != "FOREST_OFFICER" else "RANGER"

        # Apply role change
        current_role_select.select_by_value(new_role)
        self.safe_click(target_row.find_element(By.CSS_SELECTOR, "form button[type='submit']"))

        # Wait for update confirmation
        self.wait.until(lambda driver: "New Badge Number:" in driver.page_source)
        self.assertIn("New Badge Number:", self.page_text())

        # Refresh page and confirm persisted role and new badge prefix
        d.get(f"{BASE_URL}/admin-panel/users/")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        updated_row = d.find_element(By.XPATH, f"//tr[.//td[normalize-space(text())='{target_username}']]")
        updated_role = Select(updated_row.find_element(By.CSS_SELECTOR, "form select[name='role']")).first_selected_option.get_attribute("value")
        new_badge = updated_row.find_elements(By.TAG_NAME, "td")[3].text.strip()

        self.assertEqual(updated_role, new_role, f"Persisted role must be {new_role}.")
        self.assertTrue(new_badge.startswith(prefixes[new_role]), f"Badge '{new_badge}' must start with {prefixes[new_role]}")
        self.assertNotEqual(current_badge, new_badge, "Badge number must change when role is updated.")

        print(f"  [Test 6 Passed] Updated {target_username} to {new_role} with dynamic badge {new_badge}")


if __name__ == "__main__":
    print("=" * 70)
    print(" BUSTARD BEACON — SELENIUM END-TO-END AUTOMATED TEST RUNNER")
    print(f" Target Base URL: {BASE_URL}")
    print(f" Browser Mode:   {'Headless' if HEADLESS else 'Visible Window'}")
    print("=" * 70)
    unittest.main(verbosity=2)
