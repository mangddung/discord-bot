import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv('DB_NAME')

def get_connection():
    conn = sqlite3.connect(f"{DB_NAME}.db")
    return conn

def initialize_database(table):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.executescript(table)  # ✅ 여러 SQL 문 실행 가능하도록 변경
        conn.commit()
    except Exception as e:
        print(f"DB 초기화 중 오류 발생: {e}")
    finally:
        conn.close()
    # cursor.execute('''
    # CREATE TABLE IF NOT EXISTS channel_access (
    #     id INTEGER PRIMARY KEY AUTOINCREMENT,
    #     server_id INTEGER NOT NULL,
    #     access_channel_id INTEGER NOT NULL,
    #     access_message_id INTEGER NOT NULL,
    #     target_channel_id INTEGER NOT NULL,
    #     target_channel_name TEXT NOT NULL
    # )
    # ''')

    # cursor.execute('''
    # CREATE TABLE IF NOT EXISTS guest_invite_code (
    #     id INTEGER PRIMARY KEY AUTOINCREMENT,
    #     server_id INTEGER NOT NULL,
    #     invite_code TEXT NOT NULL,
    #     inviter_id INTEGER NOT NULL,
    #     inviter_name TEXT NOT NULL,
    #     target_channel_id INTEGER NOT NULL,
    #     target_user_id INTEGER,
    #     created_at TIMESTAMP,
    #     joined_at TIMESTAMP
    # )
    # ''')

if __name__ == "__main__":
    initialize_database()
