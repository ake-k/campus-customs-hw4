"""Campus Customs API (FastAPI).

Serves the product catalogue, per-size stock, and product images from the local
SQLite database; account sign-up / login; and the shop chatbot (a PydanticAI
agent, see agent.py).

Run from this folder:  uvicorn main:app --reload --port 8000
"""

import asyncio
import fcntl
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from collections import OrderedDict, deque
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic_ai.exceptions import UsageLimitExceeded

from agent import SYSTEM_PROMPT_SHA256, now_iso, run_chat
from models import (
    AuditEntry,
    ChatHistory,
    ChatLimits,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    CustomerProfile,
    LoginRequest,
    PreferencesUpdate,
    ProductResults,
    SessionOut,
    SignupRequest,
    UserOut,
)
from tools import (
    CHAT_MODEL,
    normalize_size,
    similar_products,
    DATA_DIR,
    DB_PATH,
    HW4_DIR,
    AssistantNotConfigured,
    DatabaseMissing,
    all_products,
    cards_for,
    connect,
    product_by_id,
)

log = logging.getLogger("campus_customs")
if not log.handlers:  # uvicorn configures only its own loggers; give ours a handler so INFO lines show
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     [campus_customs] %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False

app = FastAPI(title="Campus Customs API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DatabaseMissing)
def database_missing(_: Request, exc: DatabaseMissing) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=500)


@app.get("/api/health")
def health() -> dict:
    return {"ok": DB_PATH.exists()}


@app.get("/api/products")
def list_products(
    q: str | None = Query(None, description="Search name, description, colors, and tags"),
    category: str | None = None,
) -> list[dict]:
    products = all_products()
    if category:
        products = [p for p in products if p["category"].lower() == category.lower()]
    if q:
        words = q.lower().split()
        def haystack(p: dict) -> str:
            return " ".join([p["name"], p["garment_type"], p["description"], *p["colors"], *p["search_tags"]]).lower()
        products = [p for p in products if all(w in haystack(p) for w in words)]
    return products


@app.get("/api/categories")
def list_categories() -> list[dict]:
    counts: dict[str, int] = {}
    for p in list_products(q=None, category=None):
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    return [{"name": name, "count": n} for name, n in sorted(counts.items())]


@app.get("/api/products/{product_id}/similar")
def similar(product_id: str, size: str | None = None, limit: int = Query(4, ge=1, le=12)) -> list[dict]:
    """'You might also like' for a product page: similar items, in stock in `size` if given (the shopper's size)."""
    base = product_by_id(product_id)
    if base is None:
        raise HTTPException(404, "Product not found")
    norm = normalize_size(size) if size else None
    picks = similar_products(base, norm, None, limit)
    if norm and len(picks) < limit:  # top up with similar items in other sizes
        seen = {p["product_id"] for p, _, _ in picks}
        picks += [t for t in similar_products(base, None, None, limit * 2) if t[0]["product_id"] not in seen][: limit - len(picks)]
    return [{**p, "why_similar": why} for p, _, why in picks]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> dict:
    p = product_by_id(product_id)
    if p is None:
        raise HTTPException(404, "Product not found")
    return p


# ---------- Accounts: sign-up, login, sessions ----------
# Passwords are never stored. We store a salted, slow, memory-hard Argon2id
# hash (the hash embeds its own random salt and cost settings). The seed
# users were created with PBKDF2-SHA256 (120,000 iterations); those hashes
# still verify and are upgraded to Argon2id the next time that user logs in.

PASSWORDS = PasswordHasher()  # Argon2id, RFC 9106 low-memory profile: t=3, m=64 MiB, p=4
LEGACY_PBKDF2_ITERATIONS = 120_000
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(16))  # equalizes timing for unknown emails

SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"  # set true behind HTTPS

MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 15 * 60
failed_logins: dict[str, list[float]] = {}  # "email|ip" -> recent failure times


def hash_password(password: str) -> str:
    return PASSWORDS.hash(password)


