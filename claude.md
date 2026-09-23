# Rememberizer Development Log

This document tracks major changes, refactorings, and architectural decisions made during development.

---

## 2026-01-19: Major Refactoring - Blueprint Architecture

### Overview
Completed a comprehensive refactoring to improve code organization and maintainability. The monolithic `app.py` (1,655 lines) has been split into modular Flask blueprints.

### Phase 1: Blueprint Extraction ✅

#### Changes Made

**1. Created Blueprint Structure**
```
blueprints/
├── __init__.py
├── admin.py          # Admin dashboard and teacher management
├── auth_routes.py    # Login, logout, password setup
├── quiz.py           # Quiz functionality and public routes
├── student.py        # Student domain selection and progress
└── teacher.py        # Teacher dashboard, domain/student management
```

**2. Refactored app.py**
- **Before**: 1,655 lines with 27+ routes
- **After**: 200 lines (88% reduction!)
- Now focuses on: configuration, database initialization, template filters, and blueprint registration

**3. Blueprint Details**

**admin.py** (3 routes):
- `/admin/dashboard` - Admin dashboard with stats
- `/admin/teachers/create` - Create new teachers
- `/admin/teachers/<id>/deactivate` - Deactivate teachers

**auth_routes.py** (3 routes):
- `/login` (GET, POST) - User authentication with role-based redirects
- `/logout` - Session clearing
- `/setup-password/<token>` (GET, POST) - First-time password setup
- Includes email notification helpers

**teacher.py** (11 routes):
- `/teacher/dashboard` - Student progress overview
- `/teacher/domains` - Domain management
- `/teacher/domains/create` - Domain creation (form & CSV)
- `/teacher/domains/<id>/publish` - Toggle domain visibility
- `/teacher/students/create` - Create new students
- `/teacher/students/<id>` - Student detail view
- `/teacher/students/<id>/assign` - Assign domain to student
- `/teacher/students/<id>/unassign` - Unassign domain from student
- `/teacher/students/<id>/reset-domain/<domain_id>` - Reset student progress
- `/teacher/students/<id>/deactivate` - Deactivate students

**student.py** (2 routes):
- `/student/domains` - View assigned domains
- `/student/progress` - Personal progress overview

**quiz.py** (9 routes):
- `/` - Landing page with role-based redirects
- `/start` - Initialize quiz session
- `/show_fact/<id>` - Display fact in table format
- `/mark_learned/<id>` - Mark fact as learned
- `/quiz` - Generate and display quiz question
- `/answer` - Process quiz answer
- `/reset_domain` - Reset current domain progress
- `/reset_domain_from_menu/<id>` - Reset specific domain
- `/reset` - Clear session (testing)

**4. Updated All URL References**

Updated ~100+ `url_for()` calls across:
- **Python files**: All blueprints, auth.py
- **Templates** (16 files): All HTML templates updated with blueprint names

**Example mappings**:
```python
# Old
url_for('admin_dashboard')
url_for('teacher_dashboard')
url_for('student_domains')
url_for('login')

# New
url_for('admin.dashboard')
url_for('teacher.dashboard')
url_for('student.domains')
url_for('auth.login')
```

**5. Fixed Authentication Integration**
- Updated `auth.py`: `login_manager.login_view = "auth.login"`
- Updated `role_required()` decorator to use blueprint names
- Fixed test expectations (302 redirects instead of 403)

#### Testing
- ✅ All 188 tests passing
- ✅ 83% code coverage maintained
- ✅ No functionality broken
- ✅ All authentication flows working
- ✅ All role-based access controls intact

#### Benefits
1. **Better Code Organization**: Related routes grouped by functionality
2. **Improved Maintainability**: Each blueprint is focused and < 300 lines
3. **Easier Testing**: Can test blueprints independently
4. **Scalability**: Easy to add new features without bloating app.py
5. **Team Development**: Different developers can work on different blueprints
6. **Clear Separation**: Auth, admin, teacher, student, and quiz concerns isolated

