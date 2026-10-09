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
# LOAD EMPLOYEE CACHE (SQLite)
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
# LOAD TERMINAL CACHE (SQLite)
# =========================
def load_terminal_cache(sqlite_cur):
    sqlite_cur.execute("""
        SELECT id, terminal_name, terminal_tcpip, terminal_port, terminal_sns
        FROM att_terminal
    """)

    return {
        row[0]: (row[1], row[2], row[3], row[4])
        for row in sqlite_cur.fetchall()
    }

# =========================
# ORACLE CONNECTION
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

        oracle_conn = get_oracle_conn()
        oracle_cur = oracle_conn.cursor()

        # =========================
        # LOAD CACHE
        # =========================
        emp_map = load_employee_cache(sqlite_cur)
        terminal_map = load_terminal_cache(sqlite_cur)

        # =========================
        # FETCH ATTENDANCE DATA
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

        print(f"Found {len(rows)} records")

        inserted = 0

        # =========================
        # PROCESS ROWS
        # =========================
        for row in rows:

            try:
                emp = emp_map.get(row[1])
                terminal = terminal_map.get(row[3])

                if not emp:
                    print("Employee not found:", row[1])
                    continue

                if not terminal:
                    print("Terminal not found:", row[3])
                    continue

                emp_pin, emp_firstname = emp
                terminal_name, terminal_tcpip, terminal_port, terminal_sns = terminal

                # =========================
                # SAFE DATETIME
                # =========================
                try:
                    punch_time = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")
                except:
                    punch_time = datetime.now()

                # =========================
                # ORACLE MERGE
                # =========================
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
                            :7 TERMINAL_NAME,
                            :8 TERMINAL_TCPIP,
                            :9 TERMINAL_PORT,
                            :10 TERMINAL_SNS,
                            :11 PUNCH_TYPE,
                            :12 ATTENDANCE_EVENT
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
                            TERMINAL_NAME,
                            TERMINAL_TCPIP,
                            TERMINAL_PORT,
                            TERMINAL_SNS,
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
                            s.TERMINAL_NAME,
                            s.TERMINAL_TCPIP,
                            s.TERMINAL_PORT,
                            s.TERMINAL_SNS,
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
                    terminal_name,
                    terminal_tcpip,
                    terminal_port,
                    terminal_sns,
                    row[4],
                    row[5]
                ))

                # =========================
                # MARK PROCESSED
                # =========================
                sqlite_cur.execute("""
                    UPDATE att_punches
                    SET processed = 1
                    WHERE id = ?
                """, (row[0],))

                inserted += 1

            except Exception as e:
                print("Row Error:", row[0], e)

        # =========================
        # COMMIT
        # =========================
        oracle_conn.commit()
        sqlite_conn.commit()

        oracle_conn.close()
        sqlite_conn.close()

        print("Sync Completed. Inserted:", inserted)

    except Exception as e:
        print("SYNC ERROR:", e)

# =========================
# MAIN LOOP
# =========================
while True:
    sync_data()

    print("Waiting 10 seconds...")
    time.sleep(10)
