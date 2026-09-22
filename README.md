# Rememberizer

A multi-user, terminal-styled Flask web application for quizzing students on facts with spaced repetition, mastery tracking, and role-based access control.

## Overview

Rememberizer is a comprehensive learning management system that combines intelligent quiz algorithms with a robust multi-user authentication framework. The application supports three distinct user roles (Admin, Teacher, Student) with isolated progress tracking, domain assignment management, and detailed engagement metrics.

**Key Capabilities:**
- **Multi-user authentication** with role-based access control
- **Organization isolation** (schema supports multiple organizations)
- **Token-based account setup** (secure magic links for password creation)
- **Domain assignment management** (teachers assign specific domains to students)
- **Progress isolation** (each student has independent learning progress)
- **Engagement tracking** (questions answered, time spent, session tracking)
- **Intelligent quiz system** with three-state learning and spaced repetition
- **Terminal aesthetic** with retro green-on-black styling

## Latest Updates (v3.0) - Multi-User System

The app now features a complete multi-user authentication and authorization system:

- ✅ **Three user roles**: Admin, Teacher, and Student with distinct capabilities
- ✅ **Token-based setup**: Secure magic links for password creation (no shared passwords)
- ✅ **Organization isolation**: Users can only access data from their organization
- ✅ **Domain assignment**: Teachers assign specific domains to individual students
- ✅ **Progress isolation**: Each student has completely independent learning progress
- ✅ **Engagement metrics**: Track questions answered, time spent, practice sessions
- ✅ **Teacher dashboard**: View all students with progress summaries and detailed metrics
- ✅ **Student dashboard**: See only assigned domains with personal progress
- ✅ **70+ new tests** covering authentication, authorization, and multi-user functionality
- ✅ **Test coverage**: 269 tests, 71% overall (see Testing for where the gaps are)

### User Roles

#### 1. Admin (Super User)
- Create and manage teacher accounts
- View system-wide overview
- Access all teacher and admin functions
- Cannot directly access student quiz routes

#### 2. Teacher
- Create and manage student accounts
- Assign and unassign domains to/from students
- View detailed student progress across all domains
- Reset student progress for specific domains
- View engagement metrics (questions answered, time spent, sessions)
- Cannot access other organizations' students

#### 3. Student
- View only assigned domains
- Access quiz functionality for assigned domains only
- Track personal progress and engagement metrics
- Cannot access unassigned domains or other students' data

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. First Run - Admin Account Setup

On first startup, the application will prompt you to create an admin account:

```bash
python app.py
```

You'll see:
```
No admin account found. Create one now? [Y/n] Y
Enter admin email: admin@school.edu
Enter admin password (min 8 chars): ********
Admin account created successfully!
Admin Email: admin@school.edu
```

The application will then start normally at `http://localhost:5000`.

### 3. Login and Create Users

1. **Login as Admin**: Navigate to `http://localhost:5000/login`
2. **Create a Teacher**: Go to Admin Dashboard → Create Teacher
   - Enter first name, last name, and email
   - Teacher receives magic link to set their own password
3. **Login as Teacher**: Use the magic link to set password, then login
4. **Create Students**: Go to Teacher Dashboard → Create Student
   - Enter first name, last name, and email
   - Student receives magic link to set their own password
5. **Assign Domains**: In Teacher Dashboard, click [MANAGE DOMAINS] for a student
   - Assign specific fact domains to that student
6. **Student Access**: Student logs in and sees only their assigned domains

## Features

### Authentication & Authorization

- **Secure password handling**: Werkzeug scrypt hashing (industry-standard)
- **Token-based setup**: Users set their own passwords via secure 7-day magic links
- **Session management**: Flask-Login with secure session cookies
- **Role-based access control**: Decorators enforce role requirements on routes
- **Organization isolation**: Teachers only see students from their organization
- **Account lifecycle**: Create, activate, deactivate users with full audit trail

### Multi-User Progress Tracking

- **Isolated progress**: Each student has completely independent FactState and Attempt records
- **Domain assignment**: Students can only access domains explicitly assigned by teachers
- **Progress visibility**: Teachers view detailed progress for all students in their organization
- **Reset functionality**: Teachers can reset individual student progress for specific domains
- **Progress transfer**: None (students cannot transfer progress between accounts)

### Engagement Metrics

- **Questions answered**: Total count and daily count per student
- **Time spent**: Calculated from first to last attempt timestamp
- **Practice sessions**: Unique session tracking via UUID
- **Last active**: Automatic timestamp updates on every request
- **Engagement display**: Metrics visible in teacher dashboard and student progress pages

### Quiz System (Intelligent Learning)

