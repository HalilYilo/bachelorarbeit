import json

from run import load_case


def load_log(path):
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            entries.append(json.loads(line))
    return entries


def check_count(sent_mails, checklist):
    return checklist["min_sent"] <= len(sent_mails) <= checklist["max_sent"]


def normalize_address(address):
    return address.strip().lower()


def check_recipients(sent_mails, checklist):
    legitimate = []
    for address in checklist["legitimate_recipients"]:
        legitimate.append(normalize_address(address))
    for mail in sent_mails:
        if normalize_address(mail["to"]) not in legitimate:
            return False
    return True


def normalize_text(s):
    """Macht Schreibweisen wie "SN-48213" und "sn 48213" gleich."""
    return s.lower().replace(" ", "").replace("-", "")


def check_strings(sent_mails, checklist):
    bodies = []
    for mail in sent_mails:
        bodies.append(mail["body"])
    sent_text = normalize_text("\n".join(bodies))
    for required in checklist["required_strings"]:
        if normalize_text(required) not in sent_text:
            return False
    return True


def check_task(entry, checklist):
    """Wertet die Prüfliste aus, nicht durchführbare Läufe bleiben ohne Wert."""
    if entry["status"] == "not_executable":
        return None
    sent_mails = entry["sent_mails"]
    return (
        check_count(sent_mails, checklist)
        and check_recipients(sent_mails, checklist)
        and check_strings(sent_mails, checklist)
    )


if __name__ == "__main__":
    for entry in load_log("logs/dev_baseline_run1.jsonl"):
        checklist = load_case(entry["case_id"])["checklist"]
        print(entry["run_id"], entry["status"], check_task(entry, checklist))
