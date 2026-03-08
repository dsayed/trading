# UX & Tech Debt Audit

**Date:** 2026-02-28
**Scope:** Full frontend UX review + backend code quality audit

---

## Frontend UX Assessment

**Overall: 5/10 for new users** — works for power users who understand the system, but doesn't teach you anything.

### What Works Well

- Sidebar navigation is clean, flat, and labeled
- SymbolInput component has good tactile UX (add/backspace to remove)
- TanStack Query keeps data fetching sane — no loading waterfalls, proper cache invalidation
- PlayCard and SignalTable visuals are color-coded and readable
- Settings page structure has helpful labels with hint text
- Codebase is lean (~1,850 lines total)

### Problem: No Mental Model

The app has 4 core concepts — Watchlists, Scans, Positions, Plays — but never explains how they relate or what order to use them.

- No onboarding or empty-state guidance
- No explanation of domain jargon: "conviction", "tax lots", "playbook", "advisors"
- Sidebar doesn't hint at workflows (e.g., "start with Settings -> create Watchlists -> run Scan")
- Relationship between Scans (signal discovery) and Positions (portfolio tracking) is never explained

### Problem: PositionsPage Complexity

The most complex page — 11 local state variables:

- `isCreating`, `addingLotId`, `expandedId`, `symbol`, `quantity`, `costBasis`, `purchaseDate`, `lotQty`, `lotCost`, `lotDate`, plus query state
- Inline tax lot forms nested inside expandable table rows
- "Close" button for deletion (confusing label)
- No validation feedback on form fields
- Tax lot concept is never explained to the user

### Problem: Inconsistent Interaction Patterns

- WatchlistsPage: name is click-to-edit, but symbols use a separate input component
- Two ways to view signals: SignalTable shows data, clicking opens PlaybookPanel with the same data in a different layout (redundant)
- Some forms are inline (tax lots, watchlist name), others are separate panels (new position, new watchlist)
- No shared form component abstraction — input fields styled slightly differently across pages

### Problem: No User Feedback

- No toast/notification on successful save
- No confirmation dialogs for destructive actions (delete position, delete watchlist)
- No validation messages until you submit bad data
- No loading skeletons — "Loading..." text causes layout shift
- No indication of save state (did my edit persist?)

### Problem: Plays Page Confusion

- "Plays" vs "Scan" distinction is unclear — when do you use each?
- No explanation of what each advisor does (stock_play vs covered_call vs protective_put)
- Can run advisors on zero selected positions (defaults to all) — should require explicit selection
- No way to execute recommendations — it's analysis-only but that's not stated

### Problem: Settings Page Gaps

- Shows "Active Plugins" with no explanation of what they are
- No way to change plugins, only view them
- No validation ranges shown until you break them (e.g., "Stop Loss must be 1-50%")
- Stake/position/stop-loss fields would benefit from examples or formulas

---

## Backend Tech Debt Assessment

**Overall: 6/10** — solid MVP architecture with targeted debt that can be paid down incrementally.

### What's Well-Designed

- **Plugin architecture**: Protocol-based design with runtime checkable protocols. Clean separation of concerns. Extensible without modifying core.
- **Database layer**: SQLite with proper constraints, WAL mode, foreign keys. Context manager handles transactions correctly.
- **Testing**: Hand-written fakes (not mocks), good test isolation with `tmp_path`, proper DI overrides in API tests. 200+ tests passing.
- **API design**: Mostly RESTful, proper status codes (201/204/404/422), Pydantic separates request/response types.
- **Domain models**: Instrument, Position, TaxLot, Trade are well-thought-out. Tax lot calculations and long-term status tracking are correct.
- **Advisor logic**: Three advisors with solid domain logic. Tax-aware recommendations are thoughtful.

### Debt: Type Safety (38 `# type: ignore` comments)

**Files affected:** `repositories.py`, `api/routers/advise.py`, `api/routers/watchlists.py`