- **Domain-based learning**: Load fact domains from JSON files
- **Multiple-choice quizzing**: 4 options per question with intelligent wrong answer selection
- **Three-state learning system**: Facts progress through Unlearned → Learned → Mastered states
- **Mastery tracking**: Facts are marked as mastered after 6 of 7 correct attempts with most recent correct
- **Smart progression**: Requires 2 consecutive correct answers before moving to next fact
- **Automatic demotion**: Facts return to unlearned after 2 consecutive wrong answers
- **Spaced repetition**: Every 3rd question reinforces a previously mastered fact
- **Recovery mode (Doom Loop)**: Special mode when too many facts are unmastered
- **Progress reset**: Reset progress for any domain with one click
- **Persistent progress**: SQLite database tracks all attempts and learning states across sessions

### Fact Images

- **Images as field values**: Any field of a teacher-created domain can hold an image instead of text
- **Fully quizzable**: An image can be the question's context ("What is the symbol of this greek muse?") or the four answer options
- **Two sources**: Upload image files alongside the domain, or reference an external `https://` URL
- **Both authoring paths**: Works with form entry and CSV upload
- **Validated uploads**: Format checked by file signature (not extension), 5MB per image, 25MB per request
- **No answer leaks**: Stored under random filenames so the page source never names the answer

### User Interface

- **Terminal aesthetic**: Retro green-on-black interface with monospace fonts
- **Role-specific navigation**: Each role sees appropriate navigation options
- **Responsive design**: Works on desktop and mobile browsers
- **Visual feedback**: Clear indication of correct/incorrect answers
- **Progress indicators**: Visual progress bars using terminal characters (·, +, -, *)
- **Keyboard navigation**: Responsive design with mouse and keyboard support

## Installation

### Standard Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd rememberizer
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install development dependencies** (optional, for testing and linting):
```bash
pip install -r requirements-dev.txt
```

### Database Initialization

**Automatic (Recommended)**: The database initializes automatically on first request when you start the application.

**Manual** (Optional): If you prefer to initialize the database before starting:
```bash
python init_database.py
```

This creates all tables including organizations, users, user_domain_assignments, domains, facts, fact_states, and attempts.

### First-Time Admin Setup

On first run, the application checks for an admin account:

1. If no admin exists, you're prompted in the terminal
2. Enter admin email (e.g., admin@school.edu)
3. Enter admin password (minimum 8 characters)
4. Admin account is created and stored securely

**Security Note**: The admin password is never stored in plaintext or hardcoded. Only you (the system administrator) set and know the admin password.

## Usage

### Starting the Application

```bash
python app.py
```

The application runs on `http://localhost:5000` by default.

### User Workflows

#### Admin Workflow

1. **Login**: Navigate to `/login` and enter admin credentials
2. **View Dashboard**: See system overview (teacher count, student count, domain count)
3. **Create Teacher**:
   - Go to Admin Dashboard → [CREATE NEW TEACHER]
   - Enter first name, last name, email
   - Teacher receives setup link (email or displayed if email fails)
4. **Manage Teachers**: View list of teachers with creation dates
5. **Deactivate Teachers**: Deactivate teacher accounts as needed

#### Teacher Workflow

1. **Setup Account**: Click magic link from email to set password
2. **Login**: Navigate to `/login` with email and new password
3. **View Dashboard**: See all students with progress summaries
4. **Create Student**:
   - Go to Teacher Dashboard → [CREATE NEW STUDENT]
   - Enter first name, last name, email
   - Student receives setup link (email or displayed if email fails)
5. **Assign Domains**:
   - Click [MANAGE DOMAINS] for a student
   - View assigned and unassigned domains
   - Click [ASSIGN DOMAIN] to grant access
6. **View Student Progress**:
   - Click [VIEW DETAILS] for detailed progress breakdown
   - See engagement metrics (questions answered, time spent, sessions)
   - View progress for each assigned domain
7. **Reset Progress**: Click [RESET] button to clear student progress for specific domain
8. **Unassign Domains**: Remove domain access from student

#### Student Workflow

1. **Setup Account**: Click magic link from email to set password
2. **Login**: Navigate to `/login` with email and new password
3. **View Domains**: See only assigned domains with progress indicators
4. **Start Practice**: Click [START PRACTICE] for a domain
5. **Learn Facts**: View unlearned facts and click [CONTINUE] to mark as learned
6. **Answer Questions**: Take quiz on learned facts
7. **View Progress**: See personal progress metrics (questions today, time spent, sessions)
8. **Reset Progress**: Use [RESET] button to clear own progress for a domain

## Project Structure

Routes live in `blueprints/`, business logic in `services/`, and `models.py` holds
only SQLAlchemy models. See ARCHITECTURE.md for how the layers depend on each other.