def verify_password(stored: str, password: str) -> bool:
    if stored.startswith("$argon2"):
        try:
            return PASSWORDS.verify(stored, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
    if stored.startswith("pbkdf2_sha256$"):  # legacy seed format: pbkdf2_sha256$<salt>$<hex>
        try:
            _, salt, digest = stored.split("$")
        except ValueError:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), LEGACY_PBKDF2_ITERATIONS).hex()
        return hmac.compare_digest(candidate, digest)
    return False


def needs_upgrade(stored: str) -> bool:
    return not stored.startswith("$argon2") or PASSWORDS.check_needs_rehash(stored)


def ensure_sessions_table() -> None:
    if not DB_PATH.exists():
        return
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL
            )"""
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")


ensure_sessions_table()


def token_digest(token: str) -> str:
    # Only a SHA-256 of the session token is stored, so a leaked DB can't be used to hijack sessions.
    return hashlib.sha256(token.encode()).hexdigest()


def user_out(row: sqlite3.Row) -> UserOut:
    first = row["first_name"] or row["name"].split(" ")[0]
    last = row["last_name"] or " ".join(row["name"].split(" ")[1:])
    size = row["preferred_size"] if "preferred_size" in row.keys() else None
    return UserOut(
        id=row["id"], first_name=first, last_name=last, name=row["name"], email=row["email"],
        created_at=row["created_at"], preferred_size=size,
    )


def start_session(conn: sqlite3.Connection, response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, datetime('now', ?))",
        (token_digest(token), user_id, f"+{SESSION_DAYS} days"),
    )
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/",
    )


def current_user(request: Request) -> sqlite3.Row | None:
    """The logged-in user's row for this request, or None. The agent will use this too."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with connect() as conn:
        return conn.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > datetime('now')""",
            (token_digest(token),),
        ).fetchone()


def too_many_failures(key: str) -> bool:
    now = time.time()
    recent = [t for t in failed_logins.get(key, []) if now - t < LOCKOUT_SECONDS]
    failed_logins[key] = recent
    return len(recent) >= MAX_FAILED_LOGINS


@app.exception_handler(RequestValidationError)
def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Turn Pydantic's error list into one friendly sentence for the form.
    first = exc.errors()[0] if exc.errors() else {}
    msg = str(first.get("msg", "Invalid request.")).removeprefix("Value error, ")
    field = first.get("loc", [""])[-1]
    if first.get("type") == "string_too_short" and field == "password":
        msg = "Passwords need at least 8 characters."
    elif first.get("type") == "string_too_short":
        msg = "Please fill in every field."
    elif first.get("type") == "string_too_long":
        msg = f"{str(field).replace('_', ' ').capitalize()} is too long."
    return JSONResponse({"detail": msg}, status_code=422)


@app.post("/api/auth/signup", status_code=201)
def signup(body: SignupRequest, response: Response) -> SessionOut:
    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
                (f"{body.first_name} {body.last_name}", body.email, hash_password(body.password), body.first_name, body.last_name),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account with that email already exists. Try logging in.")
        start_session(conn, response, cur.lastrowid)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return SessionOut(user=user_out(row))


@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request, response: Response) -> SessionOut:
    key = f"{body.email}|{request.client.host if request.client else ''}"
    if too_many_failures(key):
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (body.email,)).fetchone()
        if row:
            ok = verify_password(row["password_hash"], body.password)
        else:
            verify_password(DUMMY_HASH, body.password)  # spend the same time so response speed doesn't reveal valid emails
            ok = False
        if not ok:
            failed_logins.setdefault(key, []).append(time.time())
            raise HTTPException(401, "Incorrect email or password.")  # same message whether or not the email exists
        failed_logins.pop(key, None)
        if needs_upgrade(row["password_hash"]):
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.password), row["id"]))
        start_session(conn, response, row["id"])
    return SessionOut(user=user_out(row))


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> SessionOut:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_digest(token),))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return SessionOut(user=None)


@app.get("/api/auth/me")
def me(request: Request) -> SessionOut:
    row = current_user(request)
    return SessionOut(user=user_out(row) if row else None)


# ---------- Chat (PydanticAI agent) ----------
# Logged-in shoppers: every message is saved in chat_messages (with the product
# page it was sent from), so the assistant remembers them across visits.
# Guests: a short history kept in server memory, keyed by a random HttpOnly
# cookie, and gone when the server restarts.

def ensure_chat_schema() -> None:
    """chat_messages ships with the seed database; add what customer memory needs (idempotent)."""
    if not DB_PATH.exists():
        return
    with connect() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "page_product_id" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN page_product_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id, id)")
        user_cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
        if "preferred_size" not in user_cols:  # the size picker's choice, saved per account
            conn.execute("ALTER TABLE users ADD COLUMN preferred_size TEXT")
        # Messages the input check blocked before they reached the model (for review; no raw IPs stored).
        conn.execute(
            """CREATE TABLE IF NOT EXISTS chat_screening_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                user_id INTEGER,
                client_hash TEXT NOT NULL,
                reason TEXT NOT NULL,
                excerpt TEXT NOT NULL
            )"""
        )


ensure_chat_schema()

CHAT_TIMEOUT_SECONDS = 90  # a shopper never waits longer than this for one reply
CHAT_COOKIE = "cc_chat"
GUEST_CHATS_MAX = 500  # oldest guest conversations are dropped beyond this
GUEST_MESSAGES_MAX = 30
guest_chats: OrderedDict[str, list[ChatMessageOut]] = OrderedDict()


def load_history(request: Request, user: UserOut | None, limit: int = 30) -> list[ChatMessageOut]:
    if user is None:
        return list(guest_chats.get(request.cookies.get(CHAT_COOKIE, ""), []))
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json, page_product_id FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user.id, limit),
        ).fetchall()
    history = []
    for r in reversed(rows):
        ids = [p.get("product_id") for p in json.loads(r["products_json"] or "[]") if isinstance(p, dict)]
        # Re-read cards from the database so old messages show today's price and stock.
        history.append(ChatMessageOut(
            role=r["role"], content=r["content"], products=cards_for([i for i in ids if i]), page_product_id=r["page_product_id"],
        ))
    return history


def customer_profile(user: UserOut) -> CustomerProfile:
    """The customer fields the agent is allowed to see (from users + chat_messages)."""
    with connect() as conn:
        stats = conn.execute(
            "SELECT count(*) AS n, max(created_at) AS last FROM chat_messages WHERE user_id = ?", (user.id,)
        ).fetchone()
    return CustomerProfile(
        user_id=user.id, first_name=user.first_name, last_name=user.last_name, email=user.email,
        member_since=user.created_at[:10], saved_messages=stats["n"], last_chat_at=stats["last"],
        preferred_size=user.preferred_size,
    )


def guest_key_for(request: Request) -> tuple[str, bool]:
    """This browser's guest-chat key, and whether it's new (then the response must set the cookie)."""
    key = request.cookies.get(CHAT_COOKIE)
    return (key, False) if key else (secrets.token_urlsafe(24), True)


def set_guest_cookie(response: Response, key: str) -> None:
    response.set_cookie(CHAT_COOKIE, key, httponly=True, samesite="lax", secure=COOKIE_SECURE, path="/")


def save_turn(user: UserOut | None, guest_key: str, turn: list[ChatMessageOut]) -> None:
    if user is None:
        key = guest_key
        messages = guest_chats.pop(key, []) + turn
        guest_chats[key] = messages[-GUEST_MESSAGES_MAX:]
        while len(guest_chats) > GUEST_CHATS_MAX:
            guest_chats.popitem(last=False)
        return
    with connect() as conn:
        conn.executemany(
            "INSERT INTO chat_messages (user_id, role, content, products_json, page_product_id) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    user.id, m.role, m.content,
                    json.dumps([c.model_dump() for c in m.products]) if m.products else None,
                    m.page_product_id,
                )
                for m in turn
            ],
        )


def page_results(message: str, output, products: list, viewed_id: str | None = None) -> ProductResults | None:
    """Turn the agent's product_ids into the cards the website renders on the page.

    Cards are rebuilt from the database (cards_for), and the category total and link
    are computed here, so the model never supplies a price, stock count, or URL.
    No shelf when the only product is the one whose page is already open.
    """
    if not products or (viewed_id and all(c.product_id == viewed_id for c in products)):
        return None
    category = output.see_all_category
    total = sum(1 for p in all_products() if p["category"] == category) if category else None
    return ProductResults(
        heading=(output.results_heading or "").strip() or ("Our " + category.lower() if category else "Picked for you"),
        query=message,
        products=products,
        category=category,
        category_total=total,
        see_all_url=f"/products?category={quote(category)}" if category else None,
    )


# ---------- Chat limits + input check (run before anything reaches the model) ----------

CHAT_LIMIT_PER_MINUTE = int(os.getenv("CHAT_LIMIT_PER_MINUTE", "8"))
CHAT_LIMIT_PER_DAY = int(os.getenv("CHAT_LIMIT_PER_DAY", "150"))
IP_LIMIT_FACTOR = 4  # guests are also capped per IP (x4) so clearing cookies doesn't reset the limit
chat_hits: dict[str, deque[float]] = {}  # limit key -> send times in the last 24 h
recent_texts: dict[str, deque[tuple[float, str]]] = {}  # limit key -> last few messages (duplicate check)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def limit_rules(request: Request, user: UserOut | None, guest_key: str) -> list[tuple[str, int, int]]:
    """(key, per_minute, per_day) rules that apply to this shopper: one per account, or per guest + per IP."""
    if user:
        return [(f"user:{user.id}", CHAT_LIMIT_PER_MINUTE, CHAT_LIMIT_PER_DAY)]
    return [
        (f"guest:{guest_key}", CHAT_LIMIT_PER_MINUTE, CHAT_LIMIT_PER_DAY),
        (f"ip:{client_ip(request)}", CHAT_LIMIT_PER_MINUTE * IP_LIMIT_FACTOR, CHAT_LIMIT_PER_DAY * IP_LIMIT_FACTOR),
    ]


def check_limits(rules: list[tuple[str, int, int]]) -> ChatLimits:
    """Raise 429 if any rule is over its per-minute or per-day cap; otherwise count this message and report what's left."""
    now = time.time()
    left_min, left_day, retry = [], [], 0
    for key, per_min, per_day in rules:
        hits = chat_hits.setdefault(key, deque())
        while hits and now - hits[0] > 86400:
            hits.popleft()
        in_minute = [t for t in hits if now - t < 60]
        if len(hits) >= per_day:
            retry = max(retry, int(86400 - (now - hits[0])) + 1)
        elif len(in_minute) >= per_min:
            retry = max(retry, int(60 - (now - in_minute[0])) + 1)
        left_min.append(per_min - len(in_minute))
        left_day.append(per_day - len(hits))
    if retry:
        daily = any(len(chat_hits[k]) >= d for k, _, d in rules)
        msg = (
            f"You've reached today's chat limit ({rules[0][2]} messages). Please come back tomorrow, or email orderdept@campuscustoms.com."
            if daily else
            f"Whoa, that's a lot of messages at once! Please wait {retry} seconds and try again."
        )
        raise HTTPException(429, detail=msg, headers={"Retry-After": str(retry)})
    for key, _, _ in rules:
        chat_hits[key].append(now)
    return ChatLimits(
        remaining_this_minute=min(left_min) - 1, remaining_today=min(left_day) - 1,
        per_minute=rules[0][1], per_day=rules[0][2],
    )


