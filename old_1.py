import sqlite3
import oracledb
from datetime import datetime
import time

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
# SYNC FUNCTION
# =========================

def sync_data():

    try:
        # SQLite connect
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        sqlite_cur = sqlite_conn.cursor()

        # Oracle connect
        oracle_conn = oracledb.connect(**ORACLE_CONFIG)
        oracle_cur = oracle_conn.cursor()

        # Fetch only unprocessed data
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

        inserted = 0

        for row in rows:

            try:
                # safe datetime convert
                punch_time = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")

                # =========================
                # SAFE UPSERT (NO DUPLICATE ERROR)
                # =========================
                oracle_cur.execute("""
                    MERGE INTO ATTENDANCE_LOG t
                    USING (
                        SELECT
                            :1 ID,
                            :2 EMPLOYEE_ID,
                            :3 PUNCH_TIME,
                            :4 TERMINAL_ID,
                            :5 PUNCH_TYPE,
                            :6 ATTENDANCE_EVENT
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

                # mark as processed in SQLite
                sqlite_cur.execute("""
                    UPDATE att_punches
                    SET processed = 1
                    WHERE id = ?
                """, (row[0],))

            except Exception as e:
                print("Row Error:", row[0], e)

        # commit both DB
        oracle_conn.commit()
        sqlite_conn.commit()

        print(f"Sync Completed. Inserted: {inserted}")

        # close connections
        sqlite_conn.close()
        oracle_conn.close()

    except Exception as e:
        print("SYNC ERROR:", e)


# =========================
# RUN EVERY 6 HOURS
# =========================

while True:
    sync_data()

    print("Waiting 10 seconds for next sync...")

    time.sleep(10)