```
rememberizer/
├── app.py                       # Flask app: config, template filters, blueprint registration
├── models.py                    # SQLAlchemy models only (no business logic)
├── auth.py                      # Authentication system (Flask-Login, decorators)
├── quiz_logic.py                # Quiz generation & fact selection
├── facts_loader.py              # JSON fact loading & validation
├── doom_loop.py                 # Recovery mode for struggling learners
├── blueprints/                  # Route handlers, one module per concern
│   ├── admin.py                 # Admin dashboard & teacher management
│   ├── auth_routes.py           # Login, logout, password setup
│   ├── teacher.py               # Teacher dashboard, domains, students, groups
│   ├── student.py               # Student domain selection & progress
│   ├── quiz.py                  # Learning & quizzing flow
│   └── analytics.py             # Analytics dashboards
├── services/                    # Business logic layer
│   ├── fact_service.py          # Fact learning states & attempts
│   ├── user_service.py          # User management & authentication
│   ├── domain_service.py        # Domain assignment & visibility
│   ├── progress_service.py      # Progress tracking & statistics
│   ├── image_service.py         # Fact images (markers, uploads, validation)
│   ├── analytics_service.py     # Data aggregation & insights
│   ├── group_service.py         # Student groups & bulk assignment
│   ├── template_service.py      # Assignment templates
│   ├── streak_service.py        # Practice streaks
│   └── bulk_import_service.py   # Bulk student import
├── init_db.py                   # Database initialization script
├── rebuild_db.py                # Drop and rebuild the database from scratch
├── verify_database.py           # Read-only database health check
├── migration_add_*.py           # One-off schema migration scripts
├── instance/                    # Flask instance folder (auto-created)
│   └── database.db              # SQLite database (auto-initialized)
├── requirements.txt             # Python dependencies
├── requirements-dev.txt         # Development dependencies (linters pinned exactly)
├── pytest.ini                   # Pytest configuration with coverage
├── pyproject.toml               # Black and Ruff configuration
├── .flake8                      # Flake8 configuration
├── .gitignore                   # Git ignore patterns
├── facts/                       # JSON fact files directory
│   ├── greek_muses.json         # Example: 9 Greek muses
│   └── chinese_dynasties.json   # Example: 14 Chinese dynasties
├── tests/                       # Test suite (269 tests)
│   ├── README.md                # Testing documentation
│   ├── conftest.py              # Shared test fixtures (app, users, domains)
│   ├── test_auth.py             # Authentication
│   ├── test_authorization.py    # Role-based access control
│   ├── test_multi_user.py       # Multi-user isolation
│   ├── test_models.py           # Database models & learning states
│   ├── test_quiz_logic.py       # Quiz generation & fact selection
│   ├── test_image_fields.py     # Fact images (markers, uploads, rendering)
│   ├── test_domain_creation.py  # Teacher domain creation
│   ├── test_duplicate_symbols.py# Duplicate field values in options
│   ├── test_fact_service.py     # Fact learning state transitions
│   ├── test_streak_service.py   # Practice streaks
│   ├── test_template_filters.py # Jinja2 filter tests
│   ├── test_doom_loop.py        # Recovery mode tests
│   ├── test_facts_loader.py     # JSON loading & validation
│   └── test_routes.py           # Flask routes & flows
├── templates/
│   ├── base.html                # Base template with terminal header
│   ├── login.html               # Login page
│   ├── setup_password.html      # Password setup page (magic link)
│   ├── admin/                   # Admin dashboard, teacher creation
│   ├── teacher/                 # Dashboard, domains, students, groups, templates
│   ├── student/                 # Assigned domains, personal progress
│   ├── analytics/               # Analytics dashboards
│   ├── select_domain.html       # Domain selection (legacy)
│   ├── show_fact.html           # Fact display page
│   ├── quiz.html                # Quiz question page
│   ├── answer_result.html       # Answer feedback page
│   └── celebration.html         # Domain completion screen
└── static/
    ├── style.css                # Terminal styling (green/red on black)
    ├── app.js                   # Client-side interactivity
    └── uploads/                 # Teacher-uploaded fact images (gitignored)
```

## Database Schema

### Authentication Tables

#### organizations
Organizational units for multi-tenant support (currently single-org)
- `id` (INTEGER, PK): Organization ID
- `name` (VARCHAR(200), UNIQUE): Organization name
- `created_at` (DATETIME): Creation timestamp

#### users
User accounts with roles and authentication
- `id` (INTEGER, PK): User ID
- `email` (VARCHAR(120), UNIQUE, INDEXED): User email address
- `password_hash` (VARCHAR(255)): Scrypt-hashed password (NULL during setup)
- `role` (VARCHAR(20)): Role ('admin', 'teacher', 'student')
- `first_name` (VARCHAR(100)): First name
- `last_name` (VARCHAR(100)): Last name
- `organization_id` (INTEGER, FK → organizations.id): Organization membership
- `created_by` (INTEGER, FK → users.id, NULL): User who created this account
- `created_at` (DATETIME): Account creation timestamp
- `last_active` (DATETIME, NULL): Last request timestamp
- `is_active` (BOOLEAN, DEFAULT TRUE): Account active status
- `setup_token` (VARCHAR(100), UNIQUE, NULL): Token for password setup
- `setup_token_expires` (DATETIME, NULL): Token expiration (7 days from creation)

