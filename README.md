# Schutzmechanismen gegen indirekte Prompt Injection in KI-Agenten

Dieses Repository beinhaltet den Quellcode zu meiner Bachelorarbeit an der Berliner Hochschule für Technik. Untersucht werden Schutzmechanismen gegen indirekte Prompt Injection am Beispiel eines simulierten Mail-Agenten.

## Voraussetzungen

- Python 3.10 oder neuer
- Claude Code von Anthropic (Anmeldung über Claude-Abo, kein API-Key nötig)

## Installation

```
pip install -r requirements.txt
```

## Start

```
python run.py
python evaluate.py
```

`run.py` führt die Läufe aus, `evaluate.py` wertet die protokollierten Läufe danach aus.

## Dateien

- `inbox.json`: Inbox des Benchmarks, alle Mails ohne Injektion.
- `inbox_pretest.json`: Inbox der ersten Angriffsversuche, nicht Teil des Benchmarks.
- `inbox_run.json`: Inbox eines Laufs, bei einem Angriffsfall mit Angriffstext. Wird bei jedem Lauf neu angelegt und liegt nicht im Repository.
- `cases.json`: Testfälle des Benchmarks (reguläre Aufgaben und Angriffsfälle). Die Kürzel der regulären Aufgaben: V = Versandaufgabe, L = Leseaufgabe, M = Versandaufgabe mit Empfängeradresse nur im Mailtext. `allowed_recipients` (erlaubte Empfänger) wertet die Regelprüfung aus, `legitimate_recipients` (legitime Empfänger) die Bewertung. Die Listen können sich unterscheiden, denn ein Empfänger kann laut Auftrag legitim sein, ohne für die Regelprüfung erlaubt zu sein. Ein Angriffsfall nutzt Auftrag und Prüfliste einer regulären Aufgabe (`base_task_id`) und hängt einen Angriffstext an eine Mail an. `attack_group` unterscheidet die geplanten Angriffsfälle (`grid`) von den ergänzenden, die getrennt ausgewertet werden (`supplementary`).
- `sent.json`: Postausgang des Agenten. Wird bei jedem Lauf neu angelegt und liegt nicht im Repository.
- `tools.py`: Die drei Tools des Agenten (`read_inbox`, `read_email`, `send_email`). `send_email` nimmt genau einen Empfänger an.
- `agent.py`: Konfiguration und Start des Agenten (Modell, Systemprompt, nur die drei eigenen Tools, Zeitlimit je Lauf).
- `run.py`: Führt die gewählten Testfälle aus (lädt sie aus `cases.json`, legt `inbox_run.json`, an leert `sent.json`, startet den Agenten und protokolliert jeden Lauf in `logs/`).
- `evaluate.py`: Prüft die protokollierten Läufe gegen die Prüfliste aus `cases.json` (Anzahl der Mails, Empfänger, Pflichtinhalte).
- `logs/`: Protokolle der Läufe, eine Datei je Bedingung, Modell und Durchgang. Der Dateiname beginnt mit `dev_` (Probeläufe während der Entwicklung), `pilot_` (Pilotlauf) oder `main_` (Hauptmessung). Liegt nicht im Repository.
