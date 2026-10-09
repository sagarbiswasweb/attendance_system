import sqlite3
import oracledb
from datetime import datetime

sqlite_conn = sqlite3.connect(
    r"C:\Program Files (x86)\ZKBio Time.Net\TimeNet.db"
)
sqlite_cur = sqlite_conn.cursor()

oracle_conn = oracledb.connect(
    user="NBNI_ERP",
    password="NBNI_ERP",
    host="192.168.3.8",
    port=1521,
    service_name="orcl19c"
)
oracle_cur = oracle_conn.cursor()

rows = sqlite_cur.execute("""
SELECT id, employee_id, punch_time,
       terminal_id, punch_type, attendance_event
FROM att_punches
""").fetchall()

inserted = 0
skipped = 0

for row in rows:

    try:
        punch_time = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")

        oracle_cur.execute("""
            MERGE INTO ATTENDANCE_LOG t
            USING (
                SELECT
                    :1 AS ID,
                    :2 AS EMPLOYEE_ID,
                    :3 AS PUNCH_TIME,
                    :4 AS TERMINAL_ID,
                    :5 AS PUNCH_TYPE,
                    :6 AS ATTENDANCE_EVENT
                FROM dual
            ) s
            ON (t.ID = s.ID)

            WHEN NOT MATCHED THEN
                INSERT (
                    ID,
                    EMPLOYEE_ID,
                    PUNCH_TIME,
                    TERMINAL_ID,
                    PUNCH_TYPE,
                    ATTENDANCE_EVENT
                )
                VALUES (
                    s.ID,
                    s.EMPLOYEE_ID,
                    s.PUNCH_TIME,
                    s.TERMINAL_ID,
                    s.PUNCH_TYPE,
                    s.ATTENDANCE_EVENT
                )
        """, (
            row[0],
            row[1],
            punch_time,
            row[3],
            row[4],
            row[5]
        ))

        inserted += 1

    except Exception as e:
        print("Error ID:", row[0], e)
        skipped += 1

oracle_conn.commit()

print("DONE")
print("Inserted:", inserted)
print("Skipped:", skipped)

sqlite_conn.close()
oracle_conn.close()
