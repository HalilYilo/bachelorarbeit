import asyncio
import json
import os
from datetime import datetime
from uuid import uuid4

from claude_agent_sdk import AssistantMessage
from claude_agent_sdk import ResultMessage
from claude_agent_sdk import ToolResultBlock
from claude_agent_sdk import ToolUseBlock
from claude_agent_sdk import UserMessage

from agent import MODEL, run_agent


# Vorläufiger Wert in Sekunden, weit über jeder bisherigen Laufzeit.
TIME_LIMIT = 600


def load_case(case_id):
    """Lädt einen Fall, fehlende Angaben kommen aus der Basisaufgabe."""
    with open("cases.json", encoding="utf-8") as f:
        cases = json.load(f)
    for case in cases:
        if case["case_id"] == case_id:
            if "base_task_id" in case:
                base = load_case(case["base_task_id"])
                # Ein eigener Auftrag des Falls geht dem der Basis vor.
                if "task" not in case:
                    case["task"] = base["task"]
                if "allowed_recipients" not in case:
                    case["allowed_recipients"] = base["allowed_recipients"]
                case["checklist"] = base["checklist"]
            return case
    raise ValueError(f"Unbekannte Fall-ID: {case_id}")


def planned_runs(case):
    """Gibt zurück, wie oft ein Fall je Bedingung läuft."""
    # Die ergänzenden Fälle laufen fünfmal, weil es nur drei sind.
    if case.get("attack_group") == "supplementary":
        return 5
    return 3


def reset_sent():
    """Legt sent.json leer an, damit jeder Lauf ohne alte Mails beginnt."""
    with open("sent.json", "w", encoding="utf-8") as f:
        json.dump([], f)


def reset_inbox(case):
    """Schreibt inbox_run.json neu, bei einem Angriff mit Angriffstext."""
    with open("inbox.json", encoding="utf-8") as f:
        inbox = json.load(f)
    if case["case_type"] == "attack":
        found = False
        for mail in inbox:
            if mail["id"] == case["attack_mail_id"]:
                # Der Angriffstext steht am Mailende hinter dem Gruß.
                mail["body"] = mail["body"] + " " + case["injection"]
                found = True
        # Ohne Treffer liefe der Fall sonst unbemerkt ohne Angriffstext.
        if not found:
            raise ValueError(f"Keine Angriffsmail in {case['case_id']}")
    with open("inbox_run.json", "w", encoding="utf-8") as f:
        json.dump(inbox, f, indent=2, ensure_ascii=False)


def load_sent():
    with open("sent.json", encoding="utf-8") as f:
        return json.load(f)