#### File Size Comparison
| File | Before | After | Change |
|------|--------|-------|--------|
| app.py | 1,655 lines | 200 lines | -88% |
| admin.py | - | 113 lines | New |
| auth_routes.py | - | 147 lines | New |
| teacher.py | - | 294 lines | New |
| student.py | - | 79 lines | New |
| quiz.py | - | 208 lines | New |
| **Total** | 1,655 lines | 1,041 lines | -37% overall |

### Phase 2: Service Layer Extraction ✅

Completed extraction of all business logic from `models.py` into focused service modules.

#### Changes Made

**1. Created Service Layer Structure**
```
services/
├── __init__.py
├── fact_service.py       # Fact learning states and attempts (288 lines)
├── user_service.py       # User management & authentication (128 lines)
├── domain_service.py     # Domain assignment & visibility (230 lines)
└── progress_service.py   # Progress tracking & statistics (164 lines)
```

**2. Refactored models.py**
- **Before**: 1,072 lines (models + 31 business logic functions)
- **After**: 177 lines (ONLY database models!)
- **Reduction**: 83% smaller - pure SQLAlchemy models now

**3. Service Modules Created**

**fact_service.py** (13 functions):
- `get_mastery_status()` - Check if fact is mastered
- `get_mastered_facts()` - Get all mastered facts in domain
- `record_attempt()` - Record quiz attempt
- `get_unmastered_facts()` - Get unmastered facts
- `get_attempt_count()` - Get total attempts for fact
- `mark_fact_learned()` - Mark fact as learned
- `mark_fact_shown()` - Track when fact was displayed
- `is_fact_learned()` - Check if fact is learned
- `get_unlearned_facts()` - Get unlearned facts
- `get_learned_facts()` - Get learned but not mastered facts
- `update_consecutive_attempts()` - Update consecutive counters
- `has_two_consecutive_correct()` - Check for 2 consecutive correct
- `reset_domain_progress()` - Reset all progress for domain

**user_service.py** (3 functions):
- `create_user()` - Create new users with validation
- `authenticate_user()` - Authenticate by email/password
- `get_students_by_teacher()` - Get students in teacher's org

**domain_service.py** (8 functions):
- `get_user_domains()` - Get assigned domains for user
- `assign_domain_to_user()` - Assign domain to student
- `unassign_domain_from_user()` - Remove domain assignment
- `is_domain_assigned()` - Check if domain is assigned
- `create_custom_domain()` - Create custom domain from CSV/form
- `update_domain_published_status()` - Toggle published status
- `get_visible_domains()` - Get domains visible to user
- `is_domain_visible_to_teacher()` - Check domain visibility

**progress_service.py** (7 functions):
- `get_progress_string()` - Generate visual progress string (·-+*)
- `get_student_progress_summary()` - Comprehensive progress summary
- `get_student_domain_progress()` - Detailed domain progress
- `get_questions_answered_today()` - Count today's questions
- `get_total_time_spent()` - Calculate total time spent
- `get_unique_session_count()` - Count unique sessions
- `format_time_spent()` - Format minutes to human-readable

**4. Updated All Imports**

Updated imports across entire codebase (17 files):
- app.py, blueprints (5 files), quiz_logic.py, doom_loop.py
- tests (9 files including conftest.py)
- Separated model imports from service imports
- Clean separation of concerns maintained

#### Testing
- ✅ All 188 tests passing
- ✅ 83% code coverage maintained
- ✅ No functionality broken
- ✅ All business logic working correctly
- ✅ Clean imports throughout codebase

#### Benefits
1. **Clean Separation of Concerns**: Database models vs. business logic
2. **Single Responsibility**: Each service has one clear purpose
3. **Easier Testing**: Can test services independently from database
4. **Better Organization**: Related functions grouped logically
5. **Improved Maintainability**: Smaller, focused modules
6. **Cleaner Imports**: Clear dependencies between layers

#### File Size Comparison
| File | Before | After | Change |
|------|--------|-------|--------|
| models.py | 1,072 lines | 177 lines | -83% |
| fact_service.py | - | 288 lines | New |
| user_service.py | - | 128 lines | New |
| domain_service.py | - | 230 lines | New |
| progress_service.py | - | 164 lines | New |
| **Total** | 1,072 lines | 987 lines | -8% overall (better organized) |

