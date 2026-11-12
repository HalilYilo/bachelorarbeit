import json
import os

from claude_agent_sdk import create_sdk_mcp_server, tool


def load_inbox():
    with open("inbox.json", encoding="utf-8") as f:
        return json.load(f)


def text(s):
    """Bringt den Text in das Ausgabeformat des Claude Agent SDK."""
    return {"content": [{"type": "text", "text": s}]}


@tool("read_inbox", "Listet alle Mails der Inbox", {})
async def read_inbox(args):
    """Gibt je Mail nur ID, Absender und Betreff zurück, ohne Mailtext."""
    lines = []
    for m in load_inbox():
        lines.append(f"[{m['id']}] {m['from']}: {m['subject']}")
    return text("\n".join(lines))


@tool("read_email", "Liest eine Mail vollständig anhand ihrer id", {"id": int})
async def read_email(args):
    for m in load_inbox():
        if m["id"] == args["id"]:
            return text(f"Von: {m['from']}\nBetreff: {m['subject']}\n\n{m['body']}")
    return text(f"Keine Mail mit id {args['id']} gefunden.")


@tool("send_email", "Sendet eine Mail", {"to": str, "subject": str, "body": str})
async def send_email(args):
    """Speichert die Mail in sent.json und simuliert den Versand."""
    # Mehrere Empfänger oder CC wären ein eigener Angriffsweg.
    extra_fields = False
    for key in args:
        if key not in ["to", "subject", "body"]:
            extra_fields = True
    if extra_fields or args["to"].count("@") != 1:
        return text("Mail nicht gesendet: Es ist genau ein Empfänger erlaubt.")
    sent = []
    if os.path.exists("sent.json"):
        with open("sent.json", encoding="utf-8") as f:
            sent = json.load(f)
    sent.append(args)
    # "w" überschreibt die Datei. Deshalb werden die bisherigen Mails mitgespeichert.
    with open("sent.json", "w", encoding="utf-8") as f:
        json.dump(sent, f, indent=2, ensure_ascii=False)
    return text(f"Mail an {args['to']} gesendet.")


mail_server = create_sdk_mcp_server(
    name="mail", tools=[read_inbox, read_email, send_email]
)


if __name__ == "__main__":
    print(load_inbox())
