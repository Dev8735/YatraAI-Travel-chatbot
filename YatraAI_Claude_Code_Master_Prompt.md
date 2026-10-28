# YatraAI — Master Build Prompt for Claude Code

Copy the entire prompt below into Claude Code after opening your project folder.

---

## ROLE AND WORKING STYLE

Act as a senior full-stack engineer, NLP engineer, RAG architect, product designer, and security-conscious technical lead. Build **YatraAI — Intelligent Real-Time Travel Companion** directly in the current repository.

Do not only provide a plan, pseudocode, or isolated snippets. Inspect the existing repository first, then implement the application in working, testable stages. If the repository already contains code, preserve useful work and adapt it rather than replacing it blindly.

Work autonomously on routine implementation decisions. If a choice is not specified, choose a sensible production-minded default and document it. Do not claim a feature works unless it is implemented and tested. Keep the app runnable throughout development, and finish by reporting what was built, commands to run it, tests performed, and anything that still needs credentials or follow-up.

## 1. PRODUCT VISION

Build **YatraAI**, a polished, conversational travel assistant that can answer questions grounded in public website content and combine those answers with travel discovery and planning tools.

This must be a real NLP/RAG application—not a static FAQ page, hard-coded demo chatbot, or simple wrapper around an LLM.

Core user outcomes:

- Ask questions about a website or a collection of public web pages and receive answers grounded in retrieved source material.
- See citations and open the underlying source pages.
- Discover destinations, attractions, restaurants, hotels, and other places using live provider data when credentials are configured.
- Create and refine multi-day itineraries based on dates, interests, pace, starting point, transport, and budget.
- Compare destinations and explain the trade-offs.
- Ask follow-up questions naturally, with relevant conversational context retained.
- Communicate in English, Hindi, Gujarati, and common Hinglish phrasing where supported by the selected language model and embeddings.
- Use the app in a clearly labelled demo/offline mode if external credentials are missing.

## 2. TECHNOLOGY STACK

Use a maintainable, typed, modular architecture. Prefer:

### Frontend
- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui or similarly accessible, consistent UI components
- A responsive layout suitable for desktop and mobile
- Map integration only when a valid provider key is configured

### Backend
- Python with FastAPI
- Pydantic request/response models
- A clean service layer separating API routes, business logic, providers, and data access
- Async I/O where appropriate

### Data and retrieval
- PostgreSQL for users/sessions where needed, conversations, messages, sources, ingestion jobs, and itinerary records
- Qdrant for vector search, with a local/dev configuration that is straightforward to run
- A multilingual embedding model from Sentence Transformers, selected and documented for the target languages
- Configurable LLM provider through environment variables; keep provider-specific code behind a common interface

### Development and delivery
- Docker Compose for local services where practical
- `.env.example` containing variable names and safe placeholders only
- Database migrations
- Unit and integration tests
- A comprehensive README with setup, architecture, configuration, troubleshooting, and limitations

If the repository or environment makes one of these choices impractical, explain the reason in the README and implement the closest reliable alternative. Avoid unnecessary infrastructure and do not introduce services that are not actually used.

## 3. USER EXPERIENCE AND DESIGN

Create a premium, modern travel product—not a generic admin dashboard.

The interface should include:

- A clean landing/chat workspace with a clear YatraAI identity.
- A prominent chat input with example prompts.
- Streaming responses if practical with the chosen architecture.
- Readable assistant messages with source citations, place cards, itinerary cards, and route summaries.
- A conversation sidebar or conversation history on larger screens.
- A source/knowledge panel for website ingestion and indexing status.
- A trip-planning workspace for destination, dates, preferences, and budget.
- Responsive mobile navigation and accessible controls.
- Loading, empty, error, offline, and no-results states.
- Keyboard accessibility, appropriate focus indicators, semantic HTML, and sufficient contrast.

Use consistent spacing, typography, restrained travel-inspired visual styling, and high-quality component states. Do not fill the interface with fake statistics, fake reviews, or decorative controls that do nothing. Every visible action must work or be clearly disabled with an explanation.

## 4. WEBSITE INGESTION AND KNOWLEDGE BASE

