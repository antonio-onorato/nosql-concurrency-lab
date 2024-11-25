import os
import pytest
import pymongo
import time
import csv
from pymongo.errors import OperationFailure
from contextlib import contextmanager

def clear_report_file():
    """Funzione per eliminare il file reportMongoDB.csv se esiste"""
    file_path = 'report/reportMongoDB.csv'
    if os.path.exists(file_path):
        os.remove(file_path)

@contextmanager
def mongodb_connection():
    """Connessione al database MongoDB in modalità replicaset (unica modalità supportata per le transazioni)"""
    client = pymongo.MongoClient("mongodb://root:onoratotestdb@localhost:27017?directConnection=true&replicaSet=rs0")
    db = client.test_db
    yield db
    client.close()

def write_to_csv(results):
    """Funzione per scrivere nel file CSV dove annoterò il debug di ogni operazione di ogni transazione"""
    with open('report/reportMongoDB.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(results)

@pytest.fixture(scope="module")
def setup_mongodb():
    """Funzione che mi permette ad ogni avvio del test di eliminare i dati precedenti dalla collection e inserire i dati di set iniziali."""
    
    # Pulisce il reportCSV all'inizio dell'esecuzione del test
    clear_report_file() 
    
    with mongodb_connection() as db:
        collection = db.test
        collection.delete_many({})
        collection.insert_many([
            {"_id": 1, "value": 10},
            {"_id": 2, "value": 20}
        ])
    yield
    with mongodb_connection() as db:
        db.test.delete_many({})

def retry_update(collection, filter_query, update_query, session, max_attempts, delay):
    """Funzione per gestire i retry in caso di errore"""
    for attempt in range(max_attempts):
        try:
            collection.update_one(filter_query, update_query, session=session)
            write_to_csv(["MongoDB", f"RETRY UPDATE SUCCESS (attempt {attempt + 1})"])
            return
        except OperationFailure as e:
            write_to_csv(["MongoDB", f"RETRY UPDATE FAILED (attempt {attempt + 1})", str(e)])
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay)

def test_mongodb_write_cycles(setup_mongodb):
    """Funzione che effettua il test per quanto riguarda il caso 'write cycles' """
    with mongodb_connection() as db:
        collection = db.test
        session = db.client.start_session()
        session2 = db.client.start_session()

        retry_attempts = 3
        retry_delay = 1

        try:
            # Transazione T1
            try:
                session.start_transaction()
                write_to_csv(["MongoDB", "T1 BEGIN"])

                collection.update_one({"_id": 1}, {"$set": {"value": 11}}, session=session)
                write_to_csv(["MongoDB", "T1 UPDATE id=1 value=11"])

                collection.update_one({"_id": 2}, {"$set": {"value": 21}}, session=session)
                write_to_csv(["MongoDB", "T1 UPDATE id=2 value=21"])
            except Exception as e:
                error_message = (
                    "Errore durante la transazione T1. "
                    "La transazione è stata annullata per garantire consistenza. "
                    f"Dettaglio errore: {str(e)}"
                )
                write_to_csv(["MongoDB", "T1 FAILED", error_message])
                session.abort_transaction()
                raise

            # Transazione T2 (inizio durante T1)
            try:
                session2.start_transaction()
                write_to_csv(["MongoDB", "T2 BEGIN"])

                # Questo update è destinato a fallire a causa del conflitto su _id=1
                collection.update_one({"_id": 1}, {"$set": {"value": 12}}, session=session2)
                write_to_csv(["MongoDB", "T2 UPDATE id=1 value=12"])
            except OperationFailure as e:
                error_message = (
                    "Conflitto durante l'aggiornamento nella transazione T2. "
                    "La transazione è stata annullata per evitare inconsistenze. "
                    f"Errore MongoDB: {str(e)}"
                )
                write_to_csv(["MongoDB", "T2 UPDATE id=1 FAILED", error_message])
                session2.abort_transaction()  # Abort dopo il fallimento atteso

            # Commit di T1 dopo il conflitto con T2
            try:
                session.commit_transaction()
                write_to_csv(["MongoDB", "T1 COMMIT"])
            except Exception as e:
                error_message = (
                    "Errore durante il commit della transazione T1. "
                    "La transazione è stata annullata. "
                    f"Dettaglio errore: {str(e)}"
                )
                write_to_csv(["MongoDB", "T1 COMMIT FAILED", error_message])
                session.abort_transaction()
                raise

            # Continuazione di T2
            try:
                collection.update_one({"_id": 2}, {"$set": {"value": 22}}, session=session2)
                write_to_csv(["MongoDB", "T2 UPDATE id=2 value=22"])

                session2.commit_transaction()
                write_to_csv(["MongoDB", "T2 COMMIT"])
            except Exception as e:
                error_message = (
                    "Errore durante la continuazione della transazione T2. "
                    "La transazione è stata annullata. "
                    f"Dettaglio errore: {str(e)}"
                )
                write_to_csv(["MongoDB", "T2 FAILED", error_message])
                session2.abort_transaction()
                raise

        finally:
            session.end_session()
            session2.end_session()

            # Scrittura del risultato finale indipendentemente dagli errori
            try:
                result = list(collection.find())
                expected_result = [{"_id": 1, "value": 12}, {"_id": 2, "value": 22}]
                
                if result == expected_result:
                    write_to_csv(["MongoDB", "Write Cycles", str(result), "RISULTATO CORRETTO"])
                else:
                    write_to_csv([
                        "MongoDB", 
                        "Write Cycles", 
                        str(result), 
                        f"RISULTATO NON CORRETTO, ATTESO: {str(expected_result)}"
                    ])
            except Exception as e:
                error_message = (
                    "Errore durante la query finale. "
                    f"Dettaglio errore: {str(e)}"
                )
                write_to_csv(["MongoDB", "Final Query FAILED", error_message])


