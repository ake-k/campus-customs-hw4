# Campus Customs: Shop + Chatbot

> **How it all works** (architecture, data types, tools, safety rules, specs, audit trail): see [`output/harness.md`](output/harness.md).

A customer website for Campus Customs (Yale Bulldog Blue), a New Haven shop selling officially licensed Yale apparel.

- **Frontend:** React + Vite + TypeScript (`frontend/`)
- **Backend:** Python FastAPI (`backend/`), reading a local SQLite catalogue

## Project layout

```
hw4/
├── AI_prompts.md            # every prompt used to build this, by problem
├── requirements.txt         # Python dependencies (backend)
├── .env.example             # placeholder settings; copy to .env
├── .gitignore               # keeps .env, the data pack, images, caches, venvs out of git
├── README.md
├── frontend/                # Vite + React + TypeScript storefront
├── backend/
│   ├── main.py              # FastAPI app (run with uvicorn, see below)
│   ├── agent.py             # ┐
│   ├── tools.py             # │ the PydanticAI shopping agent:
│   ├── models.py            # │ wiring, tools, data types, system prompt
│   └── prompts/prompt.md    # ┘
└── output/
    ├── harness.md           # how the whole system works (start here)
    ├── design.md            # storefront design write-up
    ├── usability.md         # usability improvements write-up
    ├── app_check.html       # live-site checks (open in a browser)
    ├── app_check_images/    # screenshots used by the write-ups
    └── audit_trail.json     # append-only log of agent activity
```

## 0. Get the code

```bash
git clone https://github.com/ake-k/campus-customs-hw4.git
cd campus-customs-hw4/hw4
```

Requirements: Python 3.10+ and Node.js 20.19+ (for Vite).

## 1. Add the data pack (not included in this repo)

The database and product photos are **not** in git. Unzip the course data pack so this folder exists:

```
hw4/data/campus_customs.db
hw4/data/products/*.jpg        (102 product photos; paths match the catalogue table)
```

`../data/` (next to `hw4/`) also works, or set `DATA_DIR` in `.env` to any folder that contains `campus_customs.db` and `products/`.
Both locations are ignored by git. On first start, the backend adds what it needs to the database: a `sessions` table, a `chat_screening_log` table, `users.preferred_size`, and `chat_messages.page_product_id`. The provided data itself is unchanged.

## 2. Configure secrets

```bash
cp .env.example .env
```

Then fill in `PORTKEY_API_KEY` in `.env` (in the `hw4/` folder). Never commit `.env`. The chatbot uses `CHAT_MODEL` (default `gpt-6-luna`) through Portkey. Without a key, the store still works and only the chat is unavailable.

## 3. Run the backend (port 8000)

From the `hw4/` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --port 8000
```

Check it's up: http://localhost:8000/api/health should return `{"ok": true}` (`false` means the data pack wasn't found).

The first time each product photo is requested, the backend makes a cleaned copy with a white background and caches it in `backend/.image_cache/`. The first page load can take a few seconds.

API:

| Endpoint | What it returns |
|---|---|
| `GET /api/products?q=&category=` | All products with per-size stock (optional search/filter) |
| `GET /api/products/{product_id}` | One product with per-size stock |
| `GET /api/products/{product_id}/similar?size=` | "You might also like": similar items, in stock in `size` first |
| `GET /api/categories` | Shop categories with product counts |
| `GET /media/products/{file}.jpg` | Product photo |
| `POST /api/auth/signup` | Create an account (first/last name, email, password, confirm) and sign in |
| `POST /api/auth/login` | Log in with email + password (sets an HttpOnly session cookie) |
| `POST /api/auth/logout` | End the session |
| `GET /api/auth/me` | The signed-in user, or `null` |
| `POST /api/chat` | Send `{"message": "...", "page": {"path", "product_id", "category"}}` to the shop assistant; returns `{reply, products, results, user}`. `results` holds product cards to show on the page (see `output/harness.md`, Appendix A6) |
| `POST /api/chat/stream` | Same as `/api/chat`, but streams live progress lines (NDJSON) and then the reply. The website uses this one |
| `GET /api/chat/history` | This shopper's earlier chat messages |
| `PUT /api/me/preferences` | Save `{"preferred_size": "L"}` (the size picker) to the logged-in shopper's account |

Test account from the seed database: `test@campuscustoms.yale.edu` / `password`.

## 4. Run the frontend (port 5173)

In a second terminal, from the `hw4/` folder:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite forwards `/api` and `/media` requests to the backend on port 8000. If you run the backend on another port, start Vite with `API_PORT=<port> npm run dev`.

Chat is limited to `CHAT_LIMIT_PER_MINUTE` (8) and `CHAT_LIMIT_PER_DAY` (150) messages per shopper, and every message is screened before it reaches the model. See `output/usability.md`.

## Pages

- **Home:** a featured product, then Game Day, Residential Colleges, Gifts, and New This Season collection rows, and shop-by-category
- **Products:** full catalogue with live-suggest search (header), a Shop menu, category tabs, a My size filter, and sorting
- **Bag:** items added from tiles or product pages; "Send order to the store" emails the order (online payment isn't connected)
- **Product page:** large photo and details, a sticky purchase panel (size, stock, quantity, Add to bag, Ask about this item), and "You might also like"
- **About Us:** the shop's story, what it makes, returns, and contact
- **Log in / Create account:** real accounts stored in the `users` table with Argon2id password hashes (see `output/harness.md`)
- **Chat:** the "Ask" button in the header opens the assistant in a side panel on any page. Logged-in shoppers' chats are saved and reloaded; on a product page, "this" means that product. It's a PydanticAI agent (`backend/agent.py`, `tools.py`, `prompts/prompt.md`) that answers price, size, and stock questions from the database and puts matching product cards on the page (a "From your conversation" section above any page; each card opens the product page).
