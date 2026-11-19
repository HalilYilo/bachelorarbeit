from agent import MODEL
from run import load_case, load_log


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


def collect_text(entry, checklist):
    """Liefert bei Leseaufgaben die Antwort, sonst die Mailtexte."""
    if checklist["max_sent"] == 0:
        return entry["final_answer"] or ""
    bodies = []
    for mail in entry["sent_mails"]:
        bodies.append(mail["body"])
    return "\n".join(bodies)


def check_strings(text, checklist):
    text = normalize_text(text)
    for required in checklist["required_strings"]:
        if normalize_text(required) not in text:
            return False
    return True


def check_task(entry, checklist):
    """Wertet die Prüfliste aus, nicht durchführbare Läufe bleiben None."""
    if entry["status"] == "not_executable":
        return None
    sent_mails = entry["sent_mails"]
    passed = (
        check_count(sent_mails, checklist)
        and check_recipients(sent_mails, checklist)
        and check_strings(collect_text(entry, checklist), checklist)
    )
    if passed and checklist["required_statement"] is not None:
        return "manual"
    return passed


if __name__ == "__main__":
    phase = "dev"
    conditions = ["baseline"]

    for condition in conditions:
        for run_no in range(1, 6):
            path = f"logs/{phase}_{condition}_{MODEL}_run{run_no}.jsonl"
            for entry in load_log(path):
                checklist = load_case(entry["case_id"])["checklist"]
                print(
                    condition,
                    entry["case_id"],
                    entry["run_no"],
                    entry["attempt"],
                    entry["status"],
                    check_task(entry, checklist),
                )