Implement a website ingestion pipeline that can accept a public starting URL and index relevant pages for question answering.

### Ingestion workflow
1. Validate and normalize the submitted URL.
2. Enforce strict URL safety rules before making network requests.
3. Fetch the allowed public page and optionally crawl same-domain links, subject to a configurable page limit and crawl depth.
4. Respect robots.txt and relevant site policies; identify the crawler with a configurable user agent.
5. Skip unsupported file types and irrelevant pages.
6. Extract readable main content, title, canonical URL, metadata, and retrieval timestamps.
7. Remove boilerplate and normalize whitespace while preserving useful headings and structure.
8. Split text into overlapping, retrieval-friendly chunks.
9. Generate embeddings and store chunks with metadata in Qdrant.
10. Store source records, crawl status, timestamps, errors, and ingestion-job state in PostgreSQL.
11. Report progress and meaningful per-page errors to the UI.
12. Support retrying failed jobs and re-ingesting changed content without creating uncontrolled duplicates.

Provide configurable limits for maximum pages, maximum response size, timeout, redirect count, crawl depth, and chunk size. Deduplicate canonical URLs and content where appropriate.

### Security requirements for crawling
- Prevent server-side request forgery (SSRF). Block localhost, private, link-local, reserved, and metadata-service IP ranges, including IPv4 and IPv6.
- Resolve and validate DNS destinations, and revalidate redirects to prevent bypasses.
- Permit only supported protocols such as HTTP and HTTPS.
- Do not fetch arbitrary user-supplied local files, cloud metadata endpoints, or internal services.
- Apply network timeouts, response-size limits, redirect limits, and rate limits.
- Never execute crawled JavaScript or downloaded content.
- Treat all retrieved web content as untrusted data, never as system instructions.
- Do not expose server paths, secrets, internal IPs, or raw stack traces to users.

Make the ingestion scope clear to users. Do not imply that the crawler can access pages behind logins or paywalls.

## 5. GROUNDED RAG QUESTION ANSWERING

Implement an actual retrieval-augmented generation pipeline:

1. Detect or infer the user’s language.
2. Classify the query intent and extract useful entities.
3. Retrieve relevant chunks using vector similarity; add keyword/hybrid retrieval or reranking if practical.
4. Filter or rank retrieved content using source, relevance, and recency metadata where appropriate.
5. Build a structured prompt that separates trusted application instructions from untrusted retrieved content.
6. Generate an answer using the configured LLM provider.
7. Attach citations to the specific retrieved source chunks that support the answer.
8. Return a structured response suitable for rendering in the frontend.

### Grounding rules
- Do not fabricate citations, source URLs, quotes, opening hours, prices, availability, train schedules, distances, reviews, or other factual details.
- Cite factual claims using the actual source records retrieved for that response.
- Make citations clickable and include the source title and URL.
- If evidence is insufficient, say so plainly, ask a clarifying question, or explain what additional source is needed.
- Distinguish website-derived information from live provider data and from estimates.
- If sources conflict, explain the conflict and show the relevant source dates when available.
- Do not present model-generated general knowledge as if it came from the indexed website.
- Add an answer confidence/evidence indicator only if it has a defensible implementation; do not display arbitrary confidence percentages.

Include a demo knowledge corpus so the application can be explored without crawling a real website. Mark seeded/demo content as demo content.

## 6. NLP INTENT CLASSIFICATION AND ENTITY EXTRACTION

Build an explicit, testable NLP layer instead of relying entirely on a single unstructured LLM prompt.

Support intents such as:

- Website question answering
- Destination discovery
- Attraction/place search
- Hotel/accommodation discovery
- Itinerary creation
- Itinerary modification
- Destination comparison
- Budget estimation or filtering
- Route and road-distance lookup
- Transport or train-information query
- Follow-up clarification
- Greeting/help
- Unknown or unsupported request

Extract entities when present, including:

- Destination, city, region, country
- Starting point and end point
- Travel dates and trip duration
- Number of travellers when relevant
- Budget and currency
- Interests and activity types
- Accommodation preferences
- Transport mode
- Preferred pace and accessibility needs

