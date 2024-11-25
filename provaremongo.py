import time
import csv
from pymongo.errors import OperationFailure

# Funzione per scrivere i risultati nel file CSV
def write_to_report(result):
    with open('reportMongoDB.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(result)

def test_mongodb_write_cycles(setup_mongodb):
    with mongodb_connection() as db:
        collection = db.test
        session = db.client.start_session()
    
        retry_attempts = 3
        retry_delay = 1  # Tempo di attesa tra i retry
    
        # Transazione T1
        session.start_transaction()
        write_to_report(["MongoDB", "T1 BEGIN"])
        collection.update_one({"_id": 1}, {"$set": {"value": 11}}, session=session)
        write_to_report(["MongoDB", "T1 UPDATE id=1 value=11"])
        collection.update_one({"_id": 2}, {"$set": {"value": 21}}, session=session)
        write_to_report(["MongoDB", "T1 UPDATE id=2 value=21"])
    
        # Transazione T2
        session2 = db.client.start_session()
        session2.start_transaction()
        write_to_report(["MongoDB", "T2 BEGIN"])
    
        # Gestione del conflitto per l'aggiornamento su _id=1
        try:
            collection.update_one({"_id": 1}, {"$set": {"value": 12}}, session=session2)  # Conflitto con T1
            write_to_report(["MongoDB", "T2 UPDATE id=1 value=12"])
        except OperationFailure as e:
            if 'TransientTransactionError' in str(e):  # Se c'è un conflitto temporaneo
                write_to_report(["MongoDB", "T2 RETRY UPDATE id=1 value=12"])
                for attempt in range(retry_attempts):
                    try:
                        collection.update_one({"_id": 1}, {"$set": {"value": 12}}, session=session2)
                        write_to_report(["MongoDB", "T2 UPDATE id=1 value=12"])
                        break
                    except OperationFailure:
                        if attempt == retry_attempts - 1:
                            write_to_report(["MongoDB", "T2 UPDATE failed after retries"])
                        time.sleep(retry_delay)
    
        # Commit di T1
        try:
            session.commit_transaction()
            write_to_report(["MongoDB", "T1 COMMIT"])
        except OperationFailure as e:
            write_to_report(["MongoDB", f"T1 COMMIT failed: {str(e)}"])
    
        # Transazione T2 continua
        for attempt in range(retry_attempts):
            try:
                collection.update_one({"_id": 2}, {"$set": {"value": 22}}, session=session2)
                write_to_report(["MongoDB", "T2 UPDATE id=2 value=22"])
                break
            except OperationFailure as e:
                if 'TransientTransactionError' in str(e):
                    write_to_report(["MongoDB", f"T2 RETRY UPDATE id=2 value=22 attempt {attempt + 1}"])
                    time.sleep(retry_delay)
                else:
                    raise e
    
        try:
            session2.commit_transaction()
            write_to_report(["MongoDB", "T2 COMMIT"])
        except OperationFailure as e:
            write_to_report(["MongoDB", f"T2 COMMIT failed: {str(e)}"])

# Chiamata alla funzione di test
test_mongodb_write_cycles(None)
