# Release gates and INT253 demo

## Gates

1. **Academic slice (current):** registration, profile, manual capture/private file, review, events/tasks/opportunities, search, owner isolation, admin and responsive templates. SQLite fallback; PostgreSQL container standard. Automated test files are not part of this initial repository.
2. **Product foundations:** evidence spans and action audit, richer temporal semantics and date conflict detection, deterministic deduplication and revision decisions, safe export/deletion. Gate: duplicate import produces no second obligation and conflicting venue needs a decision.
3. **Assisted intake:** parsing and optional replaceable AI with strict schema, cost bound and side-by-side source review. Gate: one document yields two independently reviewed KYC events and failure falls back to manual.
4. **Durable reminders/PWA:** database scheduler, delivery attempts, opt-in channels and safe offline read cache; then installability and push if supported. Gate: restart/retry/reschedule remains observable and idempotent.
5. **Connected sources/deploy:** only after privacy review, credentials, provider approval, HTTPS, backups and operational tests. No provider integration is currently present.

## Course-outcomes-to-demo matrix

| Outcome | Demonstration |
|---|---|
| Project structure and commands | `manage.py`, `campus_radar/`, `core/`, `migrate`, `check`, `test` |
| Views, URLs, requests and errors | `/inbox/`, `/inbox/<id>/`, `/search/?q=...`; unknown record returns 404; method mismatch returns 405 |
| Template inheritance and dynamic content | `base.html` extended by Home/Inbox; loop, conditional and empty state with real records |
| Debugging and tests | Run `check` and migration validation; demonstrate a form error. Automated test files are not included in this first commit. |
| Forms, GET/POST, CSRF, PRG | Capture GET and POST; invalid PDF error; valid POST redirects; CSRF token in the form |
| Models, migrations, FK, ORM, admin, groups/permissions | `0001_initial`, notice→events/tasks; admin list/filter, Django Groups and model permissions; ordinary user cannot access admin |
| Cookies, sessions, users, protected views | Register, inspect session cookie (HttpOnly), log out by POST and observe redirect to login |

Demo data must be synthetic. Example: “Example University KYC, Group A 10:00–10:30, Group B 11:00–11:30 on 3 Feb 2027; bring ID.” Never commit a real notice or student data.
`seed_demo USERNAME` adds this and a sample assessment notice to an existing account without inventing an assessment time.