INJECTION_PATTERNS = [
    r"\bignore\s+(?:all\s+|any\s+|the\s+|your\s+|my\s+)?(?:previous\s+|prior\s+|above\s+|earlier\s+|system\s+|original\s+)?(?:instructions|rules|prompts?|directions|guidelines)\b",
    r"\b(?:disregard|forget|override|bypass)\s+(?:all\s+|your\s+|the\s+|previous\s+)*(?:instructions|rules|prompts?|guidelines|safety)\b",
    r"\b(?:reveal|show|print|repeat|leak|output|tell me)\b.{0,30}\b(?:system prompt|your (?:instructions|prompt|rules)|hidden (?:prompt|instructions))\b",
    r"\bsystem\s+prompt\b",
    r"\b(?:developer|god|dan|admin|debug)\s+mode\b",
    r"\bjailbreak|\bdo anything now\b",
    r"\byou are (?:now|no longer)\b",
    r"\bnew (?:instructions|rules|system)\s*:",
    r"</?\s*(?:system|assistant|instructions?)\s*>|\[(?:system|inst)\]",
]
INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PASSWORD_RE = re.compile(r"\b(password|passcode|passwd|pin)(\s*(?:is|:|=)\s*)(\S+)", re.IGNORECASE)

SCREEN_REPLIES = {
    "prompt_injection": "I can only help with Campus Customs shopping, and I can't change my rules or share my instructions. "
                        "Want help finding something? Try “navy hoodies in L”.",
    "gibberish": "Hmm, I couldn't quite read that. Could you rephrase? For example: “Do you have gray crewnecks?”",
    "duplicate": "Looks like you sent that same message a few times. I answered it above! Ask me something new or rephrase it.",
}