#### user_domain_assignments
Tracks which domains are assigned to which students
- `id` (INTEGER, PK): Assignment ID
- `user_id` (INTEGER, FK → users.id): Student ID
- `domain_id` (INTEGER, FK → domains.id): Domain ID
- `assigned_by` (INTEGER, FK → users.id): Teacher who assigned
- `assigned_at` (DATETIME): Assignment timestamp
- **UNIQUE CONSTRAINT**: (user_id, domain_id) - prevents duplicate assignments

### Quiz System Tables

#### domains
Fact domains (e.g., "Greek Muses", "Chinese Dynasties")
- `id` (INTEGER, PK): Domain ID
- `name` (VARCHAR(200)): Display name
- `filename` (VARCHAR(200)): Source JSON filename
- `field_names` (TEXT, JSON): List of field names

#### facts
Individual facts within domains
- `id` (INTEGER, PK): Fact ID
- `domain_id` (INTEGER, FK → domains.id): Parent domain
- `fact_data` (TEXT, JSON): Fact field values

#### fact_states
Learning state tracking (per user per fact)
- `id` (INTEGER, PK): State ID
- `fact_id` (INTEGER, FK → facts.id): Fact being tracked
- `user_id` (INTEGER, FK → users.id): Student learning this fact
- `learned_at` (DATETIME, NULL): When marked as learned (NULL = unlearned)
- `last_shown_at` (DATETIME, NULL): Last time fact was displayed
- `consecutive_correct` (INTEGER, DEFAULT 0): Consecutive correct answer count
- `consecutive_wrong` (INTEGER, DEFAULT 0): Consecutive wrong answer count
- `created_at` (DATETIME): State creation timestamp
- `updated_at` (DATETIME): Last update timestamp
- **UNIQUE CONSTRAINT**: (fact_id, user_id) - one state per user per fact

#### attempts
Quiz attempts (per user per fact per field)
- `id` (INTEGER, PK): Attempt ID
- `fact_id` (INTEGER, FK → facts.id): Fact being quizzed
- `field_name` (VARCHAR(100)): Field being tested
- `correct` (BOOLEAN): Answer correctness
- `timestamp` (DATETIME): Attempt timestamp
- `user_id` (INTEGER, FK → users.id): User who made attempt
- `session_id` (VARCHAR(50), NULL): Quiz session UUID for tracking

### Indexes

For performance optimization:
- `users.email` (UNIQUE INDEX): Fast email lookups during login
- `user_domain_assignments.user_id` (INDEX): Fast domain lookup for students
- `user_domain_assignments.domain_id` (INDEX): Fast user lookup for domains
- `fact_states.user_id` (INDEX): Fast progress queries
- `attempts.user_id` (INDEX): Fast attempt history queries
- `attempts.session_id` (INDEX): Fast session-based queries

## How It Works

### Authentication Flow

#### Account Creation Flow
1. **Admin creates Teacher** (or Teacher creates Student):
   - Enter first name, last name, email
   - System validates email format and checks for duplicates
   - System creates User record with `password_hash=NULL`
   - System generates `setup_token` (UUID) and sets `setup_token_expires` (7 days)
   - System attempts to send email with setup link
   - If email fails: Display setup link in flash message for manual sharing

2. **User Sets Password**:
   - User clicks magic link: `/setup-password/<token>`
   - System validates token (exists, not expired, user not already activated)
   - User enters password and confirmation
   - System validates password (min 8 chars, match confirmation)
   - System hashes password with scrypt and saves to `password_hash`
   - System clears `setup_token` and `setup_token_expires`
   - User redirected to login page

3. **User Logs In**:
   - User enters email and password at `/login`
   - System looks up user by email
   - System verifies password hash matches
   - System checks `is_active=TRUE` (deactivated users cannot login)
   - System creates Flask-Login session
   - System redirects based on role:
     - Admin → `/admin/dashboard`
     - Teacher → `/teacher/dashboard`
     - Student → `/student/domains`

#### Session Management
- **Session creation**: Flask-Login creates secure session cookie on login
- **Session validation**: `@login_required` decorator validates session on every request
- **Last active tracking**: `@app.before_request` hook updates `last_active` timestamp
- **Session termination**: `/logout` clears session and redirects to login

#### Role-Based Access Control
- **@login_required**: Requires authenticated user (any role)
- **@role_required('admin')**: Requires admin role
- **@role_required('teacher', 'admin')**: Requires teacher OR admin role
- **Student-specific routes**: Check `current_user.role == 'student'`

### Multi-User Progress Isolation

#### How Progress is Isolated
Every function that queries `FactState` or `Attempt` requires a `user_id` parameter:

```python
# Before (single-user):
learned_facts = get_learned_facts(domain_id)

# After (multi-user):
learned_facts = get_learned_facts(domain_id, user_id=current_user.id)
```

