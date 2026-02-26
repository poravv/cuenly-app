from datetime import datetime

from app.modules.email_processor.imap_client import IMAPClient


class FakeIMAPConnection:
    def __init__(self, messages):
        self.messages = messages
        self.search_calls = []
        self.fetch_calls = []

    def uid(self, command, *args):
        cmd = str(command).upper()
        if cmd == "SEARCH":
            self.search_calls.append(args)
            ids = " ".join(sorted(self.messages.keys(), key=int)).encode("utf-8")
            return "OK", [ids]

        if cmd == "FETCH":
            uid_str = args[0]
            query = args[1]
            self.fetch_calls.append((uid_str, query))
            uids = [u for u in str(uid_str).split(",") if u]
            data = []

            for uid in uids:
                item = self.messages[uid]
                attachments = item.get("attachments", [])
                if "BODYSTRUCTURE" in str(query):
                    names = " ".join([f'"NAME" "{name}"' for name in attachments])
                    meta = f'{uid} (UID {uid} BODYSTRUCTURE ({names}))'.encode("utf-8")
                else:
                    meta = f"{uid} (UID {uid})".encode("utf-8")

                headers = (
                    f"Subject: {item.get('subject', '')}\r\n"
                    f"From: {item.get('sender', '')}\r\n"
                    f"Date: {item.get('date', 'Mon, 24 Feb 2026 10:00:00 -0300')}\r\n"
                    "\r\n"
                ).encode("utf-8")
                data.append((meta, headers))
            return "OK", data

        raise AssertionError(f"Comando IMAP no esperado: {command}")


def _new_client_with_fake_conn(messages):
    client = IMAPClient(
        host="imap.test.local",
        port=993,
        username="qa@tenant.test",
        password="secret",
    )
    client.conn = FakeIMAPConnection(messages)
    return client


def test_search_matches_subject_with_accents_and_synonyms():
    client = _new_client_with_fake_conn(
        {
            "101": {
                "subject": "Factura electrónica SET - marzo",
                "sender": "notificaciones@proveedor.com.py",
                "attachments": [],
            },
            "102": {
                "subject": "Resumen mensual",
                "sender": "facturacion@proveedor.com.py",
                "attachments": [],
            },
        }
    )

    results = client.search(
        ["factura electronica"],
        unread_only=True,
        search_synonyms={"factura electronica": ["facturación"]},
        fallback_sender_match=False,
        fallback_attachment_match=False,
    )

    assert [r["uid"] for r in results] == ["101"]
    assert results[0]["match_source"] == "subject"


def test_search_sender_fallback_is_optional():
    messages = {
        "201": {
            "subject": "Actualización de cuenta",
            "sender": "facturacion@proveedor.com.py",
            "attachments": [],
        }
    }

    client_no_fallback = _new_client_with_fake_conn(messages)
    results_without = client_no_fallback.search(
        ["factura electronica"],
        fallback_sender_match=False,
        fallback_attachment_match=False,
    )
    assert results_without == []

    client_with_fallback = _new_client_with_fake_conn(messages)
    results_with = client_with_fallback.search(
        ["factura electronica"],
        search_synonyms={"factura electronica": ["facturación"]},
        fallback_sender_match=True,
        fallback_attachment_match=False,
    )
    assert [r["uid"] for r in results_with] == ["201"]
    assert results_with[0]["match_source"] == "sender"


def test_search_attachment_fallback_is_optional_and_uses_bodystructure():
    messages = {
        "301": {
            "subject": "Resumen de movimientos",
            "sender": "notificaciones@proveedor.com.py",
            "attachments": ["comprobante_febrero.xml"],
        }
    }

    client_no_fallback = _new_client_with_fake_conn(messages)
    results_without = client_no_fallback.search(
        ["comprobante"],
        fallback_sender_match=False,
        fallback_attachment_match=False,
    )
    assert results_without == []
    assert client_no_fallback.conn.fetch_calls
    assert "BODYSTRUCTURE" not in str(client_no_fallback.conn.fetch_calls[0][1])

    client_with_fallback = _new_client_with_fake_conn(messages)
    results_with = client_with_fallback.search(
        ["comprobante"],
        fallback_sender_match=False,
        fallback_attachment_match=True,
    )
    assert [r["uid"] for r in results_with] == ["301"]
    assert results_with[0]["match_source"] == "attachment"
    assert client_with_fallback.conn.fetch_calls
    assert "BODYSTRUCTURE" in str(client_with_fallback.conn.fetch_calls[0][1])


def test_search_includes_since_and_before_flags():
    client = _new_client_with_fake_conn(
        {
            "401": {
                "subject": "Factura electrónica",
                "sender": "mail@proveedor.com.py",
                "attachments": [],
            }
        }
    )

    client.search(
        ["factura electronica"],
        unread_only=True,
        since_date=datetime(2026, 2, 1),
        before_date=datetime(2026, 2, 20),
    )

    assert client.conn.search_calls
    args = tuple(str(x) for x in client.conn.search_calls[0])
    assert "UNSEEN" in args
    assert "SINCE" in args
    assert "01-Feb-2026" in args
    assert "BEFORE" in args
    assert "20-Feb-2026" in args