Use a hybrid strategy: deterministic rules and date/money/location parsing for predictable cases, supplemented by a model when needed. Validate extracted values with typed schemas. Do not assume missing details. Ask concise clarifying questions when essential information is missing.

Include tests for common English, Hindi, Gujarati, and Hinglish examples. Document limitations honestly; do not claim perfect multilingual understanding.

## 7. CONVERSATION MEMORY AND FOLLOW-UPS

Implement persistent conversations with:

- Conversation and message IDs
- Role, timestamp, and relevant structured metadata
- A conversation history endpoint
- Context-aware follow-up handling, including references such as “that place,” “make it cheaper,” “add one more day,” and “remove the museum”
- A bounded context window or summarization strategy to control token use
- A way to start a new conversation and rename or delete conversations where appropriate

Store only information needed for the product. Do not put API keys or secrets into conversation records. Do not use one user’s conversation context in another user’s session. If authentication is not implemented, clearly document the local/demo security model and avoid pretending the app provides production multi-user isolation.

## 8. LIVE PLACES, HOTELS, AND PHOTOS

Create provider adapters for place discovery and details. Use Google Places API when configured, or a documented alternative provider if appropriate.

Support, where the provider permits:

- Place search by location and category
- Place details
- Coordinates and formatted address
- Provider-supplied ratings and review counts
- Opening hours when available
- Provider-supplied photos and required attributions
- Place cards that link to a provider or source

All provider fields must be mapped defensively because data can be missing. Show loading and no-results states.

### Data integrity rules
- Never invent a hotel, place, rating, review, image, price, room availability, or opening time.
- Use real provider photo references/URLs and follow the provider’s attribution and caching rules.
- Clearly distinguish live results, seeded demo records, and mock fallback results.
- If no API key is configured, provide a useful demo mode with visibly labelled sample data rather than silently returning fake live results.
- Do not claim that Google Places provides live hotel room inventory or booking availability. If actual room prices and availability are desired, design a separate accommodation-provider adapter and only display data returned by that provider.
- Do not scrape websites in ways that violate provider terms or access restrictions.

Put provider-specific logic behind interfaces so providers can be changed without rewriting the UI.

## 9. ROUTES, MAPS, AND DISTANCES

Implement a route service using Google Routes API when configured, or another documented routing provider.

Support:
- Origin and destination lookup
- Road distance and estimated travel duration returned by the provider
- Route summary and map display where available
- Multi-stop route planning if supported
- Clear indication of the selected travel mode
- A source/provider label and last-updated context when useful

Never fabricate exact road distances or drive times. If the routing provider is unavailable, either omit the value or show a clearly labelled rough estimate with a clear explanation. Do not present a straight-line distance as road distance.

Keep map keys and provider secrets on the appropriate side of the application. Follow provider restrictions on API keys and map data.

## 10. ITINERARY BUILDER

Create an itinerary engine that produces a practical day-by-day plan from the user’s constraints.

Inputs may include:
- Starting city and destinations
- Arrival/departure dates or number of days
- Budget and currency
- Interests (nature, heritage, food, beaches, temples, museums, adventure, photography, etc.)
- Pace (relaxed, balanced, packed)
- Transport mode
- Accommodation preferences
- Accessibility or other stated constraints

The itinerary should:
- Group attractions geographically where possible.
- Avoid unnecessary backtracking where route data supports that decision.
- Respect travel time and opening-hour data when available.
- Leave realistic time for meals, rest, and transfers.
- Distinguish verified facts from assumptions and suggestions.
- Show a concise reason for each recommendation.
- Allow the user to add, remove, reorder, or replace stops and regenerate affected days.
- Save itineraries and support follow-up edits.
- Display route distances only when supported by a routing provider or clearly marked as estimates.

Do not claim that a proposed itinerary is guaranteed feasible. Explain when opening hours, booking availability, or transport schedules have not been verified.

## 11. DESTINATION COMPARISON AND RECOMMENDATIONS

Allow users to compare destinations using criteria such as travel time, interests, seasonality, estimated budget, landscape, family suitability, and activity variety.