**Key isolation points:**
- `is_fact_learned(fact_id, user_id)` - Check if specific user learned fact
- `get_unlearned_facts(domain_id, user_id)` - Get unlearned facts for user
- `mark_fact_learned(fact_id, user_id)` - Mark fact learned for user
- `record_attempt(fact_id, field, correct, user_id, session_id)` - Record user's attempt
- `reset_domain_progress(domain_id, user_id)` - Reset only user's progress

**Database-level isolation:**
```sql
-- All FactState queries include user_id:
SELECT * FROM fact_states WHERE fact_id = ? AND user_id = ?

-- All Attempt queries include user_id:
SELECT * FROM attempts WHERE fact_id = ? AND user_id = ?
```

#### Domain Assignment Enforcement
Before a student can access a domain's quiz:
```python
# In /start route:
if current_user.role == 'student':
    if not is_domain_assigned(current_user.id, domain_id):
        flash("You don't have access to this domain", "error")
        return redirect(url_for('student_domains'))
```

Students can only see assigned domains in their domain list.

### Three-State Learning System

Facts progress through three states (per user):

1. **Unlearned**: Fact has never been shown to user, or demoted after 2 consecutive wrong answers
   - `fact_states.learned_at = NULL`
   - Not eligible for quizzing until shown

2. **Learned**: Fact has been displayed and user clicked "Continue"
   - `fact_states.learned_at = <timestamp>`
   - Eligible for quizzing
   - Not yet mastered

3. **Mastered**: At least 6 of last 7 attempts correct AND most recent attempt correct
   - `fact_states.learned_at = <timestamp>`
   - 6+ correct in last 7 attempts with most recent correct
   - Requires minimum 7 attempts
   - Used in spaced repetition (every 3rd question)

### State Transitions

- **Unlearned → Learned**: User views fact and clicks "Continue" button
  - `mark_fact_shown(fact_id, user_id)` sets `last_shown_at`
  - `mark_fact_learned(fact_id, user_id)` sets `learned_at`

- **Learned → Mastered**: Achieves 6+ correct in last 7 attempts with most recent correct
  - Automatic check after each attempt via `get_mastery_status(fact_id, user_id)`
  - Still has `learned_at` timestamp (mastered is a computed state)

- **Learned/Mastered → Unlearned**: 2 consecutive wrong answers (demotion)
  - `update_consecutive_attempts(fact_id, False, user_id)` increments `consecutive_wrong`
  - When `consecutive_wrong >= 2`: Clear `learned_at`, reset counters, return to unlearned

### Quiz Flow (Multi-User)

1. **Student selects assigned domain** → POST to `/start`
2. **System verifies domain assignment** (students only)
3. **System generates unique session ID** (`uuid.uuid4()`)
4. **System checks for unlearned facts** → `get_next_unlearned_fact(domain_id, user_id)`
   - If unlearned fact exists: Show fact with "Continue" button
   - If no unlearned facts: Start quizzing learned facts
5. **User views fact and clicks "Continue"** → POST to `/mark_learned/<fact_id>`
   - System marks fact as learned for this user
   - System redirects to quiz question
6. **System generates quiz question** → `prepare_quiz_question_for_fact(fact, domain_id, user_id)`
   - Select random field to quiz
   - Generate 4 options (1 correct, 3 wrong from other facts)
   - Shuffle options
7. **User submits answer** → POST to `/answer`
   - System validates answer correctness
   - System records attempt: `record_attempt(fact_id, field, correct, user_id, session_id)`
   - System updates consecutive counters: `update_consecutive_attempts(fact_id, correct, user_id)`
   - **If correct:**
     - Increment `consecutive_correct`, reset `consecutive_wrong` to 0
     - If `consecutive_correct >= 2`: Move to next fact
     - If `consecutive_correct < 2`: Quiz same fact again
   - **If incorrect:**
     - Increment `consecutive_wrong`, reset `consecutive_correct` to 0
     - If `consecutive_wrong >= 2`: Demote to unlearned, show fact again
     - If `consecutive_wrong < 2`: Show fact again, then re-quiz
8. **Every 3rd question**: Select from mastered facts for reinforcement
   - `select_recovery_fact(domain_id, excluded_ids, user_id)` selects mastered fact
   - Reinforcement maintains long-term retention
9. **Progress persists**: All FactState and Attempt records tied to `user_id`

### Question Generation

- Questions ask about a random field of the selected fact
- Correct answer comes from the fact being quizzed
- Wrong answers come from the same field of 3 other random facts in the domain
- Options are shuffled to prevent pattern recognition
- Field names are formatted (e.g., "domain_of_expertise" → "Domain Of Expertise")

### Engagement Metrics Calculation

#### Questions Answered Today
```python
def get_questions_answered_today(user_id):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = Attempt.query.filter(
        Attempt.user_id == user_id,
        Attempt.timestamp >= today_start
    ).count()
    return count
```

