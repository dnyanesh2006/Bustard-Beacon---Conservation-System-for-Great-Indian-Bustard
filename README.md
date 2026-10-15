# Bustard Beacon — Conservation System for the Great Indian Bustard

[![Django](https://img.shields.io/badge/Django-4.2+-092e20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Google Maps](https://img.shields.io/badge/Google_Maps-API-4285F4?style=for-the-badge&logo=googlemaps&logoColor=white)](https://developers.google.com/maps)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952b3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Status](https://img.shields.io/badge/Status-Production_Ready-2e7d32?style=for-the-badge)](https://github.com/)

An integrated, role-based wildlife conservation and spatial monitoring management platform engineered for the protection and habitat recovery of the critically endangered **Great Indian Bustard (*Ardeotis nigriceps*)** at the **Great Indian Bustard Sanctuary, Nannaj, Solapur District, Maharashtra**.

---

## 1. Project Overview

The Great Indian Bustard (GIB) is one of the heaviest flying birds in the world and is listed as **Critically Endangered** on the IUCN Red List, with fewer than 150 individuals remaining in the wild. Primary threats include powerline collisions, feral predator attacks on nests, habitat fragmentation, and unauthorized human encroachment into breeding sectors.

**Bustard Beacon** bridges field operations and administrative decision-making by replacing fragmented paperwork and messaging channels with a centralized, real-time spatial conservation management system. It provides real-time geospatial patrol tracking, verified field incident reporting, specialized veterinary case lifecycle management, eco-tourism permit controls, and telemetry research tracking across 5 specialized operational user roles.

---

## 2. Key Features

* **Public Conservation Portal & Sanctuary Showcase:**
  * Interactive landing page with factual conservation metrics, species identification cards, habitat gallery, and an integrated Google Maps spatial overview of Nannaj sanctuary sectors.
  * Public visitor guidelines and live eco-tourism restricted-zone notices.
* **Full-Screen GIS Spatial Map (`/map/`):**
  * Powered by Google Maps JavaScript API with high-contrast UI controls.
  * Real-time vector polygon boundaries for official habitat sectors (Nannaj Core, Solapur Grassland Buffer, Maldhok Eco-Tourism, Karmala Corridor, etc.).
  * Color-coded field incident markers with image thumbnails, severity indicators (Critical, High, Medium, Low), and weather metadata.
  * Real-time GPS location tracking of active field rangers on patrol.
  * Interactive layer toggles and one-click "Zoom to Zone" boundary framing.
* **Multi-Tab Resilient Authentication:**
  * Role-isolated session management preventing privilege leaks.
  * Cross-tab CSRF synchronization preventing HTTP 403 Forbidden errors when submitting forms across concurrent browser tabs.
  * Support for standard browser navigation, right-click "Open link in new tab", and Ctrl+Click for all roles.
  * Optional Google OAuth 2.0 Single Sign-On integration.
* **Role-Based Incident Lifecycle:**
  * Fast mobile-optimized Field Mode for Rangers with one-tap incident logging, GPS capture, offline caching, and photo attachments.
  * Forest Officer review and verification workflow transitioning incidents from `PENDING` to `VERIFIED` with audit trails.
* **Veterinary Medical Management:**
  * Full lifecycle triage, clinical examination, treatment logging, and quarantine tracking for injured birds.
  * Medical case progression: `RESCUE` &rarr; `TRIAGE` &rarr; `ICU` &rarr; `QUARANTINE` &rarr; `RELEASE_READY` &rarr; `RELEASED`.
  * Medical equipment inventory and supply usage logging.
* **Eco-Tourism & Visitor Permit Management:**
  * Regulated visitor entry management for Maldhok Tourism Zone.
  * Full CRUD permit workflows with visitor headcounts and status tracking (`PENDING`, `APPROVED`, `COMPLETED`, `CANCELLED`).
* **Scientific Research & Population Analytics:**
  * Bird banding registry and population health tracking.
  * Observation movement plotting on geospatial maps.
  * Automated periodic conservation PDF report generation with ReportLab.

---

## 3. Technology Stack

* **Backend Framework:** Django (v4.2+ / v5.x / v6.x compatible)
* **Programming Language:** Python 3.10+ (tested up to Python 3.14)
* **Database Engine:** 
  * Development: SQLite 3 (`db.sqlite3`)
  * Production: MySQL / MariaDB (via `mysqlclient`, auto-configured when credentials are provided in `.env`)
* **Mapping & GIS Engine:** Google Maps JavaScript API (with OpenStreetMap / Leaflet compatibility layers)
* **Frontend Architecture:** 
  * Semantic HTML5 & Vanilla JavaScript
  * Bootstrap 5.3 & Bootstrap Icons
  * Custom Centurion Conservation Design System (`design_system.css`, `field_mode.css`)
* **Reporting & Data Export:** ReportLab (automated PDF report generation)
* **Image Processing:** Pillow (PIL Fork)
* **Authentication:** Django Authentication with PBKDF2 SHA-256 password hashing, custom `UserProfile` role binding, and Google OAuth 2.0 (`google-auth`, `google-auth-oauthlib`)
* **Testing:** Django Test Runner (`core/tests.py`) and Selenium WebDriver (`selenium_tests/`)

---

## 4. Five User Roles & Responsibilities

The application enforces strict Role-Based Access Control (RBAC). Each role has its own dedicated dashboard and capabilities:

| Role | Primary Dashboard | Key Responsibilities |
|---|---|---|
| **Administrator** | `/admin-panel/dashboard/` | Overall system oversight, user account creation, role badge assignment, account activation/deactivation, KPI count cards, audit log monitoring, and database management. |
| **Forest Officer** | `/officer/dashboard/` | Operational field management, review and verification of ranger field reports, eco-tourism permit approvals, zone restriction configurations, and inter-agency dispatch. |
| **Ranger** | `/ranger/field-mode/` | Frontline field operations, mobile-friendly Field Mode, SOS emergency broadcasting, real-time patrol GPS tracking, wildlife sighting logging, and powerline hazard reporting. |
| **Medical Team** | `/medical/dashboard/` | Wildlife veterinary clinic management, bird rescue admissions, triage assessments, surgical/medical treatment logging, and rehabilitation quarantine tracking. |
| **Researcher** | `/research/dashboard/` | Scientific ecological studies, bird banding records, movement pattern GIS analysis, population demographics, high-risk sector analysis, and PDF research report exports. |

---

## 5. Project Directory Structure

```text
Bustard-Beacon/
│
├── manage.py                          # Django management command CLI
├── requirements.txt                   # Production Python package dependencies
├── .env.example                       # Sanitized template for environment variables
├── .gitignore                         # Comprehensive Git exclusion rules
├── README.md                          # Main project documentation and setup guide
│
├── bustard_beacon/                    # Django Project Configuration
│   ├── __init__.py
│   ├── asgi.py                        # ASGI entrypoint for async servers
│   ├── settings.py                    # Global settings, DB fallback & middleware
│   ├── urls.py                        # Root URL routing configuration
│   └── wsgi.py                        # WSGI entrypoint for web servers
│
├── core/                              # Core Conservation Application
│   ├── context_processors.py          # Global template context (roles, keys, badges)
│   ├── middleware.py                  # Multi-tab auth & session security middleware
│   ├── models.py                      # Database models (Zones, Incidents, Birds, Cases)
│   ├── urls.py                        # Application URL routes
│   ├── tests.py                       # Official Django TestCase test suite
│   │
│   ├── management/commands/           # Custom Django Management Commands
│   │   ├── seed_demo_data.py          # Master demo data seeder & account initializer
│   │   └── seed_researcher_demo_data.py # Supplementary research telemetry data
│   │
│   ├── static/                        # Static Frontend Assets
│   │   ├── css/                       # Design System CSS (design_system.css, field_mode.css)
│   │   ├── js/                        # Map GIS engines (map.js) & field mode JS
│   │   ├── images/                    # Species portraits, logos, and gallery assets
│   │   └── videos/                    # Hero background video (hero-bustard.mp4)
│   │
│   ├── templates/                     # Role-Segmented HTML Templates
│   │   ├── base.html                  # Master base template with multi-tab CSRF sync
│   │   ├── landing.html               # Public landing page with interactive map preview
│   │   ├── login.html                 # Unified role-aware authentication portal
│   │   ├── map.html                   # Full-screen Sanctuary GIS Map with zone panel
│   │   ├── tourism.html               # Eco-tourism visitor guidelines
│   │   ├── admin_panel/               # Administrator dashboards and user CRUD
│   │   ├── officer/                   # Forest Officer dashboards and tourism management
│   │   ├── ranger/                    # Ranger field mode, incidents, and SOS reports
│   │   ├── medical/                   # Veterinary triage and case tracking
│   │   ├── research/                  # Researcher analytics, movements, and reports
│   │   └── reports/                   # Report preview and layout templates
│   │
│   └── views/                         # Modular Role-Based View Handlers
│       ├── admin_views.py             # Administrator logic and account management
│       ├── auth_views.py              # Multi-tab login, logout, password resets
│       ├── landing_views.py           # Public landing and tourism views
│       ├── map_views.py               # Live Sanctuary GIS and GeoJSON REST API
│       ├── medical_views.py           # Veterinary triage and medical case views
│       ├── officer_views.py           # Forest Officer operations & tourism permits
│       ├── ranger_views.py            # Ranger field mode and incident workflows
│       ├── report_views.py            # Automated PDF report generators
│       └── research_views.py          # Researcher movement and population analysis
│
├── media/                             # User-Uploaded Dynamic Media (Git-tracked)
│   ├── incident_photos/               # Verified field observation photographs
│   └── birth_records/                 # Hatching and breeding observation photos
│
├── project_documentation/             # Architecture Specifications
│   └── uml_diagrams/                  # Official architecture UML diagrams (JPG)
│       ├── 4.1_Use_Case_Diagram.jpg
│       ├── 4.2_Class_Diagram.jpg
│       ├── 4.3_Sequence_Diagram.jpg
│       ├── 4.4_State_Chart_Diagram.jpg
│       └── 4.5_Activity_Diagram.jpg
│
├── References/                        # Academic and Domain Documentation
│   └── Assign_2_Bustard_Beacon_SRS 2.pdf # Software Requirements Specification (SRS)
│
├── selenium_tests/                    # Automated End-to-End Browser Testing Suite
│   ├── requirements-selenium.txt      # Selenium requirements
│   ├── README_SELENIUM.md             # Selenium test execution guide
│   └── selenium_tests.py              # Automated browser test cases
│
├── test_auth_roles.py                 # Multi-role authentication & redirect test suite
├── test_auth_flow.py                  # Password rotation and session test suite
├── test_tourism_and_cards.py          # Admin count cards & tourism permit test suite
└── verify_all_requirements.py         # Full browser verification test suite
```

---

## 6. Prerequisites

* **Operating System:** Windows, macOS, or Linux.
* **Python:** Python 3.10, 3.11, 3.12, or 3.14.
* **pip:** Python package manager (included with standard Python).
* **Git:** For cloning and version control.
* **Web Browser:** Modern Chromium-based browser (Chrome, Edge) or Firefox.

---

## 7. Installation Instructions

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-username/bustard-beacon.git
cd bustard-beacon
```

### Step 2: Create and Activate a Virtual Environment

* **On Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```

* **On macOS / Linux (bash/zsh):**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

---

## 8. Environment Configuration

1. Copy the template `.env.example` file to create your local `.env`:

   * **Windows (PowerShell):**
     ```powershell
     Copy-Item .env.example .env
     ```
   * **macOS / Linux:**
     ```bash
     cp .env.example .env
     ```

2. Open `.env` in a text editor and configure the variables:

```ini
# Django Secret Key (Can leave as default for local development)
SECRET_KEY=django-insecure-your-local-development-key-here
DEBUG=True

# Database Configuration (Leave blank for default SQLite database)
DATABASE_NAME=
DATABASE_USER=
DATABASE_PASSWORD=
DATABASE_HOST=localhost
DATABASE_PORT=3306

# Google Maps JavaScript API (Required for interactive GIS map display)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# Google OAuth 2.0 (Optional — leave blank if not using Google SSO)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback/
```

> **Note:** If `DATABASE_NAME` and `DATABASE_USER` are left blank, Django automatically uses the local SQLite database (`db.sqlite3`).

---

## 9. Database Setup & Demo Data Seeding

### Step 1: Apply Database Migrations
Create all necessary database tables and schema structures:
```bash
python manage.py migrate
```

### Step 2: Seed Demo Data & Initialize Accounts
Populate the database with official Nannaj sanctuary zones, registered birds, sample incidents, medical equipment, and default user accounts:
```bash
python manage.py seed_demo_data
```

*(Optional) Seed supplementary researcher telemetry movements:*
```bash
python manage.py seed_researcher_demo_data
```

---

## 10. Default Demo User Accounts

The seeding command initializes five verified demonstration accounts, one for each system role:

| System Role | Username | Default Password | Badge Number | Default Access Route |
|---|---|---|---|---|
| **Administrator** | `admin` | `admin123` | `ADM-001` | `/admin-panel/dashboard/` |
| **Forest Officer** | `officer_solapur` | `officer123` | `FO-SLP-101` | `/officer/dashboard/` |
| **Field Ranger** | `ranger_nannaj` | `ranger123` | `RNG-NNJ-204` | `/ranger/field-mode/` |
| **Medical Team** | `dr_vet_solapur` | `vet123` | `VET-SLP-302` | `/medical/dashboard/` |
| **Researcher** | `dr_researcher` | `research123` | `RES-WII-501` | `/research/dashboard/` |

> **Password Reset Tip:** If any account password is changed during testing, you can reset all demo accounts back to the credentials above at any time by running:
> ```bash
> python manage.py seed_demo_data
> ```

---

## 11. How to Run the Application

Start the Django development server:
```bash
python manage.py runserver
```

Open your web browser and navigate to:
```text
http://127.0.0.1:8000/
```

* **Landing Page:** `http://127.0.0.1:8000/`
* **Sanctuary GIS Map:** `http://127.0.0.1:8000/map/`
* **Staff Login Portal:** `http://127.0.0.1:8000/login/`

---

## 12. Running Automated Tests

The repository includes comprehensive automated test suites to ensure stability across roles, APIs, and workflows:

### A. Official Django Test Suite
Runs unit tests for models, permissions, and map data APIs:
```bash
python manage.py test
```

### B. Role-Based Access Control (RBAC) Verification
Validates that each of the five roles is redirected to their authorized dashboard and blocked from unauthorized areas:
```bash
python test_auth_roles.py
```

### C. Multi-Tab Authentication & Password Flow Verification
Tests password rotation, user deactivation/reactivation, and multi-tab session synchronization:
```bash
python test_auth_flow.py
```

### D. Tourism Permits & Admin KPI Cards Test Suite
Validates Admin KPI card counts, Forest Officer tourism permit CRUD operations, and permission checks:
```bash
python test_tourism_and_cards.py
```

### E. End-to-End Browser Automation (Selenium)
To run automated browser testing using Microsoft Edge or Google Chrome:
```bash
pip install -r selenium_tests/requirements-selenium.txt
python verify_all_requirements.py
```

---

## 13. Troubleshooting Common Setup Issues

| Issue | Cause | Solution |
|---|---|---|
| **Map shows "Map API not configured" or grey container** | Missing or invalid `GOOGLE_MAPS_API_KEY` in `.env`. | Add a valid Google Maps API Key to your `.env` file and refresh the page. |
| **`ImportError: Couldn't import Django`** | Virtual environment is not activated or dependencies are missing. | Activate your virtual environment (`.\venv\Scripts\Activate.ps1` or `source venv/bin/activate`) and run `pip install -r requirements.txt`. |
| **`OperationalError: no such table`** | Database migrations have not been applied. | Run `python manage.py migrate` followed by `python manage.py seed_demo_data`. |
| **Port 8000 is already in use** | Another local process or web server is running on port 8000. | Start the server on a different port: `python manage.py runserver 8080`. |
| **HTTP 403 Forbidden on login** | CSRF token mismatch or stale tab session. | The application includes client-side multi-tab CSRF auto-synchronization. Ensure cookies are enabled in your browser and refresh the login page. |

---

## 14. Security Notice

* **Never commit `.env` to GitHub:** The `.env` file contains your private secret keys, API credentials, and database passwords. It is strictly excluded by `.gitignore`.
* **Rotate Exposed Credentials:** If you ever accidentally commit an API key or secret token to version control, revoke and rotate the credential immediately in the corresponding console (e.g., Google Cloud Console).
* **Production Deployment:** For production deployments, set `DEBUG=False` in `.env`, configure an explicit list of `ALLOWED_HOSTS`, and use a production WSGI server (e.g., Gunicorn or uWSGI) backed by a managed MySQL or PostgreSQL database.

---

## 15. Authors & Acknowledgments

* **Project:** Bustard Beacon – Conservation System for the Great Indian Bustard
* **Domain Context:** Great Indian Bustard Sanctuary (*Maldhok Bird Sanctuary*), Nannaj, Solapur, Maharashtra.
* **Reference Specifications:** Wildlife Institute of India (WII) conservation guidelines and State Forest Department conservation protocols.
