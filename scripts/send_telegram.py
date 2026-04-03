#!/usr/bin/env python3
import argparse
import json
import mimetypes
import uuid
from pathlib import Path
from urllib import error, parse, request


def post_multipart(url: str, fields: dict, file_field: str = "", file_path: Path = None):
    boundary = f"----DomainFinder{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    if file_field and file_path:
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = file_path.read_bytes()
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8")
        )
        body.extend(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
        body.extend(data)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        return payload


def send_text(bot_token: str, chat_id: str, text: str):
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = request.Request(endpoint, data=payload, method="POST")
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def send_document(bot_token: str, chat_id: str, file_path: Path, caption: str = ""):
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption
    return post_multipart(endpoint, fields, file_field="document", file_path=file_path)


def main():
    parser = argparse.ArgumentParser(description="Send a Telegram summary and optional document.")
    parser.add_argument("--bot-token", required=True)
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--summary-file", default="results/summary.md")
    parser.add_argument("--document-file", default="results/available_domains.txt")
    args = parser.parse_args()

    summary_path = Path(args.summary_file)
    document_path = Path(args.document_file)
    summary_text = summary_path.read_text(encoding="utf-8") if summary_path.exists() else "Run finished."

    text = summary_text[:4000]
    send_text(args.bot_token, args.chat_id, text)

    if document_path.exists() and document_path.stat().st_size > 0:
        send_document(args.bot_token, args.chat_id, document_path, caption="available_domains.txt")


if __name__ == "__main__":
    try:
        main()
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Telegram API error {exc.code}: {body}")