Recommendations should explain why a place matches the user’s stated preferences. Make the ranking criteria transparent and avoid arbitrary numerical scores unless the scoring method is documented.

Do not make unsupported claims about safety, accessibility, weather, costs, or seasonal conditions. When current information matters, use a suitable provider or explain that it needs verification.

## 12. TRAIN AND OTHER TRANSPORT INFORMATION

Create a transport-provider interface that can be connected to a verified schedule or ticketing source.

- Only display schedules, fares, seat availability, and booking links when returned by a real configured provider or a trustworthy cited source.
- Do not invent train numbers, direct connections, departure times, fares, or seat availability.
- If no provider is configured, explain the limitation and provide a link to an official source where appropriate.
- Distinguish general route suggestions from confirmed timetable data.
- Keep transport integrations optional so the rest of the application works without them.

## 13. BACKEND API DESIGN

Implement documented, validated API endpoints. Adjust names to fit the repository, but cover these capabilities:

- `GET /health` — service and dependency health
- `POST /api/chat` — process a user message and return a structured response
- `GET /api/conversations` — list available conversations in the supported user/session model
- `POST /api/conversations` — create a conversation
- `GET /api/conversations/{id}` — retrieve messages and metadata
- `DELETE /api/conversations/{id}` — delete a conversation where supported
- `POST /api/knowledge/sources` — register a website source
- `GET /api/knowledge/sources` — list sources and ingestion status
- `POST /api/knowledge/sources/{id}/ingest` — start or retry ingestion
- `GET /api/knowledge/jobs/{id}` — inspect ingestion progress
- `DELETE /api/knowledge/sources/{id}` — remove a source and associated indexed content
- `GET /api/places/search` — search places
- `GET /api/places/{id}` — retrieve place details
- `POST /api/routes` — calculate a route
- `POST /api/itineraries` — create an itinerary
- `GET /api/itineraries/{id}` — retrieve a saved itinerary
- `PATCH /api/itineraries/{id}` — modify an itinerary
- `DELETE /api/itineraries/{id}` — delete an itinerary

Use Pydantic models, meaningful HTTP status codes, consistent error response schemas, input validation, pagination where relevant, and OpenAPI documentation. Do not expose internal provider responses without validation and normalization.

## 14. CONFIGURATION AND SECRETS

Create a useful `.env.example` with variables for the database, Qdrant, LLM provider, embeddings, Google Places, Google Routes, and any optional transport provider.

Requirements:
- No real credentials in source control.
- Validate required configuration at startup and give actionable error messages.
- The app must still start in supported demo mode when optional external API keys are absent.
- Never expose server-side API keys in frontend bundles or API responses.
- Add `.env`, local databases, generated secrets, and other sensitive files to `.gitignore`.
- Document where to obtain each key and which features require it.
- Keep development and production configuration distinct.

Important: using Claude Code does not automatically give the deployed application access to an Anthropic model. If the app uses Anthropic, it needs its own API credentials and billing/configuration. The app should also support another provider or demo mode where feasible.

## 15. SECURITY, PRIVACY, AND RELIABILITY

Implement appropriate protections, including:

- URL and input validation
- SSRF-safe website fetching
- Request timeouts and bounded payloads
- Rate limiting for expensive endpoints
- Safe rendering of user and retrieved content; sanitize HTML and avoid unsafe rendering
- CORS configured from environment variables
- Secure handling of secrets
- No sensitive values in logs
- Structured logging and request IDs
- Consistent error handling
- Database transaction handling and migration support
- Defensive handling of external provider errors and rate limits
- Clear separation of trusted instructions and untrusted retrieved content
- Basic abuse protection for crawling and LLM endpoints

Do not claim enterprise-grade security or production readiness without the necessary authentication, authorization, deployment controls, and security review.

## 16. TESTS AND EVALUATION

Write meaningful automated tests, not just placeholder tests.

Include:
- Unit tests for intent classification and entity extraction
- Chunking and retrieval tests
- RAG citation and insufficient-evidence behavior tests
- Website URL validation and SSRF protection tests
- API validation and error-handling tests
- Itinerary creation and editing tests
- Provider adapter tests using mocks
- Frontend tests for key user flows where practical
- A small evaluation dataset with representative questions and expected source documents