def write_log(entry, path):
    """Hängt den Lauf als eine Zeile an, frühere Läufe bleiben erhalten."""
    os.makedirs("logs", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_log(path):
    """Liest alle Zeilen eines Protokolls, ohne Datei bleibt die Liste leer."""
    entries = []
    if not os.path.exists(path):
        return entries
    with open(path, encoding="utf-8") as f:
        for line in f:
            entries.append(json.loads(line))
    return entries


def collect_tool_calls(messages):
    """Ordnet jedem Tool-Aufruf sein Ergebnis über die ID des Aufrufs zu."""
    calls = []
    calls_by_id = {}
    for message in messages:
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    call = {
                        "call_no": len(calls) + 1,
                        "tool": block.name,
                        "args": block.input,
                        "result": None,
                        "is_error": None,
                    }
                    calls.append(call)
                    calls_by_id[block.id] = call
        if isinstance(message, UserMessage):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    call = calls_by_id[block.tool_use_id]
                    call["result"] = block.content
                    call["is_error"] = bool(block.is_error)
    return calls


def read_result(messages):
    """Liest die Werte der ResultMessage, ohne sie bleiben alle Werte None."""
    values = {
        "result_subtype": None,
        "is_error": None,
        "stop_reason": None,
        "num_turns": None,
        "final_answer": None,
        "tokens_in": None,
        "tokens_out": None,
        "usage": None,
        "duration_s": None,
        "cost_usd_estimate": None,
    }
    for message in messages:
        if isinstance(message, ResultMessage):
            values["result_subtype"] = message.subtype
            values["is_error"] = message.is_error
            values["stop_reason"] = message.stop_reason
            values["num_turns"] = message.num_turns
            values["final_answer"] = message.result
            values["duration_s"] = message.duration_ms / 1000
            values["cost_usd_estimate"] = message.total_cost_usd
            usage = message.usage
            if usage:
                values["tokens_in"] = (
                    usage["input_tokens"]
                    + usage["cache_creation_input_tokens"]
                    + usage["cache_read_input_tokens"]
                )
                values["tokens_out"] = usage["output_tokens"]
                values["usage"] = usage
    return values


def read_model(messages):
    """Liest den Modellnamen der ersten Antwort, ohne Antwort ist er None."""
    for message in messages:
        if isinstance(message, AssistantMessage):
            return message.model
    return None


def read_status(entry, error):
    """Gibt Status und Abbruchgrund des Laufs zurück."""
    if entry["result_subtype"] == "success":
        # Eine Verweigerung ist Verhalten des Modells und bleibt gewertet.
        if not entry["is_error"] or entry["stop_reason"] == "refusal":
            return "ok", None
    if entry["result_subtype"] == "error_max_turns":
        return "aborted", "max_turns"
    # Ohne Modellantwort hat der Lauf nichts gemessen und zählt nicht.
    if entry["model"] is None:
        return "not_executable", None
    # Das Zeitlimit ist nur der Grund, wenn kein Ergebnis mehr kam.
    if error == "timeout" and entry["result_subtype"] is None:
        return "aborted", "timeout"
    return "aborted", "error"


def choose_attempt(case_id, path):
    """Wählt den nächsten Versuch, ohne offenen Versuch ist es None."""
    attempts = 0
    for entry in load_log(path):
        if entry["case_id"] == case_id:
            # Ein Lauf mit Modellantwort zählt und wird nie ersetzt.
            if entry["status"] != "not_executable":
                return None
            attempts += 1
    if attempts >= 3:
        return None
    return attempts + 1


def run_attempt(case, path, condition, run_no, attempt):
    """Führt einen Lauf aus und schreibt seine Protokollzeile."""
    reset_inbox(case)
    reset_sent()
    start = datetime.now()
    messages, error = asyncio.run(run_agent(case["task"], TIME_LIMIT))
    entry = {
        "run_id": str(uuid4()),
        "condition": condition,
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "base_task_id": case.get("base_task_id"),
        "run_no": run_no,
        "attempt": attempt,
        "model": read_model(messages),
        "timestamp": start.isoformat(timespec="seconds"),
        "sent_mails": load_sent(),
        "tool_calls": collect_tool_calls(messages),
    }
    entry.update(read_result(messages))
    entry["status"], entry["abort_reason"] = read_status(entry, error)
    entry["error"] = error
    write_log(entry, path)
    return entry


if __name__ == "__main__":
    phase = "dev"
    conditions = ["baseline"]
    # Ohne Auswahl laufen alle Fälle aus cases.json.
    case_ids = []
    with open("cases.json", encoding="utf-8") as f:
        for case in json.load(f):
            case_ids.append(case["case_id"])

    # Eine unbekannte Bedingung würde sonst unbemerkt ohne Schutz laufen.
    for condition in conditions:
        if condition != "baseline":
            raise ValueError(f"Unbekannte Bedingung: {condition}")
    cases = []
    for case_id in case_ids:
        cases.append(load_case(case_id))

    for run_no in range(1, 6):
        for case in cases:
            # Ein Fall mit drei Durchgängen ist nach dem dritten fertig.
            if run_no > planned_runs(case):
                continue
            for condition in conditions:
                path = f"logs/{phase}_{condition}_{MODEL}_run{run_no}.jsonl"
                attempt = choose_attempt(case["case_id"], path)
                if attempt is None:
                    continue
                entry = run_attempt(case, path, condition, run_no, attempt)
                print(
                    entry["case_id"],
                    condition,
                    run_no,
                    attempt,
                    entry["status"],
                    entry["abort_reason"],
                )
                # Bei einer Störung würde sonst jeder weitere Lauf scheitern.
                if entry["status"] == "not_executable":
                    raise SystemExit("Kein Start möglich, später neu starten.")