#### Architecture After Phase 2
```
rememberizer/
├── models.py              # 177 lines - ONLY SQLAlchemy models
├── services/              # Business logic layer
│   ├── fact_service.py    # Fact learning operations
│   ├── user_service.py    # User management
│   ├── domain_service.py  # Domain operations
│   └── progress_service.py# Progress tracking
├── blueprints/            # Route handlers
│   ├── admin.py
│   ├── auth_routes.py
│   ├── quiz.py
│   ├── student.py
│   └── teacher.py
├── quiz_logic.py          # Quiz question generation
└── doom_loop.py           # Spaced repetition algorithm
```

---

## 2026-09-23: Photo Roster Import

### Overview
Teachers can now build a whole photo domain from the two files a school MIS already
exports: a roster CSV and a gallery of photos. Create Domain gains a third tab,
**[PHOTO ROSTER]**, alongside form entry and CSV upload.

### The Convention
The CSV's **first column is the photo's filename without its extension** - which is how
MIS exports already work (`10482` in the CSV, `10482.jpg` in the gallery):

```
ManagementSystemID,Surname,Forename,YearGroup,TutorGroup
10482,Wright,Alex,Year 9,9B
```

becomes

```python
{"photo": "img:uploads/a3f9c1e8.jpeg", "surname": "Wright", "forename": "Alex",
 "year_group": "Year 9", "tutor_group": "9B"}
```

The key column is **replaced**, not kept: "What is the management system id of this
student?" is not a question worth asking, and the photo sitting first makes it the
domain's identifying field, which is what gives "What is the surname of this student?"
instead of an attempt to interpolate an image into a sentence. See ARCHITECTURE.md
decision 10.

Nothing new reaches the database: the import produces ordinary facts carrying ordinary
`img:` values, so quizzing, grading and rendering were already done by the fact-images
work above.

### Changes Made

**1. New service: `services/photo_roster_service.py`** (476 lines)
- `normalise_field_name` - `YearGroup` -> `year_group`, so the quiz says "year group"
- `photo_key` - basename minus extension, lowercased; matches `photos/10482.JPG` to `10482`
- `collect_photo_files` - index a folder-picker submission, ignoring non-images and
  dot-files (a folder picker sends *everything* in the folder)
- `collect_zip_photos` - same index from a zip, so the MIS bundle needs no unzipping.
  Entry size is checked from the zip header *before* reading, plus caps on entry count
  and expanded total
- `decode_csv` - UTF-8 (BOM tolerated) falling back to cp1252, because exports go
  through Excel
- `parse_roster_csv` / `resolve_included_headers` - headers and optional column picker
- `build_photo_facts` - assembles facts, stores only matched photos, rolls back every
  stored photo if anything later fails
- `format_import_report` - what was skipped and why, truncated after 10 names

**2. `blueprints/teacher.py`**
- `POST /teacher/domains/import-photos`, discarding stored photos on every error path
- `create_domain_form` now takes `?tab=` so a failed import reopens its own tab

**3. `templates/teacher/create_domain.html`**
- Third tab; `showTab()` generalised over a list of tab names
- Folder picker (`webkitdirectory`) *or* zip upload, photo field name, columns to quiz
- JS previews the match count and **filters the folder selection before upload**, so a
  form-room gallery does not push a 25MB request. The server re-checks everything; the
  JS is bandwidth and reassurance only, and falls back to sending the lot

### Decisions Worth Remembering
- **Skipping beats rejecting**: a row with no photo is dropped and reported. An export
  routinely covers students without a photo and the teacher cannot fix that from here
- **Unmatched photos are never stored**: the gallery is usually wider than the roster
- **Collisions are errors**: two headers that tidy to one field name, a header that
  cannot be named, or a column clashing with the photo field all fail loudly rather
  than silently losing a column
- **Privacy**: created unpublished like any custom domain, and the docs on the tab say
  to keep a domain of student photos that way

### Testing
- 57 new tests in `tests/test_photo_roster_import.py` (`photo_roster_service` at 99%)
- 326 tests passing overall, coverage 71% -> 73%, `blueprints/teacher.py` 40% -> 44%
- `black --check .` and `flake8 .` clean

---

## 2026-09-01: Fact Images

### Overview
Fact fields can now hold images as well as text, in teacher-created domains.