Track or document evaluation measures such as:
- Retrieval relevance/recall on the evaluation set
- Citation correctness
- Answer groundedness
- Intent classification accuracy
- API reliability and latency

Do not fabricate passing test results. Run the available test suites and report actual outcomes.

## 17. DEMO MODE

The application must be useful for a reviewer who has not configured external API credentials.

Provide:
- A small, clearly labelled sample travel knowledge base
- A guided example question
- A demo ingestion/source status if a real crawl is not configured
- Clearly labelled sample place data only where needed
- Graceful messaging when live search, maps, transport, or LLM providers are not configured
- A predictable fallback strategy that does not pretend mock results are live

Prefer deterministic local behavior for tests. Keep demo data separate from production data and make it easy to replace.

## 18. README AND PROJECT DOCUMENTATION

Write a complete README covering:

1. Product overview and feature list
2. Architecture diagram using Mermaid
3. Repository structure
4. Prerequisites
5. Setup and installation
6. Environment variables and where to obtain API keys
7. How to start frontend, backend, PostgreSQL, and Qdrant
8. Database migration and seed commands
9. How to ingest a website
10. How to use grounded Q&A and citations
11. How to configure live places and routes
12. Demo/offline mode
13. Tests and evaluation
14. Common errors and troubleshooting
15. Security considerations and known limitations
16. Deployment notes

Also include useful API examples and sample prompts. Ensure the documented commands match the actual repository.

## 19. IMPLEMENTATION WORKFLOW

Proceed in stages, but do the work rather than stopping after each planning phase.

### Stage A — Inspect and plan
- Inspect the repository and existing environment.
- Identify existing conventions and reuse useful code.
- Create a concise implementation checklist.
- Confirm the chosen architecture in the README or a short architecture note.

### Stage B — Establish the runnable skeleton
- Set up the frontend and backend.
- Add configuration, health checks, and consistent errors.
- Add Docker Compose and environment examples where appropriate.
- Verify the basic application starts.

### Stage C — Build persistence and ingestion
- Add migrations and data models.
- Implement secure fetching, extraction, chunking, embeddings, indexing, and ingestion status.
- Add tests for URL safety and ingestion behavior.

### Stage D — Implement NLP and RAG
- Add intent/entity processing, retrieval, answer generation, citation mapping, and conversation history.
- Add groundedness and insufficient-evidence tests.

### Stage E — Implement travel capabilities
- Add place discovery, provider adapters, route calculation, itinerary creation/editing, and optional transport integrations.
- Add clear demo behavior for missing keys.

### Stage F — Build and connect the UI
- Implement chat, sources, citations, place cards, itinerary builder, route summaries, and conversation history.
- Connect every UI action to a working backend capability.
- Check responsive and accessible behavior.

### Stage G — Verify and document
- Run formatting, linting, type checks, migrations, tests, and builds that are available.
- Fix failures caused by the implementation.
- Test demo mode without external API keys.
- Update README and `.env.example`.
- Report exact commands and test outcomes.

If a long-running task cannot be completed in one pass, leave the repository in a coherent, runnable state and document the next concrete steps. Never hide incomplete functionality behind fake success messages.

## 20. DEFINITION OF DONE

The project is complete only when:

- The repository contains the implemented application, not just a design or plan.
- The frontend and backend have documented startup commands.
- Demo mode works without external provider credentials, to the extent documented.
- Website content can be ingested safely and retrieved for grounded answers.
- Answers cite real indexed source records, and unsupported claims are handled honestly.
- Conversation history and relevant follow-ups work.
- Live provider integrations use real returned data when configured and visibly distinguish demo data otherwise.
- Itinerary creation and modification are implemented.
- Important security and validation cases have tests.
- The available automated tests and builds have been run, with actual results documented.
- The README and `.env.example` are accurate.
- No secrets, invented live results, fake citations, or nonfunctional UI controls remain.

**Start now:** inspect the current repository, then implement YatraAI in working stages. Do not stop at a plan. Make reasonable decisions, run checks, fix issues, and clearly report any remaining limitations or configuration steps.