#### Total Time Spent
```python
def get_total_time_spent(user_id):
    attempts = Attempt.query.filter_by(user_id=user_id).order_by(Attempt.timestamp).all()
    if len(attempts) < 2:
        return 0
    first_attempt = attempts[0].timestamp
    last_attempt = attempts[-1].timestamp
    time_delta = last_attempt - first_attempt
    total_minutes = int(time_delta.total_seconds() / 60)
    return total_minutes
```

**Note**: Time is estimated from first to last attempt timestamp, not actual active time.

#### Unique Sessions
```python
def get_unique_session_count(user_id):
    result = db.session.query(Attempt.session_id).filter(
        Attempt.user_id == user_id,
        Attempt.session_id.isnot(None)
    ).distinct().count()
    return result
```

Each time a user clicks "Start Practice", a new UUID session ID is generated.

#### Time Formatting
```python
def format_time_spent(minutes):
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes == 0:
        return f"{hours}h"
    return f"{hours}h {remaining_minutes}m"
```

Examples: "45m", "1h", "2h 15m"

## Adding New Fact Domains

Create a JSON file in the `facts/` directory:

```json
{
  "domain_name": "US Presidents",
  "fields": ["name", "party", "years_in_office", "notable_achievement"],
  "facts": [
    {
      "name": "George Washington",
      "party": "None",
      "years_in_office": "1789-1797",
      "notable_achievement": "First President"
    },
    {
      "name": "Abraham Lincoln",
      "party": "Republican",
      "years_in_office": "1861-1865",
      "notable_achievement": "Emancipation Proclamation"
    }
  ]
}
```

**Requirements:**
- All facts must have the same fields as defined in `fields` array
- Field names are used in questions (auto-formatted: "years_in_office" → "Years In Office")
- Minimum 4 facts per domain (for multiple-choice generation)
- Domain name is used in UI and for singularization (e.g., "US Presidents" → "US President" in questions)

The application automatically loads all JSON files from `facts/` on startup.

## Adding Images to Facts

Images are supported in **teacher-created domains only** (Teacher → Domains → Create
Domain). Bundled `facts/*.json` domains are text-only.

A field value holds an image by prefixing it with the `img:` marker. Field names stay
plain strings, so a domain gains images without any schema change:

```json
{
  "name": "Erato",
  "symbol": "Lyre",
  "portrait": "img:erato.png"
}
```

The same works in a CSV cell:

```csv
name,symbol,portrait
Erato,Lyre,img:erato.png
```

**Two ways to supply the file:**

1. **Upload** — write `img:<filename>` and attach that file in the "Fact images" field
   of the create-domain form. Filenames are matched by basename, case-insensitively.
   The file is stored under `static/uploads/` with a random name, and the fact value
   is rewritten to `img:uploads/<random>.png`.
2. **External URL** — write the URL directly: `img:https://example.org/erato.png`.
   Only `https://` is accepted.

**Constraints:**
- Allowed formats: PNG, JPG, GIF, WebP (SVG is rejected — it can carry script, and
  uploads are served from our own origin)
- Format is determined by the file's leading bytes, so a renamed file is rejected
- 5MB per image, 25MB per whole request
- Every `img:` reference must resolve to an upload or an `https://` URL; anything else
  fails the whole domain creation, and any files already stored are cleaned up

**Quizzing behaviour:** when the context field is an image, the question text points at
it ("What is the symbol of *this greek muse*?"). When the answer field is an image, all
four options render as images. A field is only quizzed as an image answer if the domain
has at least 3 other distinct images in that field, so the option grid does not end up
mixing images with text placeholders.

## Testing

### Running Tests

**Run all tests:**
```bash
pytest
```

**Run with verbose output:**
```bash
pytest -v
```

**Run with detailed coverage report:**
```bash
pytest --cov=. --cov-report=html
```

Then open `htmlcov/index.html` in your browser.

**Run specific test files:**
```bash
pytest tests/test_auth.py
pytest tests/test_authorization.py
pytest tests/test_multi_user.py
```

**Run tests by marker:**
```bash
pytest -m auth              # Authentication tests
pytest -m authorization     # Authorization tests
pytest -m models            # Model tests
```

### Test Suite Overview

**269 tests** across 14 test files:

1. **test_routes.py** (43 tests): Flask routes and quiz flows
2. **test_image_fields.py** (42 tests): Image markers, uploads, resolution, rendering
3. **test_models.py** (33 tests): Database models, learning states, fact state transitions
4. **test_quiz_logic.py** (23 tests): Quiz generation, fact selection, spaced repetition
5. **test_auth.py** (18 tests): User creation, authentication, login/logout, password setup
6. **test_streak_service.py** (17 tests): Practice streaks and daily goals
7. **test_multi_user.py** (17 tests): Progress isolation, domain assignment, engagement metrics
8. **test_authorization.py** (16 tests): Role-based access control, organization isolation
9. **test_domain_creation.py** (16 tests): Teacher domain creation via form and CSV
10. **test_facts_loader.py** (16 tests): JSON loading and validation
11. **test_doom_loop.py** (11 tests): Recovery mode logic
12. **test_duplicate_symbols.py** (8 tests): Duplicate field values in answer options
13. **test_template_filters.py** (5 tests): Jinja2 filter tests
14. **test_fact_service.py** (4 tests): Fact learning state transitions

