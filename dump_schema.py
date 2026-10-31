import sqlite3

conn = sqlite3.connect("instance/subscription_system.db")
c = conn.cursor()

output = []
for name, sql in c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"):
    output.append(f"-- ==========================================\n-- TABLE: {name}\n-- ==========================================\n{sql};\n")

conn.close()

with open("instance/schema.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Schema dumped to instance/schema.sql successfully!")
