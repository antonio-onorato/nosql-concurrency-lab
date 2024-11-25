# nosql-concurrency-lab


# Test di Concorrenza: MySQL vs MongoDB

Questa repository mostra come MySQL e MongoDB gestiscono transazioni concorrenti.

## Prerequisiti
- Python 3.7+
- MySQL e MongoDB installati e in esecuzione

## Installazione
1. Clona la repository:
   ```bash
   git clone https://github.com/tuo-nome/repository.git
   cd repository

*** WRITE CYCLES ***

MySQL:

	•	Utilizza lock per gestire i conflitti di scrittura tra le transazioni.
	•	Se una transazione (ad esempio T2) tenta di modificare una riga già aggiornata da un’altra transazione (T1), T2 deve attendere che T1 completi il suo commit o esegua un rollback.
	•	Questo approccio garantisce una forte consistenza, ma può causare ritardi, soprattutto in ambienti con alto carico di concorrenza.

MongoDB:

	•	Non utilizza un sistema di lock per gestire i conflitti.
	•	In caso di conflitti, come un write conflict, MongoDB restituisce immediatamente un errore (ad esempio WriteConflict) e forza la transazione fallita (T2) a riprovare automaticamente.
	•	Il numero massimo di retry può essere configurato in modo fisso, dando flessibilità nel bilanciare il numero di tentativi rispetto al tempo totale di esecuzione.

Principali differenze:

	•	MySQL si concentra sulla consistenza immediata, a costo di introdurre attese per la risoluzione dei lock.
	•	MongoDB, grazie alla sua ottimizzazione per l’alta disponibilità, adotta una strategia che evita blocchi, sacrificando temporaneamente l’immediatezza per riprovare e risolvere i conflitti in modo eventuale.