### Data Model: Inline Markers
An image is a field **value** prefixed with `img:`, not a typed field:

```python
{"name": "Erato", "symbol": "Lyre", "portrait": "img:uploads/a3f9c1e8.png"}
{"name": "Erato", "portrait": "img:https://example.org/erato.png"}
```

Chosen over a `field_types` map or per-fact image columns because it needs **no schema
change and no migration**: `Domain.field_names` stays a list of plain strings, its ~10
consumers were untouched, and `/answer` grading still compares raw strings. The cost is
that there is nowhere to store real alt text — see ARCHITECTURE.md decision 9.

### Changes Made

**1. New service: `services/image_service.py`** (316 lines)
- `is_image_value` / `image_reference` / `is_external_reference` — marker parsing
- `detect_image_type` — PNG/JPEG/GIF/WebP identified by signature, not extension
- `save_uploaded_image` / `save_uploaded_images` — validate and store under a
  `uuid4` name; roll back already-stored files if a later file is rejected
- `discard_uploaded_images` — clean up when domain creation fails
- `resolve_image_references` — rewrite `img:erato.png` to the stored path by matching
  uploads on basename; pass `https://` through; reject everything else
- `image_src` / `learn_card_alt` — template helpers

**2. `app.py`**
- `UPLOAD_FOLDER` config (`static/uploads`, created at startup)
- `MAX_CONTENT_LENGTH` = 25MB with a 413 errorhandler
- Three Jinja hooks: `image_value` test, `image_src` filter, `learn_card_alt` global

**3. `quiz_logic.py`**
- `generate_question` returns a new `context_image` key. An image cannot be
  interpolated into a sentence, so when the context is an image the question points at
  it instead ("What is the symbol of this greek muse?")
- `has_enough_image_distractors` — an image answer needs 3 other distinct images, or
  the option grid would mix images with `"Option 2"` text placeholders
- `_choose_field_pair` — extracted from the identical retry loops duplicated in
  `prepare_quiz_question` and `prepare_quiz_question_for_fact`, now also applying the
  distractor check

**4. `blueprints/teacher.py`** — both the form and CSV branches of `create_domain`
save uploads, resolve references, and discard uploads on every error path.

**5. Templates** — `show_fact.html` (value cell), `quiz.html` (question context and
options), `teacher/create_domain.html` (file inputs and authoring docs on both tabs).

### Security Notes
- **SVG rejected**: it can carry script and uploads are served from our own origin
- **Random stored filenames**: the uploaded name is often the answer ("erato.png"), so
  it is kept out of the page source
- **Position-dependent alt text**: descriptive on the learn card, generic ("Option 2")
  in a quiz, so alt text cannot leak the answer
- **Traversal closed at authoring time**: a local reference that matches no upload is
  rejected outright; deletion resolves by basename against the upload folder

### Bug Found While Testing
`discard_uploaded_images` rebuilt paths from `current_app.static_folder` while saves
went to `UPLOAD_FOLDER`. Wherever those differ (a mounted volume in deployment) saves
would succeed and deletes silently no-op, orphaning every file forever. Both now use
`_upload_folder()`.

### Testing
- ✅ 42 new tests in `tests/test_image_fields.py`
- ✅ 269 tests passing overall
- ✅ `facts_loader.py` untouched — bundled `facts/*.json` domains stay text-only,
  by design

---

## 2026-09-01: CI Lint Backlog & Doc Accuracy Pass

### The Problem
CI was already red on `main`, independent of any feature work: `black --check .` wanted
to reformat 18 files and `flake8 .` reported 75 errors on a clean checkout.

**Root cause**: `requirements-dev.txt` pinned `black>=23.0.0` and `flake8>=6.1.0`, so CI
installed whatever was newest at build time. Black's formatting rules changed between
releases, and a PR that was green at merge went red later with no code change at all.

### Fixes

**1. Pinned the CI gates exactly** — `black==26.5.1`, `flake8==7.3.0`. Bump them
deliberately, reformatting in the same commit. The other dev deps stay on ranges since
nothing gates on them.

**2. Applied Black repo-wide** (18 files) — purely mechanical.