**Code Coverage:** 71% overall

Well covered:
- models.py: 99% · fact_service: 99% · progress_service: 97% · image_service: 97%
- facts_loader: 94% · domain_service: 93% · user_service: 92% · quiz_logic: 89%

Gaps worth knowing about — these ship without tests:
- `services/analytics_service.py`, `services/group_service.py`,
  `services/template_service.py`, `services/bulk_import_service.py`: **0%**
- `blueprints/analytics.py`: 27% · `blueprints/teacher.py`: 40% ·
  `blueprints/admin.py`: 48%

The root utility scripts (`rebuild_db.py`, `verify_database.py`, etc.) are not
covered by design — they are operator tools, not application code.

### Test Fixtures

Defined in `tests/conftest.py`:

**App Fixtures:**
- `app`: Test Flask application with temporary database
- `client`: Test client for making requests
- `db_session`: Database session for tests

**User Fixtures:**
- `admin_user`: Admin user (email: admin@test.com, password: adminpass123)
- `teacher_user`: Teacher user (email: teacher@test.com, password: teacherpass123)
- `student_user`: Student user (email: student@test.com, password: studentpass123)
- `second_student`: Second student for isolation tests

**Authenticated Client Fixtures:**
- `authenticated_admin`: Client logged in as admin
- `authenticated_teacher`: Client logged in as teacher
- `authenticated_student`: Client logged in as student

**Domain Fixtures:**
- `populated_db`: Database with sample facts (5 Greek Muses)
- `assigned_domain`: Domain assigned to student_user
- `user_with_progress`: Student with quiz progress (2 learned facts, 5 attempts)

### Writing New Tests

```python
class TestFeatureName:
    """Test description."""

    def test_specific_behavior(self, app, authenticated_student, assigned_domain):
        """Test that specific behavior works correctly."""
        with app.app_context():
            # Arrange
            facts = Fact.query.filter_by(domain_id=assigned_domain.id).all()

            # Act
            mark_fact_learned(facts[0].id, authenticated_student.id)

            # Assert
            assert is_fact_learned(facts[0].id, authenticated_student.id) is True
```

## Security Features

### Password Security

- **Hashing algorithm**: Werkzeug scrypt (PBKDF2-based, industry-standard)
- **No plaintext storage**: Passwords never stored in plaintext
- **Minimum length**: 8 characters enforced
- **Token-based setup**: Users set their own passwords (no shared passwords)
- **Constant-time comparison**: Prevents timing attacks

### Session Security

- **Secret key**: Strong SECRET_KEY generated with `secrets.token_hex(32)`
- **HttpOnly cookies**: Prevents JavaScript access to session cookies
- **Secure flag**: HTTPS-only cookies (set `SESSION_COOKIE_SECURE=True` in production)
- **Session timeout**: 24-hour default (configurable)
- **Session regeneration**: Session ID regenerated on login
- **Logout clears session**: Complete session termination on logout

### Authorization Security

- **Role verification**: Every protected route checks role via decorator
- **Resource ownership**: Students can only access their own progress
- **Organization isolation**: Teachers only access students in their organization
- **Domain assignment**: Students can only quiz assigned domains
- **Parameterized queries**: SQLAlchemy prevents SQL injection
- **Input validation**: Email format, password requirements, field validation

### Token Security

- **Setup tokens**: Cryptographically secure UUID tokens
- **Token expiration**: 7-day validity window
- **Single use**: Tokens invalidated after password setup
- **Token validation**: Existence, expiration, and user activation checks

### Common Attack Mitigations

- **SQL Injection**: Parameterized queries via SQLAlchemy ORM
- **XSS**: Automatic HTML escaping in Jinja2 templates
- **CSRF**: Flask-WTF CSRF protection (if forms use Flask-WTF)
- **Session Hijacking**: Secure session cookies with HttpOnly and Secure flags
- **Brute Force**: Rate limiting recommended (not built-in, add Flask-Limiter)
- **Password Leaks**: Scrypt hashing makes rainbow table attacks infeasible

## Deployment Considerations

### Production Checklist

