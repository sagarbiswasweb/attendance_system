import sqlite3
import oracledb
from datetime import datetime

# =========================
# CONFIG
# =========================

SQLITE_DB = r"C:\Program Files (x86)\ZKBio Time.Net\TimeNet.db"

ORACLE_CONFIG = {
    "user": "NBNI_ERP",
    "password": "NBNI_ERP",
    "host": "192.168.3.8",
    "port": 1521,
    "service_name": "orcl19c"
}

# =========================
# SQLITE CONNECT
# =========================

sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_cur = sqlite_conn.cursor()

# =========================
# ORACLE CONNECT
# =========================

oracle_conn = oracledb.connect(
    user=ORACLE_CONFIG["user"],
    password=ORACLE_CONFIG["password"],
    host=ORACLE_CONFIG["host"],
    port=ORACLE_CONFIG["port"],
    service_name=ORACLE_CONFIG["service_name"]
)

oracle_cur = oracle_conn.cursor()

# =========================
# FETCH DATA FROM SQLITE
# =========================

rows = sqlite_cur.execute("""
SELECT
    id,
    employee_id,
    punch_time,
    terminal_id,
    punch_type,
    attendance_event
FROM att_punches
WHERE processed = 0 OR processed IS NULL
""").fetchall()

print(f"Found {len(rows)} records to sync")

# =========================
# INSERT INTO ORACLE
# =========================

inserted = 0

for row in rows:

    try:
        # convert datetime safely (fix ORA-01861 issue)
        punch_time = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")

        oracle_cur.execute("""
            INSERT INTO ATTENDANCE_LOG
            (
                ID,
                EMPLOYEE_ID,
                PUNCH_TIME,
                TERMINAL_ID,
                PUNCH_TYPE,
                ATTENDANCE_EVENT
            )
            VALUES
            (
                :1,:2,:3,:4,:5,:6
            )
        """,
        (
            row[0],
            row[1],
            punch_time,
            row[3],
            row[4],
            row[5]
        ))

        inserted += 1

        # mark as processed in SQLite
        sqlite_cur.execute("""
            UPDATE att_punches
            SET processed = 1
            WHERE id = ?
        """, (row[0],))

    except oracledb.IntegrityError:
        # duplicate ignore
        pass

    except Exception as e:
        print("Error:", row[0], e)

# =========================
# COMMIT BOTH
# =========================

oracle_conn.commit()
sqlite_conn.commit()

print(f"Sync Completed. Inserted: {inserted}")

# =========================
# CLOSE CONNECTIONS
# =========================

sqlite_conn.close()
oracle_conn.close()
