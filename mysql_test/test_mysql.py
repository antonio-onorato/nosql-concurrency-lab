import os
import pytest
import mysql.connector
import time
import csv
from contextlib import contextmanager

def clear_report_file():
    """Funzione per eliminare il file reportMySQL.csv se esiste"""
    file_path = 'report/reportMySQL.csv'
    if os.path.exists(file_path):
        os.remove(file_path)

@contextmanager
def mysql_connection():
    """Connessione al database MySQL"""
    conn = mysql.connector.connect(
        host="mysql-test",
        user="root",
        password="onoratotestdb",
        database="test_db"
    )
    try:
        yield conn
    finally:
        conn.close()

def write_to_csv(results):
    with open('report/reportMySQL.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(results)

@pytest.fixture(scope="module")
def setup_mysql():
    with mysql_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS test_db")
        cursor.execute("USE test_db")
        cursor.execute("CREATE TABLE IF NOT EXISTS test (id INT PRIMARY KEY, value INT)")
        cursor.execute("DELETE FROM test")
        cursor.execute("INSERT INTO test (id, value) VALUES (1, 10), (2, 20)")
        conn.commit()
    yield
    # Cleanup after tests
    with mysql_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DROP DATABASE IF EXISTS test_db")
        conn.commit()

def test_mysql_write_cycles(setup_mysql):
    with mysql_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        
        # Iniziamo la transazione T1
        write_to_csv(["MySQL", "T1 BEGIN"])
        cursor.execute("BEGIN;")
        cursor.execute("UPDATE test SET value = 11 WHERE id = 1;")  # T1 aggiorna id=1 a 11
        write_to_csv(["MySQL", "T1 UPDATE id=1 value=11"])
        cursor.execute("UPDATE test SET value = 21 WHERE id = 2;")  # T1 aggiorna id=2 a 21
        write_to_csv(["MySQL", "T1 UPDATE id=2 value=21"])

        # Seconda transazione T2 che deve tentare di aggiornare id=1 prima
        write_to_csv(["MySQL", "T2 BEGIN"])
        cursor.execute("BEGIN;")
        start_deadlock_time = time.time()  # Inizia a misurare il tempo in cui T2 è bloccato
        cursor.execute("UPDATE test SET value = 12 WHERE id = 1;")  # T2 aggiorna id=1 a 12 (prima)
        write_to_csv(["MySQL", "T2 UPDATE id=1 value=12"])
        cursor.execute("UPDATE test SET value = 22 WHERE id = 2;")  # T2 aggiorna id=2 a 22
        write_to_csv(["MySQL", "T2 UPDATE id=2 value=22"])

        # Commit di T1, che sblocca T2
        cursor.execute("COMMIT;")
        write_to_csv(["MySQL", "T1 COMMIT"])

        # Tempo di deadlock
        deadlock_duration = time.time() - start_deadlock_time
        write_to_csv(["MySQL", f"T2 was deadlocked for {deadlock_duration:.2f} seconds"])

        # Commit di T2
        cursor.execute("COMMIT;")
        write_to_csv(["MySQL", "T2 COMMIT"])

        # Verifica il risultato della tabella
        cursor.execute("SELECT * FROM test")
        result = cursor.fetchall()

        # Scrivi il risultato nel CSV
        write_to_csv(["MySQL", "Final Result", str(result)])

    # Controlla che il risultato sia quello previsto: id=1 => 12, id=2 => 22
    assert result == [(1, 12), (2, 22)], f"Expected [(1, 12), (2, 22)], but got {result}"