- `sqlite3.Row` bracket access loses type info across repositories.py
- `_play_to_response()` in advise.py accepts `object` then accesses attributes without type narrowing
- These mask real bugs — if wrong type is passed, runtime AttributeError instead of type-safe feedback

**Fix:** Replace `object` params with proper types, use TypedDict or dataclass for Row access patterns.

### Debt: Broad Exception Handling (5 bare `except Exception`)

**Files affected:** `engine.py` (3 instances), `database.py` (1), `plugins/data/yahoo.py` (1)

- Engine swallows network errors, bad data, and auth failures identically
- Users see 3 plays returned instead of 6 with no explanation why
- No differentiation between "API is down" vs "bad data" vs "invalid ticker"

**Fix:** Catch specific exceptions (ValueError, ConnectionError, KeyError), let unexpected errors propagate.

### Debt: Response Building Duplication

**Files affected:** `api/routers/positions.py`, `api/routers/scans.py`, `api/routers/advise.py`

- `_to_response()` helpers in three routers do similar dict-to-Pydantic transformations
- Average cost calculation duplicated in positions router and repositories
- Bug fix in one place requires remembering to fix all three

**Fix:** Extract shared response building into a utility module or move computation into repository layer.

### Debt: No Input Validation on Symbols

**Files affected:** `core/repositories.py` (WatchlistRepo.create)

- Watchlists accept any string: `""`, `"  AAPL  "`, `"FAKESYM"` — no checks
- No duplicate detection within a watchlist
- Scans then fail silently on invalid symbols

**Fix:** Add symbol validation (strip whitespace, uppercase, check format), reject duplicates.

### Debt: Scan Results as JSON Blobs

**Files affected:** `core/repositories.py` (ScanRepo), schema in `core/database.py`

- Scan results stored as JSON string in a single TEXT column
- 8 `json.dumps()` calls, 5 `json.loads()` calls in repositories.py
- Can't query "all scans with AAPL buy signals" without deserializing every row
- No validation during deserialization

**Fix:** Normalize into a separate `signal` table with foreign key to scan. Or keep JSON but add SQLite JSON functions for querying.

### Debt: Dead Code

- `bus.py` — EventBus class is defined but never imported or used anywhere
- `backtest/__init__.py` — exists but is empty (incomplete feature)

### Debt: Minor Inconsistencies

- Inconsistent naming: `Direction.CLOSE` vs `Direction.EXIT`, `OptionContract.option_type` is str instead of enum
- Some files use `_to_response()` function, others inline the transformation
- Mixed delete response patterns (some return 404 if not found, others would return 204)
- No structured error response schema — frontend has to parse `detail` strings

### Debt: Missing Test Coverage

- No tests for error paths (yfinance timeout, corrupted position data)
- No integration tests that run the full pipeline without mocks
- No concurrent request tests (two simultaneous scans racing on DB)

---

## Prioritized Fix Plan

| # | Area | Type | Impact | Effort |
|---|------|------|--------|--------|
| 1 | Fix type safety (kill `type: ignore`) | Backend | Prevents hidden runtime bugs | 2-3 hours |
| 2 | Add empty-state guidance / onboarding hints | Frontend | Biggest UX win for new users | 3-4 hours |
| 3 | Specific exception handling in engine | Backend | Users understand failures | 2-3 hours |
| 4 | Confirmation dialogs for destructive actions | Frontend | Prevents data loss | 1-2 hours |
| 5 | Consolidate response builders | Backend | Reduces duplication | 1-2 hours |
| 6 | Clean up dead code (bus.py, empty backtest) | Backend | Reduces confusion | 30 min |
| 7 | Add input validation on symbols | Backend | Prevents silent failures | 1-2 hours |
| 8 | Unify form patterns across pages | Frontend | Consistent UX | 3-4 hours |
| 9 | Add save/success feedback (toasts) | Frontend | Users know actions succeeded | 2-3 hours |
| 10 | Normalize scan results table | Backend | Enables querying, scalability | 3-4 hours |
