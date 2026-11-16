# Product and feature map

Campus Radar helps one student turn a fragmented announcement into source-backed commitments. It is multi-user by design; each student's records are private. No privileged portal integration, automated action, community feed, native client or AI is in the academic release.

| Student need | Route | Input and success | Empty/error and manual check |
|---|---|---|---|
| Join and set context | `/register/`, `/settings/` | Account, institution, program, batch, IANA timezone; authenticated home | Invalid timezone is rejected; sign out and log back in |
| Capture evidence | `/capture/` | Paste source text or upload PDF/image; notice opens in review | Invalid/oversized file reports an error; upload-only item asks for manual transcription |
| Review and correct | `/inbox/`, `/inbox/<id>/edit/` | Compare original with summary, confirm or archive; history records normalized edits | Empty inbox offers capture; another student's identifier returns 404 |
| Act on notice | Notice detail → Add event/task/opportunity | Multiple independently linked actions, date-only or exact time, preparation tasks | Missing or contradictory event time rejected; foreign links rejected |
| Plan the day | `/` and `/events/`, `/tasks/` | Future commitments, incomplete tasks, source links, task completion | Empty overview directs capture; deadline visually labeled and unknown time displayed |
| Find it later | `/search/` | Deterministic text search within own records | No-match message per category; other user's content never appears |
| Admin demonstration | `/admin/` | Superuser can inspect relational data and groups | Ordinary users cannot enter admin; staff records are owner-scoped |

Manual journey: register → profile → paste synthetic notice with two KYC sessions → review original → add two separate attendance events → add ID-preparation task → confirm notice → find it via Search → see events/task on Home → log in as second student and verify isolation. No scheduling occurs before the student creates actions.