@dataclass
class Screened:
    text: str  # the message after redaction (what the model would see)
    reason: str | None  # None = allowed; otherwise a key of SCREEN_REPLIES
    redactions: list[str]


def screen_message(text: str, key: str) -> Screened:
    """Input check on every chat message, before the model sees it."""
    redactions = []
    if SSN_RE.search(text):
        text, _ = SSN_RE.subn("[SSN removed]", text)
        redactions.append("ssn")
    if PASSWORD_RE.search(text):
        text = PASSWORD_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[removed]", text)
        redactions.append("password")
    if "[card number removed]" in text:  # done by ChatRequest's validator
        redactions.append("card_number")
    norm = " ".join(text.lower().split())
    words = norm.split()
    letters = sum(ch.isalpha() for ch in norm)
    if INJECTION_RE.search(text):
        return Screened(text, "prompt_injection", redactions)
    if (len(norm) >= 12 and letters / max(len(norm), 1) < 0.35) or re.search(r"(.)\1{14,}", norm) or (
        len(words) >= 10 and max(words.count(w) for w in set(words)) / len(words) > 0.6
    ):
        return Screened(text, "gibberish", redactions)
    now = time.time()
    seen = recent_texts.setdefault(key, deque(maxlen=3))
    repeats = sum(1 for t, m in seen if m == norm and now - t < 120)
    seen.append((now, norm))
    if repeats >= 2:  # third identical message within 2 minutes
        return Screened(text, "duplicate", redactions)
    return Screened(text, None, redactions)


