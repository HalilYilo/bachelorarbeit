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

from agent import run_agent


def load_case(case_id):
    with open("cases.json", encoding="utf-8") as f:
        cases = json.load(f)
    for case in cases:
        if case["case_id"] == case_id:
            return case
    raise ValueError(f"Unbekannte Fall-ID: {case_id}")


def reset_sent():
    """Legt sent.json leer an, damit jeder Lauf ohne alte Mails beginnt."""
    with open("sent.json", "w", encoding="utf-8") as f:
        json.dump([], f)


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


def read_status(entry):
    """Gibt Status und Abbruchgrund des Laufs zurück."""
    if entry["result_subtype"] == "success":
        return "ok", None
    if entry["result_subtype"] == "error_max_turns":
        return "aborted", "max_turns"
    # Ohne Modellantwort hat der Lauf nichts gemessen und zählt nicht.
    if entry["model"] is None:
        return "not_executable", None
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
    reset_sent()
    start = datetime.now()
    messages, error = asyncio.run(run_agent(case["task"]))
    entry = {
        "run_id": str(uuid4()),
        "condition": condition,
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "run_no": run_no,
        "attempt": attempt,
        "model": read_model(messages),
        "timestamp": start.isoformat(timespec="seconds"),
        "sent_mails": load_sent(),
        "tool_calls": collect_tool_calls(messages),
    }
    entry.update(read_result(messages))
    entry["status"], entry["abort_reason"] = read_status(entry)
    entry["error"] = error
    write_log(entry, path)
    return entry


if __name__ == "__main__":
    phase = "dev"
    conditions = ["baseline"]
    case_ids = ["V1", "V2", "V3", "V4", "L1", "L2", "L3", "L4", "M1", "M2"]

    # Eine unbekannte Bedingung würde sonst unbemerkt ohne Schutz laufen.
    for condition in conditions:
        if condition != "baseline":
            raise ValueError(f"Unbekannte Bedingung: {condition}")
    cases = []
    for case_id in case_ids:
        cases.append(load_case(case_id))

    for run_no in range(1, 4):
        for case in cases:
            for condition in conditions:
                path = f"logs/{phase}_{condition}_run{run_no}.jsonl"
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
