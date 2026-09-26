#!/usr/bin/env python3
"""FAQ bot — a Telegram bot that answers from a knowledge-base file and relays the rest to the owner.

Uses the official Telegram Bot API over long polling (no webhook, no public URL).
Known questions are answered from the KB (faq-knowledge-base JSON format) with
deterministic token matching — zero AI tokens. Unmatched questions get a polite
holding reply and are forwarded to the owner's chat; when the owner replies to
the forwarded message, the bot sends that reply back to the person who asked.

Secrets come from the environment only:
  TELEGRAM_BOT_TOKEN      token from @BotFather
  TELEGRAM_OWNER_CHAT_ID  your own chat id (send /id to the bot to learn it)

Modes:
  --sample            offline demo on an embedded KB (no network)
  --ask TEXT          offline: show what the bot would answer (no network)
  --whoami            check the token with getMe
  --run               start the bot (long polling, Ctrl+C to stop)

Exit codes: 0 = ok, 1 = question not answered from KB (--ask), 2 = config/API error.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE = 4096
MAX_UNANSWERED_LOG = 500
MAX_RELAY = 2000
WORD = re.compile(r"\w+", re.UNICODE)
STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "i", "you", "we", "to", "of", "for", "in", "on", "and", "or",
    "can", "how", "what", "my", "me", "it", "be", "with", "please", "hi", "hello",
    "и", "в", "во", "на", "не", "а", "но", "что", "как", "я", "мы", "вы", "ты", "у", "с", "со", "по", "к",
    "за", "из", "о", "об", "это", "ли", "же", "бы", "мне", "вам", "нам", "есть", "можно", "здравствуйте",
    "привет", "пожалуйста", "подскажите", "скажите",
}

DEFAULT_TEXTS = {
    "greeting": "Hi! Ask me a question — I'll answer right away if I know it, or pass it on and reply here.",
    "fallback": "Thanks! I've passed your question on — the answer will come here in this chat.",
}

SAMPLE_KB = {
    "meta": {"greeting": "Привет! Задайте вопрос — отвечу сразу или передам владельцу.",
             "fallback": "Спасибо! Передал вопрос, ответ придёт сюда же."},
    "entries": [
        {"id": "faq_prices", "question": "Сколько стоит подписка?",
         "phrasings": ["цена", "сколько стоит", "стоимость тарифа", "how much is it", "price"],
         "answer": "Базовый тариф — 990 ₽/мес, Pro — 2 490 ₽/мес. Оплата картой или по счёту."},
        {"id": "faq_reset_pw", "question": "Как сбросить пароль?",
         "phrasings": ["забыл пароль", "не могу войти", "восстановить доступ", "reset password"],
         "answer": "Нажмите «Забыли пароль?» на странице входа — ссылка придёт на почту за 1-2 минуты."},
        {"id": "faq_hours", "question": "Когда вы работаете?",
         "phrasings": ["часы работы", "во сколько отвечаете", "график", "working hours"],
         "answer": "Отвечаем в будни с 10:00 до 19:00 по Москве."},
    ],
}
SAMPLE_QUESTIONS = ["Сколько стоит Pro тариф?", "забыл пароль, что делать", "Можно вернуть деньги за прошлый месяц?"]


def tokens(text):
    return {w[:5] for w in WORD.findall(text.lower()) if w not in STOPWORDS and len(w) > 1}


def dice(a, b):
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def match(kb, question, min_score=50, min_margin=10):
    q = tokens(question)
    scored = []
    for entry in kb.get("entries", []):
        variants = [entry.get("question", "")] + list(entry.get("phrasings", []))
        best = max((dice(q, tokens(v)) for v in variants if v), default=0.0)
        scored.append((round(best * 100), entry))
    scored.sort(key=lambda s: s[0], reverse=True)
    top = scored[0] if scored else (0, None)
    second = scored[1][0] if len(scored) > 1 else 0
    confident = top[1] is not None and top[0] >= min_score and top[0] - second >= min_margin
    return {
        "question": question,
        "answered": confident,
        "entry_id": top[1]["id"] if confident else None,
        "answer": top[1]["answer"] if confident else None,
        "top": [{"id": e["id"], "score": s} for s, e in scored[:3]],
    }


def load_kb(path):
    with open(path, encoding="utf-8") as f:
        kb = json.load(f)
    if not isinstance(kb, dict) or not isinstance(kb.get("entries"), list):
        raise ValueError("KB must be an object with an `entries` list")
    for e in kb["entries"]:
        if not e.get("id") or not e.get("answer"):
            raise ValueError(f"KB entry without id or answer: {e!r:.80}")
    return kb


class TelegramError(Exception):
    def __init__(self, code, description, retry_after=None):
        super().__init__(f"Telegram API error {code}: {description}")
        self.code, self.retry_after = code, retry_after


def api(token, method, params=None, timeout=40):
    req = urllib.request.Request(API.format(token=token, method=method),  # noqa: SEC-AUDITOR - fixed host api.telegram.org, the Bot API contract
                                 data=json.dumps(params or {}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: SEC-AUDITOR - only the Request built above
            body = json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            body = json.load(exc)
        except (json.JSONDecodeError, ValueError):
            raise TelegramError(exc.code, "non-JSON error response") from None
    if not body.get("ok"):
        raise TelegramError(body.get("error_code"), body.get("description"),
                            (body.get("parameters") or {}).get("retry_after"))
    return body["result"]


def chunks(text):
    while text:
        if len(text) <= MAX_MESSAGE:
            yield text
            return
        cut = text.rfind("\n", 0, MAX_MESSAGE)
        cut = cut if cut > MAX_MESSAGE // 2 else MAX_MESSAGE
        yield text[:cut]
        text = text[cut:].lstrip("\n")


def send(token, chat_id, text, reply_to=None):
    sent = []
    for part in chunks(text):
        params = {"chat_id": chat_id, "text": part}
        if reply_to:
            params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        sent.append(api(token, "sendMessage", params))
    return sent


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"offset": None, "relay": {}, "unanswered": []}


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def handle(token, owner, kb, state, update, args):
    msg = update.get("message")
    if not msg or "text" not in msg:
        return
    chat, text = msg["chat"], msg["text"].strip()
    texts = {**DEFAULT_TEXTS, **kb.get("meta", {})}

    if owner and str(chat["id"]) == owner:
        replied = (msg.get("reply_to_message") or {}).get("message_id")
        target = state["relay"].get(str(replied)) if replied else None
        if target:
            send(token, target["chat_id"], text, reply_to=target["message_id"])
            send(token, chat["id"], "✅ Sent.", reply_to=msg["message_id"])
            return
    if chat.get("type") != "private":
        return
    if text == "/id":
        send(token, chat["id"], f"Your chat id: {chat['id']}")
        return
    if text in ("/start", "/help"):
        send(token, chat["id"], texts["greeting"])
        return

    result = match(kb, text, args.min_score, args.min_margin)
    if result["answered"]:
        send(token, chat["id"], result["answer"], reply_to=msg["message_id"])
        return
    send(token, chat["id"], texts["fallback"], reply_to=msg["message_id"])
    state["unanswered"] = (state["unanswered"] + [{"text": text, "ts": msg.get("date")}])[-MAX_UNANSWERED_LOG:]
    if owner:
        who = msg.get("from", {})
        name = " ".join(filter(None, [who.get("first_name"), who.get("last_name")])) or "someone"
        handle_name = f" @{who['username']}" if who.get("username") else ""
        forwarded = send(token, owner, f"❓ {name}{handle_name} (chat {chat['id']}):\n\n{text}\n\n↩️ Reply to this message to answer.")
        for part in forwarded:
            state["relay"][str(part["message_id"])] = {"chat_id": chat["id"], "message_id": msg["message_id"]}
        for stale in list(state["relay"])[:-MAX_RELAY]:
            del state["relay"][stale]


def run(token, owner, kb, args):
    state = load_state(args.state)
    try:
        me = api(token, "getMe")
    except TelegramError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    print(f"@{me.get('username')} is running. KB entries: {len(kb['entries'])}. Owner relay: {'on' if owner else 'OFF'}.")
    while True:
        try:
            updates = api(token, "getUpdates",
                          {"offset": state.get("offset"), "timeout": 30, "allowed_updates": ["message"]}, timeout=40)
        except TelegramError as exc:
            if exc.code == 401:
                print("error: token rejected (401)", file=sys.stderr)
                sys.exit(2)
            time.sleep(exc.retry_after or 5)
            continue
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(5)
            continue
        for update in updates:
            state["offset"] = update["update_id"] + 1
            try:
                handle(token, owner, kb, state, update, args)
            except TelegramError as exc:
                print(f"warning: update {update['update_id']}: {exc}", file=sys.stderr)
                if exc.retry_after:
                    time.sleep(exc.retry_after)
            save_state(args.state, state)


def main():
    parser = argparse.ArgumentParser(description="Telegram FAQ bot: answers from a KB file, relays the rest to the owner. "
                                                 "Token and owner id come from TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--sample", action="store_true", help="offline demo on an embedded KB (no network)")
    mode.add_argument("--ask", metavar="TEXT", help="offline: what would the bot answer to TEXT (no network)")
    mode.add_argument("--whoami", action="store_true", help="check the token with getMe")
    mode.add_argument("--run", action="store_true", help="start the bot (long polling)")
    parser.add_argument("--kb", help="knowledge-base JSON (faq-knowledge-base format); defaults to the sample KB for --sample/--ask")
    parser.add_argument("--state", default="faq_bot_state.json", help="state file: polling offset, relay map, unanswered log")
    parser.add_argument("--min-score", type=int, default=50, help="minimum match score 0-100 to answer from the KB")
    parser.add_argument("--min-margin", type=int, default=10, help="minimum lead over the second-best entry")
    parser.add_argument("--json", action="store_true", help="output as JSON (--sample / --ask)")
    args = parser.parse_args()

    try:
        kb = load_kb(args.kb) if args.kb else SAMPLE_KB
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.sample or args.ask:
        questions = SAMPLE_QUESTIONS if args.sample else [args.ask]
        results = [match(kb, q, args.min_score, args.min_margin) for q in questions]
        if args.json:
            print(json.dumps(results if args.sample else results[0], indent=2, ensure_ascii=False))
        else:
            for r in results:
                verdict = f"ANSWER ({r['entry_id']})" if r["answered"] else "RELAY TO OWNER"
                print(f"{r['question']}\n  -> {verdict}; top: {r['top']}")
                if r["answer"]:
                    print(f"     {r['answer']}")
        sys.exit(0 if args.sample or results[0]["answered"] else 1)

    if not (args.whoami or args.run):
        parser.error("choose one of --sample, --ask, --whoami, --run")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()  # noqa: SEC-AUDITOR - the bot's own token, sent only to Telegram
    if not token:
        print("error: set TELEGRAM_BOT_TOKEN (from @BotFather) in the environment", file=sys.stderr)
        sys.exit(2)
    if args.whoami:
        try:
            me = api(token, "getMe")
        except (TelegramError, urllib.error.URLError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps({"id": me["id"], "username": me.get("username")}) if args.json
              else f"OK: @{me.get('username')} (id {me['id']})")
        return
    if not args.kb:
        print("error: --run needs --kb path/to/faq.json", file=sys.stderr)
        sys.exit(2)
    owner = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip() or None
    try:
        run(token, owner, kb, args)
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