def log_screening(user: UserOut | None, key: str, reason: str, text: str) -> None:
    log.warning("chat screened reason=%s user=%s", reason, user.id if user else "guest")
    with connect() as conn:
        conn.execute(
            "INSERT INTO chat_screening_log (user_id, client_hash, reason, excerpt) VALUES (?, ?, ?, ?)",
            (user.id if user else None, hashlib.sha256(key.encode()).hexdigest()[:16], reason, text[:160]),
        )


# ---------- Audit trail (append-only) ----------
# Every chat request adds one AuditEntry to output/audit_trail.json: answered, screened,
# rate-limited, timed out, or failed. Earlier entries are never removed or rewritten.

AUDIT_PATH = Path(os.getenv("AUDIT_TRAIL_PATH", HW4_DIR / "output" / "audit_trail.json"))


def append_audit(entry: AuditEntry, path: Path = AUDIT_PATH) -> None:
    """Append one entry under an exclusive file lock (safe if several requests finish together)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    with os.fdopen(fd, "r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        raw = f.read()
        entries: list = []
        if raw.strip():
            try:
                entries = json.loads(raw)
                if not isinstance(entries, list):
                    raise ValueError("audit trail is not a list")
            except ValueError:
                # Never discard history: keep the unreadable file beside it and start a new list.
                path.with_name(f"{path.stem}.unreadable-{datetime.now():%Y%m%d-%H%M%S}.json").write_text(raw, encoding="utf-8")
                entries = []
        entries.append(entry.model_dump(mode="json"))
        f.seek(0)
        f.truncate()
        f.write(json.dumps(entries, indent=2, ensure_ascii=False))
        f.flush()
        os.fsync(f.fileno())


def audit(request_started: float, started_iso: str, kind: str, status: str, stop_reason: str, body: ChatRequest,
          user: UserOut | None, *, message: str = "", redactions: list[str] | None = None, deps=None, reply: str = "",
          product_ids: list[str] | None = None, size: str | None = None) -> None:
    trace = getattr(deps, "trace", None)
    iterations = trace.iterations if trace else []
    entry = AuditEntry(
        run_id=secrets.token_hex(6), kind=kind, started_at=started_iso, finished_at=now_iso(),
        total_seconds=round(time.time() - request_started, 2), status=status, stop_reason=stop_reason,
        model=CHAT_MODEL, system_prompt_sha256=SYSTEM_PROMPT_SHA256,
        shopper=f"user:{user.id}" if user else "guest",
        page_path=body.page.path if body.page else None,
        page_product_id=(deps.page_product["product_id"] if deps and deps.page_product else (body.page.product_id if body.page else None)),
        preferred_size=size, message=message[:300], redactions=redactions or [], iterations=iterations,
        tools_used=list(deps.tool_calls) if deps else [], product_ids=product_ids or [], reply=reply[:400],
        grounding_retries=deps.grounding_retries if deps else 0, usage=trace.usage if trace else AuditEntry.model_fields["usage"].default_factory(),
    )
    try:
        append_audit(entry)
    except OSError:
        log.exception("Could not write the audit trail")


# ---------- Chat routes ----------

async def answer(body: ChatRequest, request: Request, user: UserOut | None, guest_key: str, on_progress=None) -> ChatResponse:
    """Limits -> input check -> agent -> save -> audit. Shared by POST /api/chat and /api/chat/stream. Raises HTTPException."""
    started, started_iso = time.time(), now_iso()
    rules = limit_rules(request, user, guest_key)
    try:
        limits = check_limits(rules)
    except HTTPException as exc:
        audit(started, started_iso, "rate_limited", "blocked", f"rate limit: {exc.detail}", body, user,
              message="(not recorded: over the limit)")
        raise
    screened = screen_message(body.message, rules[0][0])
    if screened.reason:
        log_screening(user, rules[0][0], screened.reason, screened.text)
        reply = SCREEN_REPLIES[screened.reason]
        audit(started, started_iso, "screened", "blocked", f"input check blocked the message ({screened.reason}); model not called",
              body, user, message=screened.text, redactions=screened.redactions, reply=reply)
        return ChatResponse(reply=reply, screened=True, limits=limits, products=[], results=None, user=user)
    message = screened.text
    history = load_history(request, user)
    customer = customer_profile(user) if user else None
    size = user.preferred_size if user and user.preferred_size else body.preferred_size
    holder: dict = {}

    def fail(reason: str, status_code: int, detail: str) -> HTTPException:
        audit(started, started_iso, "chat", "error", reason, body, user, message=message, redactions=screened.redactions,
              deps=holder.get("deps"), size=size)
        return HTTPException(status_code, detail)

    try:
        output, products, deps = await asyncio.wait_for(
            run_chat(message, history, user, customer, body.page, size, on_progress, holder), timeout=CHAT_TIMEOUT_SECONDS
        )
    except TimeoutError:
        log.warning("Chat timed out after %ss", CHAT_TIMEOUT_SECONDS)
        raise fail(f"timeout: no answer within {CHAT_TIMEOUT_SECONDS}s", 503, "Sorry, that took too long on my end. Please try asking again.")
    except UsageLimitExceeded as exc:
        raise fail(f"usage limit reached ({exc})", 503, "That one took me too many steps. Could you ask in a simpler way?")
    except AssistantNotConfigured as exc:  # PORTKEY_API_KEY missing
        log.error("Chat unavailable: %s", exc)
        raise fail("assistant not configured (missing PORTKEY_API_KEY)", 503, "The shopping assistant isn't configured right now. Please try again later.")
    except Exception as exc:
        log.exception("Chat agent failed")
        raise fail(f"error: {type(exc).__name__}: {str(exc)[:200]}", 503, "Sorry, I couldn't reach the shop's assistant just now. Please try again in a moment.")
    reply = output.reply.strip()
    viewed_id = deps.page_product["product_id"] if deps.page_product else None
    results = page_results(message, output, products, viewed_id)
    log.info(
        "chat user=%s page=%s size=%s tools=%s products=%d grounding_retries=%d redactions=%s %.1fs",
        user.id if user else "guest", body.page.path if body.page else "-", size, deps.tool_calls, len(products),
        deps.grounding_retries, screened.redactions, time.time() - started,
    )
    save_turn(user, guest_key, [
        ChatMessageOut(role="user", content=message, page_product_id=viewed_id),
        ChatMessageOut(role="assistant", content=reply, products=products),
    ])
    trace = deps.trace
    final = trace.final_tool if trace else None
    audit(started, started_iso, "chat", "ok",
          f"final answer accepted ({final or 'final_result'}; model finish_reason={trace.finish_reason if trace else None})",
          body, user, message=message, redactions=screened.redactions, deps=deps, reply=reply,
          product_ids=[c.product_id for c in products], size=size)
    return ChatResponse(reply=reply, products=products, results=results, limits=limits, user=user)


def current_identity(request: Request) -> tuple[UserOut | None, str, bool]:
    row = current_user(request)
    key, is_new = guest_key_for(request)
    return (user_out(row) if row else None), key, is_new


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request, response: Response) -> ChatResponse:
    """One message from the website's chat widget -> the agent's reply plus product cards to show."""
    user, guest_key, is_new = current_identity(request)
    if user is None and is_new:
        set_guest_cookie(response, guest_key)
    return await answer(body, request, user, guest_key)


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    """Same as /api/chat, but streams newline-delimited JSON so the widget can show live progress:

        {"type": "status", "text": "Checking stock: Basic Hoodie Big Yale in L"}   (one per agent step)
        {"type": "done", "response": {...ChatResponse...}}                         (last line)
        {"type": "error", "status": 429, "detail": "...", "retry_after": 23}      (instead of done)
    """
    user, guest_key, is_new = current_identity(request)
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def progress(text: str) -> None:
        await queue.put({"type": "status", "text": text})

    async def work() -> None:
        try:
            resp = await answer(body, request, user, guest_key, progress)
            await queue.put({"type": "done", "response": resp.model_dump(mode="json")})
        except HTTPException as exc:
            await queue.put({
                "type": "error", "status": exc.status_code, "detail": exc.detail,
                "retry_after": int((exc.headers or {}).get("Retry-After", 0)) or None,
            })
        except Exception:
            log.exception("Chat stream failed")
            await queue.put({"type": "error", "status": 500, "detail": "Sorry, something went wrong. Please try again."})
        finally:
            await queue.put(None)

    async def lines():
        task = asyncio.create_task(work())
        try:
            while (event := await queue.get()) is not None:
                yield json.dumps(event) + "\n"
        finally:
            if not task.done():  # shopper closed the page mid-answer
                task.cancel()

    stream = StreamingResponse(lines(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    if user is None and is_new:
        set_guest_cookie(stream, guest_key)
    return stream


@app.put("/api/me/preferences")
def update_preferences(body: PreferencesUpdate, request: Request) -> SessionOut:
    """Save the size picked in the size picker to the logged-in shopper's account."""
    row = current_user(request)
    if row is None:
        raise HTTPException(401, "Log in to save your size to your account.")
    with connect() as conn:
        conn.execute("UPDATE users SET preferred_size = ? WHERE id = ?", (body.preferred_size, row["id"]))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
    return SessionOut(user=user_out(row))


