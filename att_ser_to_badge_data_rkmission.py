import sqlite3
import os

os.environ["PATH"] = r"D:\oracle\db_home19c\bin;" + os.environ["PATH"]

import oracledb
from datetime import datetime
import time

oracledb.init_oracle_client(
    lib_dir=r"D:\oracle\db_home19c\bin"
)

# =========================
# CONFIG
# =========================

SQLITE_DB = r"C:\Program Files (x86)\ZKBio Time.Net\TimeNet.db"

ORACLE_CONFIG = {
    "user": "ACCESS_CONTROL",
    "password": "ADMIN1",
    "host": "118.67.219.110",
    "port": 1521,
    "service_name": "orclmission"
}

# =========================
# ORACLE CONNECTION
# =========================
def get_oracle_conn():
    return oracledb.connect(
        user=ORACLE_CONFIG["user"],
        password=ORACLE_CONFIG["password"],
        host=ORACLE_CONFIG["host"],
        port=ORACLE_CONFIG["port"],
        service_name=ORACLE_CONFIG["service_name"]
    )
# =========================
# LOAD EMPLOYEE CACHE
# =========================
def load_employee_cache(sqlite_cur):
    sqlite_cur.execute("""
        SELECT id, emp_pin, emp_firstname 
        FROM hr_employee
    """)
    return {
        row[0]: (row[1], row[2]) for row in sqlite_cur.fetchall()
    }

# =========================
# LOAD TERMINAL CACHE
# =========================
def load_terminal_cache(sqlite_cur):
    sqlite_cur.execute("""
        SELECT id, terminal_name, terminal_tcpip, terminal_port, terminal_sns 
        FROM att_terminal
    """)
    return {
        row[0]: (row[1], row[2], row[3], row[4]) for row in sqlite_cur.fetchall()
    }

# =========================
# SYNC FUNCTION
# =========================
def sync_data():
    sqlite_conn = None
    oracle_conn = None

    try:
        # SQLITE CONNECT
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        sqlite_cur = sqlite_conn.cursor()

        # ORACLE CONNECT
        try:
            oracle_conn = get_oracle_conn()
            oracle_cur = oracle_conn.cursor()
        except Exception as e:
            print("ORACLE CONNECTION FAILED:", e)
            return

        # CACHE LOAD
        emp_map = load_employee_cache(sqlite_cur)
        terminal_map = load_terminal_cache(sqlite_cur)

        # FETCH DATA
        rows = sqlite_cur.execute("""
            SELECT id, employee_id, punch_time, terminal_id, punch_type, attendance_event
            FROM att_punches
            WHERE processed = 0 OR processed IS NULL
        """).fetchall()

        print(f"[{datetime.now()}] Found {len(rows)} records")

        inserted = 0

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

                # PARSE DATETIME SAFELY
                try:
                    punch_time = datetime.strptime(row[2], "%Y-%m-%d %H:%M:%S")
                except:
                    punch_time = datetime.now()

                # INSERT ORACLE
                oracle_cur.execute("""
                    INSERT INTO BADGE_DATA (
                        DATA_PROCESSED,
                        PUNCH_DATE_TIME,
                        CARD_NO,
                        TERMINAL,
                        READER,
                        DOOR_STATE,
                        ERROR_CODE,
                        CARD_LEVEL,
                        BLOCK,
                        CARD_TYPE,
                        REASON,
                        IP_ADDRESS
                    )
                    VALUES (
                        :1, :2, :3, :4, :5, :6,
                        :7, :8, :9, :10, :11, :12
                    )
                """, (
                    'N',
                    punch_time,
                    str(emp_pin),
                    str(row[3])[:2],
                    '0',
                    '0',
                    0,
                    0,
                    0,
                    0,
                    str(row[5]) if row[5] else None,
                    terminal_tcpip
                ))

                # MARK PROCESSED
                sqlite_cur.execute("""
                    UPDATE att_punches
                    SET processed = 1
                    WHERE id = ?
                """, (row[0],))

                inserted += 1

            except Exception as e:
                print("Row Error ID", row[0], e)

        oracle_conn.commit()
        sqlite_conn.commit()

        print("Sync Completed. Inserted:", inserted)

    except Exception as e:
        print("SYNC ERROR:", e)

    finally:
        if oracle_conn:
            oracle_conn.close()
        if sqlite_conn:
            sqlite_conn.close()


# =========================
# MAIN LOOP
# =========================
while True:
    sync_data()
    print("Waiting 10 seconds...\n")
    time.sleep(10)
