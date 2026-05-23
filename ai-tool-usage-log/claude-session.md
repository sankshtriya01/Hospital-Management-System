# AI Tool Usage Log

## Tool: Claude (Anthropic) — claude.ai

**Date:** 2025

**Task:** Build HMS (Hospital Management System) shortlisting task

---

### Session Summary

Used Claude to:
1. Plan overall project architecture (Django + PostgreSQL + serverless email + Google Calendar)
2. Generate initial models for `User`, `AvailabilitySlot`, `Booking`
3. Discuss race condition handling approaches — chose `select_for_update` over optimistic locking
4. Generate Django views, forms, URL routing
5. Generate HTML templates with inline CSS
6. Draft README sections including the design decision section
7. Review Google Calendar OAuth2 token storage approach

### Key prompts used

- "What's the best way to handle race conditions in Django slot booking — optimistic locking or select_for_update?"
- "Generate a custom User model with doctor/patient roles and Google OAuth token fields"
- "How should the Django app call the serverless function — direct HTTP or message queue?"
- "Write the serverless handler that supports SIGNUP_WELCOME and BOOKING_CONFIRMATION events"

### What I verified / modified

- Reviewed all generated code line by line
- Modified the `book_slot` view to keep side effects (calendar, email) outside the DB transaction
- Adjusted template styling to match desired look
- Verified the `select_for_update` pattern is correct for PostgreSQL
- Confirmed `unique_together` constraint on `AvailabilitySlot` as an extra safety net

---

All code was reviewed and understood before inclusion. I can defend every line.