@app.get("/api/chat/history")
def chat_history(request: Request) -> ChatHistory:
    """Earlier messages for this shopper (saved chats if logged in, this browser's guest chat otherwise)."""
    row = current_user(request)
    user = user_out(row) if row else None
    return ChatHistory(messages=load_history(request, user), user=user)


# ---------- Product photos ----------
# Most catalogue photos had transparent backgrounds that were flattened to pure
# black. We flood-fill the black region connected to the image border with
# white (garments are navy, not pure black, so they are untouched) and cache
# the cleaned copy. Originals in data/products/ are never modified.

PRODUCTS_DIR = DATA_DIR / "products"
IMAGE_CACHE = HW4_DIR / "backend" / ".image_cache" / "v3"  # bump when the cleanup changes
BLACK_MAX = 18  # a pixel counts as background if all channels are <= this
POCKET_MIN_SHARE = 0.002  # enclosed pure-black areas larger than 0.2% of the image are background too
POCKET_BLACK_MAX = 4  # pockets must be essentially exact black (flattened transparency), not fabric shadow


def whiten_background(src: Path, dest: Path) -> None:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    img = Image.open(src).convert("RGB")
    w, h = img.size
    brightest = ImageChops.lighter(ImageChops.lighter(*img.split()[:2]), img.split()[2])
    mask = brightest.point(lambda v: 255 if v <= BLACK_MAX else 0)
    border = [(x, y) for x in range(0, w, 8) for y in (0, h - 1)] + [(x, y) for y in range(0, h, 8) for x in (0, w - 1)]
    for xy in border:
        if mask.getpixel(xy) == 255:
            ImageDraw.floodfill(mask, xy, 128)
    # Pockets of old background enclosed by the garment (e.g. between an arm and the body) don't touch
    # the border. They are exact black, unlike shadowed fabric, so use a much stricter test, then keep
    # small regions (logo details) and whiten big ones.
    pocket = brightest.point(lambda v: 255 if v <= POCKET_BLACK_MAX else 0)
    mask = Image.composite(mask, pocket, mask.point(lambda v: 255 if v == 128 else 0))
    min_area = int(w * h * POCKET_MIN_SHARE)
    for y in range(0, h, 6):
        for x in range(0, w, 6):
            if mask.getpixel((x, y)) == 255:
                ImageDraw.floodfill(mask, (x, y), 64)
                area = mask.histogram()[64]
                ImageDraw.floodfill(mask, (x, y), 128 if area >= min_area else 32)
    background = mask.point(lambda v: 255 if v == 128 else 0).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1))
    Image.composite(Image.new("RGB", img.size, "white"), img, background).save(dest, quality=92)


@app.get("/media/products/{filename}")
def product_image(filename: str) -> FileResponse:
    src = (PRODUCTS_DIR / filename).resolve()
    if src.parent != PRODUCTS_DIR.resolve() or not src.is_file():
        raise HTTPException(404, "Image not found")
    IMAGE_CACHE.mkdir(parents=True, exist_ok=True)
    cached = IMAGE_CACHE / filename
    if not cached.exists() or cached.stat().st_mtime < src.stat().st_mtime:
        try:
            whiten_background(src, cached)
        except Exception:  # never block a product photo on the cleanup step
            return FileResponse(src)
    return FileResponse(cached, headers={"Cache-Control": "public, max-age=86400"})
