# BUSTARD BEACON — Selenium End-to-End Automated Testing Suite

Comprehensive, reliable Selenium WebDriver end-to-end testing suite for the **BUSTARD BEACON** Grassland Conservation Platform. This suite validates all six core cross-functional workflows across the platform's role-based operational architecture (Ranger, Forest Officer, Medical Team, Researcher, and Administrator).

---

## 1. Directory Structure

The testing suite resides in `selenium_tests/` alongside `manage.py`:

```
d:/Bustard Beaccon/
├── manage.py
├── bustard_beacon/
├── core/
├── selenium_tests/
│   ├── selenium_tests.py          # Complete 6-workflow Selenium test suite
│   ├── requirements-selenium.txt  # Python testing dependencies
│   ├── README_SELENIUM.md         # Setup, execution, documentation, faculty guide
│   └── screenshots/               # Directory for failure diagnostic screenshots
```

---

## 2. Core Architecture & Design Principles

- **No Application Changes**: Tests run directly against the unaltered Django production/development code, models, views, templates, permissions, and database schemas.
- **Data Safety & Integrity**: Tests use unique timestamps/UUID markers (`SELENIUM-INC-T1-...`, `SELENIUM-MED-ALERT-...`, `SELENIUM-RX-...`), avoiding collisions or corruption of real records.
- **Zero Arbitrary Sleeps**: Uses explicit Selenium `WebDriverWait` conditions (`element_to_be_clickable`, `visibility_of_element_located`, `url_contains`, custom predicates) rather than fragile `time.sleep()` calls.
- **Cross-Browser & Multi-Mode**: Automatically attempts Google Chrome first, falling back to Microsoft Edge if Chrome is not detected. Supports both **Headless** (default/fast) and **Visible Browser** (for faculty demos).
- **Safe Element Interaction (`safe_click`)**: Intercepts scrolling and viewport occlusion with automated scroll-into-view and JavaScript execution fallback, preventing `ElementClickInterceptedException`.
- **Sequential Workflow Linking with Standalone Capability**: Test 1 feeds its created incident into Test 2, and Test 3 feeds its created medical case into Test 4. If tests are executed individually, intelligent UI queue fallbacks and environment variable overrides are supported.

---

## 3. Test Accounts & Credentials

The test suite reads credentials from environment variables, falling back to the standard development credentials documented in `DEVELOPMENT_CREDENTIALS.md`:

| Role | Environment User Var | Environment Password Var | Default Username | Default Password | Initial Landing View |
|---|---|---|---|---|---|
| **Field Ranger** | `BB_RANGER_USER` | `BB_RANGER_PASSWORD` | `ranger_nannaj` | `ranger123` | `/ranger/field-mode/` |
| **Forest Officer** | `BB_OFFICER_USER` | `BB_OFFICER_PASSWORD` | `officer_solapur` | `officer123` | `/officer/dashboard/` |
| **Medical Team** | `BB_MEDICAL_USER` | `BB_MEDICAL_PASSWORD` | `dr_vet_solapur` | `vet123` | `/medical/dashboard/` |
| **Researcher** | `BB_RESEARCHER_USER` | `BB_RESEARCHER_PASSWORD` | `dr_researcher` | `research123` | `/research/dashboard/` |
| **Administrator** | `BB_ADMIN_USER` | `BB_ADMIN_PASSWORD` | `admin` | `admin123` | `/admin-panel/` |

---

## 4. Configuration Environment Variables

All variables are optional when running against a standard local development database:

| Variable | Default Value | Description |
|---|---|---|
| `BB_BASE_URL` | `http://127.0.0.1:8000` | Target URL of the running Django application |
| `BB_HEADLESS` | `1` | Set to `0` to open visible browser window during execution |
| `BB_INCIDENT_ID` | Auto-linked from Test 1 | Manual override for disposable incident ID in Test 2 |
| `BB_MEDICAL_USER_ID` | Auto-detected from UI | User ID of an AVAILABLE Medical Team member |
| `BB_MEDICAL_CASE_ID` | Auto-linked from Test 3 | Manual override for medical case ID in Test 4 |
| `BB_TARGET_USERNAME` | `demo_ranger` | Staff username for Admin role modification in Test 6 |
| `BB_REPORT_FROM` | Today's Date (`YYYY-MM-DD`) | Period start date for Researcher report in Test 5 |
| `BB_REPORT_TO` | Today's Date (`YYYY-MM-DD`) | Period end date for Researcher report in Test 5 |

---

## 5. Two-Terminal Installation & Execution Workflow

### Step 1: Install Dependencies
Open a PowerShell or Terminal window in the project root:
```powershell
pip install -r selenium_tests/requirements-selenium.txt
```

### Step 2: Terminal 1 — Start the Django Application Server
Ensure your virtual environment is active, then launch the Django server:
```powershell
python manage.py runserver 127.0.0.1:8000
```
*Leave Terminal 1 running.*

### Step 3: Terminal 2 — Run the Selenium Test Suite
In a second terminal window, run the test runner:

**Standard Headless Mode (Fast execution):**
```powershell
python selenium_tests/selenium_tests.py
```

**Visible Browser Mode (Watch the tests interact live):**
```powershell
$env:BB_HEADLESS="0"
python selenium_tests/selenium_tests.py
```

**Run a Single Specific Test (e.g., Test 1):**
```powershell
python -m unittest selenium_tests.selenium_tests.BustardBeaconCoreWorkflowTests.test_01_ranger_submits_injured_bird_incident
```

---

## 6. Detailed Workflow Test Breakdown

