# AI Prompts Log — Homework 4 (Campus Customs Website + Chatbot)

This file logs every prompt given to the AI assistant (Claude Code) while completing Homework 4, organized by problem. Each section lists the initial prompt, any follow-up prompts, and a brief note on why a follow-up was needed.

---

## Problem 1: Setup

### Prompt 1
> Hi Claude! Today, we'll be working in the Homework 4 folder, and I want you to put all my work in there. Please confirm that you can read/write the Homework 4 folder.

### Prompt 2
> @"/Users/akekankirawatana/Downloads/data.zip"
> First, I'll describe the Scenario for Homework 4 (don't do anything yet):
>
> "Campus Customs needs a real customer website with a helpful chatbot. Your job is to build a React + Vite TypeScript frontend and a Python FastAPI backend whose brain is a PydanticAI agent. Shoppers should be able to browse products, create an account, chat about merch, see matching items appear on the page, and get honest answers about price and stock from a local database."
>
> I will give you campus_customs.db with tables for the product catalogue, inventory by size, and users (with hashed passwords). Product image file paths are in the catalogue table. Research yalebulldogblue.com to learn the style of Campus Customs page and information for the agent prompt.
>
> Use the PORTKEY_API_KEY, or whatever API key you have for the agent's AI calls. If using OpenAI through Portkey, use any models in the 5.6 or 6 series. You may want to use a smarter model for harder steps the agent takes.
>
> In the end, we will push the project to a public GitHub repo. Do NOT commit the database or product images.
>
> Here is the data for the assignment. Unzip it so there is data/campus_customs.db (SQLite database with tables catalogue, inventory, and users -- one test user is already there) and data/products/ (product images -- paths match the catalgoue table).
>
> Additionally, in order to submit the assignment once complete, I will need to put my code in a folder named hw4 and push it to a public GitHub repository. I will then submit the repo URL, which graders will open and clone. The expected file layout is attached (remember this for later, but don't create anything yet).
>
> Important: Do NOT put the real .env, campus_customs.db, or product images in the GitHub repo. Use .gitignore. Include .env.example with placeholders only.
>
> *(Attached: screenshot of the required `hw4/` folder structure.)*

### Prompt 3
> 1. Yes -- start logging from here on out.
> 2. Yes -- exactly.

*Note:* Prompt 3 answered two questions from the AI: whether to keep this prompt log (yes) and whether to put the repo in `Homework 4/hw4/` with `data/` beside it, outside the repo (yes). The AI then unzipped the data into `Homework 4/data/` (leaving out macOS `__MACOSX` files) and created the virtual environment at `Homework 4/.venv`.

**Follow-up needed?** No. These prompts were clear and were completed as asked.

---

## Problem 2: Analyze the database

### Initial Prompt
> Great! That was all Problem 1. Now onto Problem 2: Analyze the database.
>
> Look at data/campus_customs.db and understand the fields in it (there are catalogue, inventory, and users).
>
> Create output/harness.md. Write down each table and its fields, with a short 1-line description for why each field matters for the shop or chatbot. We will keep adding to the harness throughout the assignment.

*Note:* The AI also documented a fourth table found in the database, `chat_messages`, and listed data quirks that will affect the build: inconsistent `garment_type` values, JSON stored as text, and many sold-out sizes.

---

## Problem 3: Build the Campus Customs website

### Initial Prompt
> Great! Onto Problem 3: Build the Campus Customs website.
>
> Scaffold a React + Vite + TypeScript frontend for Campus Customs. Put a nav bar at the top that links to the main pages (Home, Products, About Us, Log in, Create account). Pull Campus Customs-style wording from yalebulldogblue.com for Home and About Us, but write these pages in your own voice without copying the original site text.
>
> The Products page should show product images from the catalogue using the image paths in the database. It should include basic product info, including name, price, and short description.
>
> Make each product open a single-item page (large image on one size with full product text on the other, including long description, price, sizes/stock, etc.). Clicking a card on Products should take the shopper there.
>
> Add a chat interface in the bottom right of the site (a floating chat panel is fine). It does not need to talk to an agent yet -- a stub that will call the backend later is enough -- as we will address that in a later problem.
>
> A small API will also be needed to read the database -- create a simple FastAPI app in backend/main.py just to serve products and images for now, as we will grow this into the full agent backend in a later problem.

*Note:* While building the site, the AI found that 73 of the 102 product photos have black backgrounds (flattened transparency) and 3 products have leftover placeholder descriptions. Neither was in the prompt. The AI fixed both on the backend without changing the provided data: it serves white-background copies of the photos and shows a neutral description instead of the placeholder text. Both fixes are documented in `output/harness.md`.

**Follow-up needed?** No.

---

## Problem 4: Create account and login

### Initial Prompt
> Great! Onto Problem 4: Create account and login.
>
> Build a create-account / login flow. Create account asks first name, last name, email, password, and confirm password. Login asks email and password.
>
> New accounts go in the users table. Make sure to store passwords securely so hackers -- AI or human -- cannot access them.
>
> The seed database already has a test user you can use while building. Its email is test@campuscustoms.yale.edu and its password is password.
>
> Confirm that you can log in as that user and that a brand new account you create works.
>
> Update output/harness.md with how auth works (what you store for a user and how passwords are protected).

*Note:* The seed hashes didn't say how they were made, so the AI determined the format (PBKDF2-SHA256, 120,000 iterations) by testing the provided test password. It then added Argon2id for new passwords, with an automatic upgrade of old hashes at login. Both the test-user login and a brand-new account ("Bulldog Tester") were verified end-to-end in the browser against the real database.

**Follow-up needed?** No.

---

## Problem 5: PydanticAI agent backend

### Initial Prompt
> Great! Onto Problem 5: PydanticAI agent backend.
>
> Build the shop chatbot as a PydanticAI agent behind FastAPI, plugged into the frontend chat widget. Put the API app in backend/main.py which will be run with Uvicorn. Keep the agent as these four files next to it (same way as you did in Homework 3): backend/prompts/prompt.md (system prompt, which we will add to later), backend/agent.py (agent entry / wiring), backend/tools.py (tools the agent can call), and backend/models.py (Pydantic / PydanticAI structured types).
>
> In main.py, expose a chat route so that a message from the website returns a reply from the agent, along with whatever is needed for products/auth. Use the AI model API key for the agent.
>
> Put basic info for Campus Custom's voice and safety in prompts/prompt.md (we will add to tools and safety in a later problem). Create or update types in models.py for chat replies and product cards as needed.
>
> In output/harness.md, note how the frontend communicates with FastAPI and how the agent is loaded (prompt file and model).
>
> Ensure the backend runs from the backend/ folder like this:
>
> uvicorn main:app --reload --port 8000

*Note:* During testing the AI found that gpt-6-luna rejects tool calls on the Chat Completions API, so it switched the agent to the Responses API. The first test round also showed the agent answering off-topic requests (it wrote a Python script) and offering hats the catalogue doesn't carry. The AI tightened `prompts/prompt.md` and re-tested. It also added redaction of card numbers in chat messages. All of this is documented in `output/harness.md`.

**Follow-up needed?** No.

---

## Problem 6: Tools: product info and stock

### Initial Prompt
> Great! Onto Problem 6: Tools: product info and stock.
>
> Create tools for the agent to look stuff up in campus_customs.db, such as product description, price, how many units are in stock (by size, if the customer asks).
>
> Make sure the agent uses the database and does not invent prices or quantities. If a size is out of stock, it should say so.
>
> Add to prompts/prompt.md so the agent knows to call these tools for price and stock questions. Add/update the return types in models.py.
>
> Explain each tool and which model fields are used for lookup results and why in output/harness.md.

*Note:* The AI built an automated 12-question evaluation with expected answers taken from the database. The first run passed 10/12: the agent answered one size question from search results and missed that only 2 were left. The AI added low-stock sizes to search results, required `get_stock` for size questions, and re-ran the evaluation (12/12). It also added a code check that rejects replies quoting prices or stock counts no tool returned, and proved it works with a scripted test model.

**Follow-up needed?** No.

---

## Problem 7: Chat search that updates the page

### Initial Prompt
> Great! Onto Problem 7: Chat search that updates the page.
>
> When a customer asks about a type of item (e.g., "What hoodies do you have?"), the agent should search the catalogue and the website should dynamically show those matching items as product cards with the product image, name, price, and short description.
>
> This is an API contract -- the agent returns structured product matches, and the frontend renders them on the site.
>
> After the dynamic product cards loads, make sure the same single-item page behavior from Problem 3 still works (each product card should open the detail view, with a large image and full description, when clicked.
>
> Update prompts/prompt.md and output/harness.md with how search results reach the page.

*Note:* The AI defined the chat → page contract in `models.py`. The agent returns `product_ids`, `results_heading`, and `see_all_category`; the server builds the cards, counts, and links from the database. The frontend renders them in a results shelf whose cards open the existing product page. Browser testing found that the color filter matched accent colors (a gray crewneck with navy lettering showed up as "navy"), so the AI changed it to match each garment's main color.

**Follow-up needed?** No.

---

## Problem 8: Customer memory

### Initial Prompt
> Great! Onto Problem 8: Customer memory.
>
> When a shopper is logged in, save their chat history in an appropriate table in the database and reload it when they return. The agent should know who (name, email) is talking to them. Put that in agent deps or an equivalent clear pattern, as well as the tools the agent can call.
>
> Also pass enough page context so that if someone is on a product page and asks, "Do you have this in pink?" or "Do you have this in size large?" the agent knows which item they are referring to. (Hint: You can put code into the agent context.)
>
> Guests can still chat, but the history only needs to persist for logged-in users.
>
> Document how user chat history is stored, what customer fields the agent sees, and how page context is passed in output/harness.md.

*Note:* Logged-in history already lived in `chat_messages` from Problem 5. The AI added a `page_product_id` column and an index, a `CustomerProfile` in the agent deps, three tools (`get_my_account`, `recall_past_conversations`, `get_viewed_product`), and page context sent from the browser and checked against the database. Browser tests across separate sessions turned up three gaps, each fixed and re-tested:
- the recall tool couldn't find the shopper's first (September) message
- "pink" missed a dusty-coral tee
- a duplicate one-card shelf appeared on product pages

**Follow-up needed?** No.

---

## Problem 9: Usability improvements

### Initial Prompt
> Great! Onto Problem 9: Usability improvements.
>
> Make the following usability improvements to the frontend and backend:
>
> * On the frontend, show live progress in the chat so the shopper can see the assistant working after they ask it a question
> * On the frontend, remember a shopper's size preference across the site by adding a size picker to the Products page and chat results, which would hide/gray out items not in stock in that size
> * On the backend, create a tool that finds in-stock alternatives, so that the agent can recommend similar products that are in stock in the shopper's preferred size
> * On the backend, set limits and an input check on the chat to cap how many messages a shopper (guest or logged-in) can send per minute per day and screen each message before it reached the model
>
>
> After you are done, write output/usability.md to document each improvement, describing what you added and why it helps a Campus Customs shopper or the business.
>
> Once you implement the improvements, check to make sure all improvements actually show up in the running app. I will be graded on whether these improvements were successfully implemented, based on the write-up in output/usability.md.

*Note:* The AI built all four improvements:
- live chat progress through a new streaming endpoint
- a "My size" picker that grays out or hides items, saved to the account
- a `find_alternatives` tool
- per-minute/per-day chat limits with an input check that blocks prompt injection and redacts passwords and SSNs

Each was verified in the running app with headless Chrome, and the screenshots are in `output/app_check_images/`. Verification found one real bug: on a product page, "Is this in stock?" was answered about a product from earlier in the chat. The AI added two guards (tagging the current message with its page, and an output-validator check) and re-tested 3/3. Everything is documented in `output/usability.md`.

**Follow-up needed?** No.

---

## Problem 10: Style the website

### Initial Prompt
> Great! Onto Problem 10: Style the website.
>
> Make the following changes to the website's design to improve customers' browsing and shopping experiences. The current design is somewhat outdated -- I want the new design to be sleek, modern, and elegant, providing shoppers a refined and convenient online shopping experience. Avoid cluttering the menu or burying key pages. The design should ensure shoppers have a seamless experience navigating the site, finding the product they want, and buying it. The new design should include:
>
> * Calmer look: Replace gradients, bevels, and heavy shadows with flat surfaces and white space, using a serif for headings, a clean sans for body text, Yale navy and warm off-white, and one accent color.
> * Slim navigation: Use a thin sticky header with live-suggest search, and icons for account, "My size," and the assistant, with one clean "Shop" dropdown.
> * Cleaner product tiles: Show uniform photos with name, price, and a small low-stock note, plus size buttons on hover and a sticky purchase panel with "You might also like" on product pages.
> * Curated homepage: Open with a featured product, then collection rows (Game Day, Residential Colleges, Gifts, New This Season)
> * Concierge assistant: Swap the floating bubble for a slim side panel with suggested questions and compact product rows, and use short fades instead of bouncy animations.
>
>
> After you are done, write output/design.md to document each improvement, describing what you changed and why it should help customers stick around and buy.
>
> Once you implement the improvements, check to make sure all improvements actually show up in the running app. I will be graded on whether these improvements were successfully implemented, based on the write-up in output/design.md.

*Note:* The AI rebuilt the frontend's look and layout:
- a new stylesheet, plus Fraunces and Inter fonts
- a slim header with a "Shop" dropdown, live-suggest search, and account / My size / Ask / bag controls
- new product tiles with hover size buttons, plus a bag page
- a product page with a sticky purchase panel and "You might also like", backed by a new `/api/products/{id}/similar` endpoint
- a curated homepage
- the assistant in a side panel

It verified each change in the running app with headless Chrome, and the screenshots are in `output/app_check_images/design-*.png`. Testing turned up several bugs, each fixed and re-verified:
- a crash on load, caused by an effect that returned `window.scrollTo()`'s Promise
- the purchase panel looked non-sticky, but that was the test's scroll position; sticky was confirmed at 150 and 300 px
- product photos showed black gaps between sleeves and body on the new white backgrounds; the backend image cleanup was improved without darkening fabric shadows

Everything is documented in `output/design.md`.

**Follow-up needed?** No.

---

## Problem 11: Site testing (app check)

### Initial Prompt
> Great! Onto Problem 11: Site testing (app check).
>
> I want your help testing the live site to make sure things work properly. Please test the following features on the live site to ensure they are working as expected. Capture a screenshot of the full webpage for each test (you should capture only three screenshots total).
>
> 1. Chat checking the inventory level of an item (honest stock/price from the database).
> 2. The dynamic search-result cards appearing after a category question (e.g., hoodies).
> 3. One of the usability features added in Problem 9 -- tool that finds in-stock alternatives, so that the agent can recommend similar products that are in stock in the shopper's preferred size.
>
>
> For each of the screenshots, write a short caption. Then, document the tests in output/app_check.html (a page that a grader can just double-click open). Make the HTML page easy to grade -- there should be a heading for each check, the screenshot, and 1-2 sentences on what the screenshot proves. Put the screenshot image files in output/app_check_images/ and link them from app_check.html with relative paths (e.g., app_check_images/inventory.png).

*Note:* The AI ran the three checks on the live site with headless Chrome, each in a fresh guest session, and compared every number in the chat replies with `campus_customs.db`. All three passed. The first full-page captures cut off the assistant side panel, because it is fixed to the screen, so the AI re-captured them with the browser window set to the page's full height. The results are in `output/app_check.html`, with screenshots `inventory.png`, `search_cards.png`, and `alternatives.png` in `output/app_check_images/`.

**Follow-up needed?** No.

---

## Problem 12: Audit trail, safety, finish harness

### Initial Prompt
> Great! Onto Problem 12: Audit trail, safety, finish harness.
>
> Keep an append-only output/audit_trail.json of agent-loop activity, including the time, tool name, short args/result, stop reason, etc. Do not wipe it between runs.
>
> Also, add safety guardrails for the agent in prompts/prompt.md (see safety guardrails from previous homework assignments for example).
>
> Finish output/harness.md so it is clear how the system works. A manager should be able to read it and quickly understand the model fields in models.py and why they were chosen, tools and abilities, safety rules, specs (e.g., loop limits, result caps, models, how to run frontend and backend, etc.).

*Note:* The AI added an append-only `output/audit_trail.json`:
- **Contents:** one entry per chat request, with per-iteration tool calls, shortened args and results, timings, stop reason, and token usage.
- **Coverage:** written with a file lock, and recorded for answered, blocked, rate-limited, and failed requests.
- **Verified:** it survived a server restart (10 → 11 entries), and a deliberately buggy first run showed that failed runs keep their partial trace.

In `prompts/prompt.md`, it added 10 numbered safety guardrails modeled on Homework 3's. A 10-message adversarial check was handled 10/10, and the price/stock evaluation still passed 12/12. Finally, it rewrote the top of `output/harness.md` as a manager's guide (overview, architecture, quick start, specs table, `models.py` field-by-field rationale, tools, layered safety rules, audit trail, evidence, file map), keeping the earlier per-problem notes as an appendix.

**Follow-up needed?** No.

---

## Problem 13: Push to GitHub and submit the URL

### Initial Prompt
> Great! Onto the final problem, Problem 13: Push to GitHub and submit the URL.
>
> Ensure the code is in the folder hw4 and push it to a public GitHub repository. Then, provide me the repo URL, which I will submit to the graders to open and clone.
>
> Do NOT put the real .env, campus_customs.db, or product images in the GitHub repo. Use .gitignore. Include .env.example with placeholders only.
>
> See the attached screenshot for the expected file layout. The local-only data pack (the database and product images) should not be in the git. The agent itself is four files under backend/ (prompts/prompt.md, agent.py, tools.py, and models.py). The README.md should explain how to run the frontend and backend after placing the data pack.
>
> *(Attached: screenshot of the required `hw4/` folder structure.)*
