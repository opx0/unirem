# Domain and transition contracts

The current monolith has a single `core` app for the bounded academic slice. Forms validate HTTP input; views scope every lookup by owner; models enforce linked-owner and temporal rules; templates present escaped content. Cross-domain extraction, provider adapters and durable reminders are deliberately absent rather than hidden stubs. Use a service layer when a multi-record workflow requires it, not for a single CRUD save.

## Current model

`User` owns `StudentProfile` (one-to-one), `SourceDocument`, `Notice`, `Opportunity`, `Event`, `Task` and `AuditEvent`. A Notice optionally links an immutable uploaded original and many actions. Its original pasted text is not editable after capture; title, summary, category and status are normalized fields. AuditEvent stores before/after changes to those fields. An Event has either an exact UTC-backed start or a date-only value, never both; optional end must follow start. `kind` distinguishes attendance, deadline, reporting and window. Date-only does not imply midnight. An Opportunity has a category and freely editable stage; unusual stage ordering is allowed. Tasks may lack due dates. When a notice link is removed, actions remain. All user-selected foreign keys are owner-scoped in forms and checked by model validation. Uploaded files are outside static/media serving routes and are only downloaded through an authenticated owner-scoped endpoint.

## State tables (implemented subset and planned extensions)

| Object | Current transitions | Future transitions / guard |
|---|---|---|
| Notice/document | capture → needs review → confirmed or archived; correction keeps original and records audit | received → processing/manual review → reviewable → confirmed/rejected/failed/duplicate; retries cannot create duplicate actions |
| Event/task | manual create → editable; task incomplete ↔ completed | proposed → confirmed → active/scheduled → completed/expired/cancelled; date revision cancels/replaces pending reminders |
| Opportunity | announced ↔ any selected stage; non-linear by intent | stage history and provenance for every correction; rejection/withdrawal do not erase prior history |
| Reminder | not implemented | pending → due → processing → attempted → succeeded or failed/retry/cancelled; provider handoff is not user receipt |
| Revision | normalized notice edit → audit entry | newly observed → compared → conflict/compatible → explicit keep/replace/merge decision; recency alone never supersedes |

Future entities: SourceConnection (opt-in provider and revocation policy), Evidence/ExtractedFact (verbatim span, inference flag and provenance), ExtractionRun (schema, errors, retry identity), Reminder and NotificationDelivery (persistent idempotency key and attempt history), Revision (cross-notice comparison). No user-facing claim should rely on them until implemented and verified.

Limitations: ORM direct writes and superuser edits can bypass `clean`; no database-level composite owner foreign key; no duplicate fingerprint, event revision history or persistent reminder yet. Admin access is trusted privileged operation. Uploaded document bytes are not extracted or malware-scanned; keep this deployment private/local until hardened.