### Test 1: Ranger submits an injured-bird incident
- **Action**: Authenticates via the `#ranger-tab` as Field Ranger, navigates to `/ranger/report-incident/`, selects `INJURED_BIRD` category, injects valid GPS coordinates (`17.6599, 75.9064`), attaches a unique timestamped observation description, and submits the form.
- **Verification**: Verifies automatic redirection to `/ranger/incidents/`, confirms the new report exists in the incident queue, asserts the status is `PENDING`, and captures the generated `INC-YYYY-XXXXXX` code and primary key.

### Test 2: Forest Officer verifies the incident and sets priority
- **Action**: Authenticates as Forest Officer (`#officer-tab`), opens `/officer/incidents/<id>/` for the incident created in Test 1, selects `VERIFIED` status, upgrades priority to `CRITICAL`, enters official verification notes, and submits.
- **Verification**: Verifies page refresh with success notification `"Incident ... verification updated"`, verifies the status dropdown persists `VERIFIED`, and asserts the priority dropdown persists `CRITICAL`.

### Test 3: Ranger assigns a case to the Medical Team
- **Action**: Authenticates as Ranger, reports an injured bird with the `#send_medical_alert` toggle activated, dynamically discovers and selects an active `AVAILABLE` Medical Team member (`dr_vet_solapur`), and submits the emergency dispatch.
- **Verification**: Confirms report creation in Ranger view, logs out, logs in as the assigned Medical Team account (`#medical-tab`), opens `/medical/cases/`, asserts the newly assigned case appears in the veterinary queue, opens `/medical/cases/<case_id>/`, and verifies clinical symptom persistence.

### Test 4: Medical Team treats and closes the case
- **Action**: Opens the assigned clinical case detail view, enters a treatment log (procedure, medications `Meloxicam, Enrofloxacin`, dosage), submits the treatment form, then updates the case rehabilitation stage to `RELEASED` ("Successfully Released to Wild") and status to `CLOSED`.
- **Verification**: Verifies treatment history persistence, asserts success message `"Medical case status and stage updated"`, confirms stage display is `Successfully Released to Wild`, and asserts status display is `CLOSED`.

### Test 5: Researcher report workflow and Forest Officer access
- **Action**: Authenticates as Wildlife Researcher (`#researcher-tab`), navigates to `/research/reports/`, drafts a monthly conservation report, finalizes the draft, and clicks `"Send to Forest Officer"`. Logs out, logs in as Forest Officer, and visits `/notifications/`.
- **Verification**: Asserts report badge displays `FINALIZED`, verifies submission button state transitions to `"Sent to FO"`, verifies Forest Officer receives high-priority notification `"Monthly Conservation Analysis Report Submitted"`, and verifies direct access to the generated report endpoint (`/reports/pdf/?type=CONSERVATION_ANALYSIS_REPORT&report_id=...`).

### Test 6: Admin changes a user's role and verifies employee ID/badge number
- **Action**: Authenticates as System Administrator (`#admin-tab`), navigates to `/admin-panel/users/`, locates the dedicated test staff account (`demo_ranger`), reads current badge number, toggles the role between `RANGER` and `FOREST_OFFICER`, and submits the change.
- **Verification**: Asserts success message `"Role for ... updated ... New Badge Number: ..."`, reloads `/admin-panel/users/`, confirms persisted role in dropdown, and verifies the badge number changes to the correct prefix (`RNG-` for Ranger, `FO-` for Forest Officer) and is distinct from the previous badge number.

---

## 7. Limitations & Architectural Findings

1. **Medical Team Referral Interface**: In the BUSTARD BEACON implementation, Rangers assign cases to Medical Teams **at the time of reporting** via the `Medical Treatment Required` toggle (`#send_medical_alert`) on `/ranger/report-incident/`. There is no post-submission referral button inside the read-only incident modal on `/ranger/incidents/`. Forest Officers can also assign or reassign Medical Teams on `/officer/incidents/<id>/`.
2. **Rehabilitation Stage Transitions**: The application enforces a strict clinical state transition map (`valid_mapping` in `medical_views.py`). `RELEASED` and `DECEASED` can only transition with `CLOSED` status. The test suite strictly follows this business rule.
3. **Headless Geolocation**: Headless automated browsers lack physical GPS hardware; coordinates are injected directly into the form's `#field-latitude` and `#field-longitude` hidden inputs, exactly as the HTML5 Geolocation API does in mobile field mode.
4. **Email & External Services**: Password reset and external email dispatch are safely bypassed in end-to-end tests to prevent external network dependencies.

---

## 8. Faculty Demonstration Guide

When presenting this test suite to evaluators or faculty members:

1. **Open two side-by-side terminal windows** on your desktop.
2. In Terminal 1, run `python manage.py runserver`.
3. In Terminal 2, launch the tests in visible mode so the browser window is displayed:
   ```powershell
   $env:BB_HEADLESS="0"
   python selenium_tests/selenium_tests.py
   ```
4. **Key Talking Points for Evaluators**:
   - Point out how each role's authentication is partitioned using role tabs (`#ranger-tab`, `#officer-tab`, etc.) to prevent cross-role session escalation.
   - Explain that all six tests run against the **real SQLite database** and **real Django views** rather than mock stubs.
   - Highlight the data safety: every test creates isolated records with unique UUID tags without corrupting existing historical sanctuary records.
   - Show how Test 1 flows into Test 2 (Ranger incident -> Officer verification), and Test 3 flows into Test 4 (Ranger dispatch -> Vet treatment and release).