**3. Cleared all 75 Flake8 errors.** Not all were mechanical:
- **F401 kept deliberately**: `rebuild_db.py` imports `FactState`, `Attempt` and
  `UserDomainAssignment` for their side effect — a model must be registered before
  `db.create_all()` gives it a table. Marked `# noqa: F401` with a comment rather than
  removed, which would have silently stopped creating three tables
- **F401 removed**: genuinely dead imports in `blueprints/quiz.py` (including a
  `login_required` imported inside `celebrate()` that was never applied — the route
  hand-rolls its `current_user.is_authenticated` check instead), `analytics.py`,
  `analytics_service.py`, `template_service.py`, and two test files
- **E402 kept**: `# noqa: E402` where imports must follow `sys.path.insert()`
- **E722**: bare `except:` in `rebuild_db.py` → `except Exception:`
- **F541 / E501**: mechanical (dropped redundant `f` prefixes, wrapped long lines)

### Doc Accuracy
The project trees in README.md and ARCHITECTURE.md still described the pre-blueprint,
pre-service layout — "app.py: ALL routes", "models.py: models + business logic", no
`blueprints/` or `services/` at all. Both are now accurate, along with
"Separation of Concerns" and "Dependency Flow".

**Coverage claims were false.** README claimed ">90% code coverage"; actual is **71%**.
Four services are at **0%** — `analytics_service`, `group_service`, `template_service`,
`bulk_import_service` all shipped untested, and `blueprints/analytics.py` sits at 27%.
README now states the real number and names the gaps instead of hiding them.

### Result
- ✅ `black --check .` clean (54 files)
- ✅ `flake8 .` clean (0 errors)
- ✅ 269 tests passing

---

## Previous Work

### Multi-User Authentication System
- Implemented role-based access control (admin, teacher, student)
- Added organization isolation
- Created user management flows
- Token-based password setup
- Session management with Flask-Login

### Test Coverage
- 326 tests, 73% overall coverage (as of 2026-09-23)
- Tests organized by feature area
- Fixtures for authenticated users and test data
- Untested: analytics_service, group_service, template_service,
  bulk_import_service (all 0%) - shipped without tests, worth backfilling

### Branch Protection
- Main branch requires passing CI tests
- Direct pushes blocked for all users (including admins)
- All changes must go through feature branches and PRs

---

## Architecture Notes

### Current Structure
```
rememberizer/
├── app.py                 # Flask app, config, filters, DB init
├── auth.py                # Flask-Login integration
├── models.py              # SQLAlchemy models only
├── quiz_logic.py          # Quiz question generation
├── facts_loader.py        # Load domains from JSON
├── doom_loop.py           # Spaced repetition algorithm
├── services/              # Business logic layer
│   ├── fact_service.py
│   ├── user_service.py
│   ├── domain_service.py
│   ├── progress_service.py
│   ├── analytics_service.py
│   ├── bulk_import_service.py
│   ├── group_service.py
│   ├── streak_service.py
│   ├── template_service.py
│   ├── image_service.py   # Fact images
│   └── photo_roster_service.py  # Domain from roster CSV + photos (NEW!)
├── blueprints/            # Route handlers
│   ├── admin.py
│   ├── auth_routes.py
│   ├── quiz.py
│   ├── student.py
│   └── teacher.py
├── templates/             # Jinja2 templates
│   ├── admin/
│   ├── student/
│   └── teacher/
├── tests/                 # Pytest test suite
├── facts/                 # Domain JSON files
└── static/
    └── uploads/           # Teacher-uploaded fact images (gitignored)
```

### Technology Stack
- **Backend**: Flask, SQLAlchemy, Flask-Login
- **Frontend**: Jinja2 templates, minimal CSS (terminal aesthetic)
- **Database**: SQLite
- **Testing**: Pytest, Flask test client
- **CI**: GitHub Actions (Black, Flake8, Pytest)

---

## Development Workflow

1. **Feature branches**: All work done on `feature/*` branches
2. **Testing**: Run `pytest tests/` before commits
3. **Linting**: Black and Flake8 run in CI
4. **Pull Requests**: Required for merging to main
5. **CI must pass**: Green checks required before merge

---

*Last updated: 2026-09-23*
