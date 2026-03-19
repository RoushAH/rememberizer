# Database Persistence Testing Guide

## Summary of Changes

The database configuration has been updated to use an **absolute path** to the `instance/database.db` file, fixing the persistence issue where data was lost across application restarts.

### What Changed

**Before:**
```python
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"  # Relative path
```

**After:**
```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'database.db')  # Absolute path
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
```

## Verification Steps

### 1. Verify Database Configuration

Run the verification script to confirm the database is properly configured:

```bash
python verify_database.py
```

**Expected Output:**
```
======================================================================
DATABASE VERIFICATION
======================================================================

[OK] Database configured at:
  C:\Users\Adam Work\PycharmProjects\rememberizer\instance\database.db

[OK] Database file exists:
  Size: 61,440 bytes (60.0 KB)
  Last modified: 2026-01-20 09:53:34

[OK] Database contains:
  Domains: 2
  Users: 0
  Domain assignments: 0

[OK] Sample domains:
  - Chinese Dynasties (published)
  - Greek Muses (published)

======================================================================
[SUCCESS] DATABASE IS CORRECTLY CONFIGURED AND CONTAINS DATA
======================================================================
```

### 2. Test Persistence Across Restarts

#### Step 2a: Create Test Data

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Navigate to `http://localhost:5000` in your browser

3. Create an admin account (if prompted) or log in

4. Create a test student:
   - Go to teacher dashboard
   - Create a new student (e.g., "test@student.com")
   - Assign a domain to the student

5. Log in as the test student and answer several quiz questions

6. Note down the progress (e.g., "3 facts learned, 5 attempts")

#### Step 2b: Restart Application

1. **Stop the Flask application** (Ctrl+C in the terminal)

2. **Verify database file was modified:**
   ```bash
   ls -lh instance/database.db
   ```
   Check that the timestamp is recent.

3. **Restart the application:**
   ```bash
   python app.py
   ```

4. **Verify startup message shows correct path:**
   Look for this in the console output:
   ```
   Database configured at: C:\Users\Adam Work\PycharmProjects\rememberizer\instance\database.db
   [OK] Existing database found at: ...
     Database has 2 domains
   ```

#### Step 2c: Verify Data Persisted

1. Log in as the test student

2. Navigate to their progress page

3. **Expected:** All progress from Step 2a is still present:
   - Same number of facts learned
   - Same attempt count
   - Progress strings show same state (`·-+*` symbols match)

### 3. Test Multiple Restart Cycles

Repeat the following 3 times:
1. Answer 2-3 quiz questions
2. Stop the application
3. Restart the application
4. Verify all previous progress is still present

### 4. Test Working Directory Independence

This test confirms the fix works regardless of where the app is launched from:

1. Stop the application

2. Change to parent directory:
   ```bash
   cd ..
   ```

3. Start the app from parent directory:
   ```bash
   python rememberizer/app.py
   ```

4. **Expected:**
   - Console shows same database path
   - All data is still present
   - No new database files created

## Success Criteria

- ✅ Database path is absolute and always points to `instance/database.db`
- ✅ Application finds existing database on every startup
- ✅ Progress persists across multiple restart cycles
- ✅ Database file in `instance/` folder is being modified when data changes
- ✅ Launching from different directories doesn't affect database location
- ✅ All 191 tests still pass
- ✅ No data loss after restarts

## Test Results

All tests passed successfully:
```bash
pytest tests/ -v --tb=short
# Result: 191 passed in 59.43s
```

## Troubleshooting

### Issue: Database file exists but has no tables

**Symptom:** Verification script shows "no such table: domains"

**Solution:** Initialize the database:
```bash
python init_db.py
```

### Issue: Data is not persisting

**Check these:**

1. **Verify database path in console output:**
   ```
   Database configured at: C:\Users\Adam Work\PycharmProjects\rememberizer\instance\database.db
   ```

2. **Check file is being modified:**
   ```bash
   ls -lh instance/database.db
   ```
   Timestamp should update when you make changes in the app.

3. **Verify no other database files exist:**
   ```bash
   find . -name "database.db" -o -name "*.db"
   ```
   Should only find `instance/database.db`.

### Issue: Tests are failing

**Most likely cause:** Tests use temporary databases and should not be affected.

If tests fail, check:
1. Run pytest with verbose output: `pytest -v`
2. Check if `conftest.py` properly sets up temporary databases for tests
3. Ensure tests don't hardcode database paths

## Additional Information

### Database Backups

To manually backup the database:

```bash
cp instance/database.db instance/database_backup_$(date +%Y%m%d_%H%M%S).db
```

### Database Location

The database will ALWAYS be at:
```
C:\Users\Adam Work\PycharmProjects\rememberizer\instance\database.db
```

This is **independent** of:
- Current working directory
- Where the app is launched from
- Virtual environment location

## Next Steps

For production deployment, consider:

1. **Environment variable configuration:**
   - Set `DATABASE_PATH` environment variable
   - Allows different database locations per environment

2. **Automated backups:**
   - Backup database on application startup
   - Keep last N backups with timestamps

3. **Database migrations:**
   - Use Flask-Migrate or Alembic
   - Track schema changes over time

4. **Monitoring:**
   - Log database file size on startup
   - Alert if database grows too large
