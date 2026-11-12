import asyncio
import json
import os
from datetime import datetime

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
    """Liest den Modellnamen aus der ersten Antwort, ohne Antwort bleibt er None."""
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


if __name__ == "__main__":
    case = load_case("V1")
    reset_sent()
    start = datetime.now()
    messages, error = asyncio.run(run_agent(case["task"]))
    entry = {
        "run_id": start.strftime("%Y%m%d-%H%M%S"),
        "condition": "baseline",
        "case_id": case["case_id"],
        "case_type": case["case_type"],
        "run_no": 1,
        "attempt": 1,
        "model": read_model(messages),
        "timestamp": start.isoformat(timespec="seconds"),
        "sent_mails": load_sent(),
        "tool_calls": collect_tool_calls(messages),
    }
    entry.update(read_result(messages))
    entry["status"], entry["abort_reason"] = read_status(entry)
    entry["error"] = error
    write_log(entry, "logs/dev_baseline_run1.jsonl")
    print(entry["case_id"], entry["status"], entry["abort_reason"], entry["num_turns"])