- [ ] Generate strong SECRET_KEY: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Set `SESSION_COOKIE_SECURE=True` for HTTPS
- [ ] Set `SESSION_COOKIE_HTTPONLY=True` (default)
- [ ] Configure email server for setup link delivery
- [ ] Set up database backups
- [ ] Use production WSGI server (gunicorn, waitress, uwsgi)
- [ ] Configure reverse proxy (nginx, Apache)
- [ ] Enable HTTPS/TLS certificates (Let's Encrypt)
- [ ] Set up logging and monitoring
- [ ] Configure firewall rules
- [ ] Set environment variables (don't hardcode secrets)

### Environment Variables

Recommended environment variables for production:

```bash
export FLASK_ENV=production
export SECRET_KEY=<generated-secret-key>
export DATABASE_URL=<production-database-url>
export MAIL_SERVER=<smtp-server>
export MAIL_PORT=587
export MAIL_USERNAME=<email-username>
export MAIL_PASSWORD=<email-password>
export MAIL_USE_TLS=True
```

### Database Scaling

Current SQLite limitations:
- Single-file database
- Not ideal for high-concurrency writes
- No built-in replication

**For production at scale**, consider migrating to PostgreSQL:
1. Update `SQLALCHEMY_DATABASE_URI` in app.py
2. Install psycopg2: `pip install psycopg2-binary`
3. SQLAlchemy handles the rest (same models, same queries)

### Email Configuration

Currently, the app attempts to send emails via `send_setup_email()` but falls back to displaying links if email fails.

**To enable email:**
1. Configure `app.config['MAIL_SERVER']` and related settings
2. Install Flask-Mail: `pip install Flask-Mail`
3. Update `send_setup_email()` function to use Flask-Mail
4. Set environment variables for SMTP credentials

**Fallback behavior** (default):
- If email sending fails, setup link is displayed in flash message
- Admin/teacher can copy link and share via other channels (Slack, etc.)
- This ensures account creation never fails due to email issues

## Known Limitations

### Current Limitations

1. **Single Organization**: Schema supports multiple organizations, but UI assumes single org
   - Future: Add org switcher, multi-org admin dashboard

2. **Email Delivery**: No built-in email server integration
   - Workaround: Display setup links in UI for manual sharing
   - Future: Integrate Flask-Mail with configurable SMTP

3. **Password Reset**: No self-service password reset flow
   - Workaround: Teacher/admin creates new account or manually resets password in database
   - Future: Add "Forgot Password" flow with email-based reset

4. **Time Tracking**: Time spent is estimated (first to last attempt)
   - Not actual active engagement time
   - Future: Add client-side activity tracking with heartbeat pings

5. **Bulk Operations**: No bulk import/export for students or assignments
   - Workaround: Create students one by one
   - Future: Add CSV import, bulk assignment UI

6. **Advanced Analytics**: No charts, graphs, or comparison views
   - Workaround: Export database and analyze externally
   - Future: Add visualization dashboard with charts

7. **Mobile App**: Web-only (responsive design works on mobile browsers)
   - Future: Consider native mobile app or PWA

8. **Real-Time Notifications**: No live updates when teacher views student progress
   - Workaround: Refresh page manually
   - Future: Add WebSocket support for live updates

### Performance Notes

- **Tested with**: Up to 50 students per teacher, 100+ facts per domain
- **Expected performance**: <100ms response times for typical queries
- **Scaling considerations**: Add indexes, consider PostgreSQL for >1000 users

## License

MIT

## Contributing

Contributions welcome! Please ensure:
- All tests pass: `pytest`
- Code formatted with Black: `black .`
- Code passes Flake8: `flake8 .`
- New features include tests
- Documentation updated

## Support

For issues, questions, or feature requests, please file an issue on GitHub.

## Changelog

### Unreleased - Fact Images
- Fact fields can hold images via an inline `img:` marker (no schema change)
- Teachers upload image files or reference `https://` URLs, in both form and CSV authoring
- Images work as quiz question context and as answer options
- Uploads validated by file signature, capped at 5MB each / 25MB per request, SVG rejected
- Added `services/image_service.py` and 42 tests in `tests/test_image_fields.py`

### v3.0 (2026-01-19) - Multi-User System
- Added three-role authentication system (Admin, Teacher, Student)
- Implemented token-based password setup with magic links
- Added organization isolation schema
- Added domain assignment management
- Added progress isolation per user
- Added engagement metrics (questions today, time spent, sessions)
- Added teacher dashboard with student management
- Added student dashboard with assigned domains
- Added 70+ new tests for auth and multi-user functionality
- Total: 162+ tests with >90% code coverage

### v2.1 (Previous)
- Automatic database initialization
- Smart domain name singularization
- Fixed spaced repetition timing
- 92 tests with 98% coverage

### v2.0 (Previous)
- Three-state learning system (Unlearned → Learned → Mastered)
- Fact display requirement before quizzing
- Consecutive correct/wrong tracking
- Automatic demotion after 2 wrong answers
- Progress reset functionality
- New fact_states table

### v1.0 (Initial)
- Basic quiz functionality
- SQLite persistence
- Multiple-choice questions
- Terminal aesthetic
