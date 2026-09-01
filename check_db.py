import sqlite3

conn = sqlite3.connect("instance/database.db")
cursor = conn.cursor()

# Check all objects in database
cursor.execute("SELECT type, name, sql FROM sqlite_master ORDER BY type, name;")
objects = cursor.fetchall()

print(f"Total database objects: {len(objects)}\n")

if len(objects) == 0:
    print("DATABASE IS EMPTY - No tables, indexes, or other objects found!")
else:
    for obj_type, name, sql in objects:
        print(f"{obj_type.upper()}: {name}")
        if sql:
            print(f"  SQL: {sql[:100]}...")
        print()

conn.close()
