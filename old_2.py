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
# LOAD EMPLOYEE CACHE (FROM SQLITE)
# =========================
def load_employee_cache(sqlite_cur):
    sqlite_cur.execute("""
        SELECT id, emp_pin, emp_firstname
        FROM hr_employee
    """)

    return {
        row[0]: (row[1], row[2])
        for row in sqlite_cur.fetchall()
    }

# =========================
# ORACLE CONNECT
# =========================
def get_oracle_conn():
    return oracledb.connect(**ORACLE_CONFIG)

# =========================
# SYNC FUNCTION
# =========================
def sync_data():

    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        sqlite_cur = sqlite_conn.cursor()

        # 🔥 refresh employee map every sync (IMPORTANT FIX)
        emp_map = load_employee_cache(sqlite_cur)

        oracle_conn = get_oracle_conn()
        oracle_cur = oracle_conn.cursor()

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

        print(f"Found {len(rows)} records")

        inserted = 0

        for row in rows:

            try:
                emp = emp_map.get(row[1])

                if not emp:
                    print("Employee not found:", row[1])
                    continue

                emp_pin = emp[0]
                emp_firstname = emp[1]

                # safe datetime parsing
                try:
                    punch_time = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")
                except:
                    punch_time = datetime.now()

                oracle_cur.execute("""
                    MERGE INTO ATTENDANCE_LOG t
                    USING (
                        SELECT
                            :1 ID,
                            :2 EMPLOYEE_ID,
                            :3 EMP_PIN,
                            :4 EMP_FIRSTNAME,
                            :5 PUNCH_TIME,
                            :6 TERMINAL_ID,
                            :7 PUNCH_TYPE,
                            :8 ATTENDANCE_EVENT
                        FROM dual
                    ) s
                    ON (t.ID = s.ID)

                    WHEN NOT MATCHED THEN
                        INSERT (
                            ID,
                            EMPLOYEE_ID,
                            EMP_PIN,
                            EMP_FIRSTNAME,
                            PUNCH_TIME,
                            TERMINAL_ID,
                            PUNCH_TYPE,
                            ATTENDANCE_EVENT
                        )
                        VALUES (
                            s.ID,
                            s.EMPLOYEE_ID,
                            s.EMP_PIN,
                            s.EMP_FIRSTNAME,
                            s.PUNCH_TIME,
                            s.TERMINAL_ID,
                            s.PUNCH_TYPE,
                            s.ATTENDANCE_EVENT
                        )
                """, (
                    row[0],
                    row[1],
                    emp_pin,
                    emp_firstname,
                    punch_time,
                    row[3],
                    row[4],
                    row[5]
                ))

                sqlite_cur.execute("""
                    UPDATE att_punches
                    SET processed = 1
                    WHERE id = ?
                """, (row[0],))

                inserted += 1

            except Exception as e:
                print("Row Error:", row[0], e)

        # =========================
        # COMMIT SAFELY
        # =========================
        oracle_conn.commit()
        sqlite_conn.commit()

        oracle_conn.close()
        sqlite_conn.close()

        print("Sync Completed. Inserted:", inserted)

    except Exception as e:
        print("SYNC ERROR:", e)

# =========================
# MAIN LOOP (SAFE VERSION)
# =========================
while True:
    sync_data()

    print("Waiting 10 seconds...")
    time.sleep(10)
