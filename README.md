# HMS — Hospital Management System

A Django-based hospital management web app with doctor availability, patient appointment booking, Google Calendar integration, and a separate serverless email notification service.

---

## Setup and Run

### Prerequisites

- Python 3.11+
- PostgreSQL (running locally)
- Node.js 18+ and npm (for serverless-offline)
- A Google Cloud project with Calendar API enabled (for calendar integration — optional for core demo)

---

### 1. Clone the repo

```bash
git clone https://github.com/sankshtriya01/Hospital-Management-System.git
cd hms-project
```

---

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:

```
DB_NAME=hms_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
EMAIL_SERVICE_URL=http://localhost:3000/dev/send-email
```

Google Calendar fields (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) are optional — the app works fully without them; calendar events are simply skipped.

For SMTP email: set `SMTP_USER` and `SMTP_PASSWORD` in the email-service `.env`. Without them, emails are logged to the serverless console (dev mode).

---

### 3. Set up the database

```bash
psql -U postgres -c "CREATE DATABASE hms_db;"
```

---

### 4. Set up the Django app

```bash
cd hms/
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r ../requirements.txt

# Load env vars (or export them manually)
export $(cat ../.env | xargs)

python manage.py migrate
python manage.py createsuperuser   # optional
```

---

### 5. Run the Django app

```bash
python manage.py runserver
```

App is live at **http://localhost:8000**

---

### 6. Run the serverless email service

Open a **second terminal**:

```bash
cd email-service/
npm install
npx serverless offline
```

Email function runs at **http://localhost:3000/dev/send-email**

You can test it directly:

```bash
curl -X POST http://localhost:3000/dev/send-email \
  -H "Content-Type: application/json" \
  -d '{"event_type":"SIGNUP_WELCOME","email":"test@example.com","name":"Alice","role":"Doctor"}'
```

---

### 6. Google Calendar Setup (optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Google Calendar API**
3. Create OAuth 2.0 credentials (Web Application)
4. Add authorized redirect URI: `http://localhost:8000/accounts/oauth2callback/`
5. Copy Client ID and Secret into `.env`
6. After login, click **"Connect Google Calendar"** in the nav bar

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser (User)                   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────┐
│              Django Application (port 8000)          │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  accounts/  │  │appointments/ │  │notifications│  │
│  │  - User     │  │  - Slot      │  │  - service  │  │
│  │  - Doctor   │  │  - Booking   │  │    .py      │  │
│  │    Profile  │  │  - Calendar  │  └──────┬─────┘  │
│  │  - Patient  │  │    service   │         │        │
│  │    Profile  │  └──────────────┘         │ HTTP   │
│  └─────────────┘                           │ POST   │
│                                            │        │
└────────────────────────────────────────────┼────────┘
                                             │
┌────────────────────────────────────────────▼────────┐
│         Serverless Email Service (port 3000)         │
│         serverless-offline / AWS Lambda              │
│                                                      │
│  POST /dev/send-email                                │
│  ├── SIGNUP_WELCOME → welcome email                  │
│  └── BOOKING_CONFIRMATION → confirmation email       │
│                                                      │
│  Gmail SMTP (or any SMTP provider)                   │
└─────────────────────────────────────────────────────┘

                    ┌──────────────────────┐
                    │  Google Calendar API │
                    │  (per-user OAuth2)   │
                    └──────────────────────┘
```

### Data Model

**`User`** (extends `AbstractUser`)
- `role`: `doctor` | `patient`
- `google_access_token`, `google_refresh_token`, `google_token_expiry` — stored per user for Calendar API

**`DoctorProfile`** — 1:1 with User (role=doctor), stores specialization

**`PatientProfile`** — 1:1 with User (role=patient)

**`AvailabilitySlot`**
- `doctor` (FK to User)
- `date`, `start_time`, `end_time`
- `is_booked` (bool, flipped atomically on booking)
- Unique constraint: `(doctor, date, start_time)` — prevents duplicate slots

**`Booking`**
- `slot` (OneToOne to AvailabilitySlot)
- `patient` (FK to User)
- `status`: confirmed | cancelled
- `doctor_calendar_event_id`, `patient_calendar_event_id`

### Role-Based Access

Role is stored on the `User` model as a `role` field set at signup. Two decorator helpers enforce it at the view level:

- `@doctor_required` — redirects non-doctors with a 403-equivalent message
- `@patient_required` — same for non-patients

The decorators wrap `@login_required`, so unauthenticated users hit the login page first.

Doctors can only query `AvailabilitySlot` filtered by `doctor=request.user` — they cannot see or modify other doctors' data even by manipulating URL parameters (the queryset filter enforces it).

### Google Calendar Integration

OAuth2 tokens are stored directly on the `User` model (see Design Decision below). When a booking is confirmed, `calendar_service.create_calendar_event()` is called for both doctor and patient. It builds a `Credentials` object from stored tokens, refreshes if expired, and calls the Calendar API. Failures are caught and logged — they do not roll back the booking.

### Serverless Email Service

The Django app sends a fire-and-forget HTTP POST to `http://localhost:3000/dev/send-email`. The serverless function owns all SMTP logic. The two endpoints are:

| `event_type` | Trigger | Required fields |
|---|---|---|
| `SIGNUP_WELCOME` | User signs up | `email`, `name`, `role` |
| `BOOKING_CONFIRMATION` | Booking confirmed | `patient_email`, `patient_name`, `doctor_name`, `date`, `start_time`, `end_time` |

If `SMTP_USER`/`SMTP_PASSWORD` are not set, emails are printed to the console (dev mode) so the integration is demonstrable without real SMTP credentials.

---

## The Design Decision

### Problem: How to handle the race condition in slot booking

When two patients simultaneously view the same available slot and both click "Book", the naive implementation would create two `Booking` records for the same slot — a double-booking.

Two reasonable approaches exist:

**Option A: Optimistic locking**
Add a `version` integer field to `AvailabilitySlot`. Before saving, check that the version in the DB still matches the version read at the start of the request. If they differ, abort and retry. This is non-blocking — concurrent requests don't wait for each other.

**Option B: Pessimistic locking with `SELECT FOR UPDATE`**
Wrap the critical section in a `transaction.atomic()` block and use `select_for_update()` to acquire a row-level lock. The second concurrent request blocks at the lock until the first transaction commits. It then reads `is_booked=True` and aborts cleanly.

**I chose Option B — `SELECT FOR UPDATE` inside `transaction.atomic()`.**

Here's why:

Optimistic locking works well when conflicts are rare and retries are cheap — a good fit for high-throughput systems where holding a lock would be a bottleneck. But slot booking is not high-throughput: a given slot can only have two concurrent claimants at most, and the window is milliseconds. In that situation, optimistic locking's retry logic adds complexity with no meaningful latency benefit.

More importantly, optimistic locking shifts the burden of conflict resolution to the application — I need to implement retry logic, decide how many retries, and handle the case where retries all fail. That's extra code that can be wrong. `SELECT FOR UPDATE` delegates the serialization guarantee to PostgreSQL, which handles it correctly by definition. The transaction is short (one read + one update), so the lock is held for microseconds.

The result is simpler, correct code: one `select_for_update()` call, one `is_booked` check, one `save()`, all inside `transaction.atomic()`. The second concurrent request either waits and gets `is_booked=True` (and sees the clean "already booked" message), or — if the DB is down — fails with a DB error rather than a silent double-booking.

I also added a `unique_together` constraint on `(doctor, date, start_time)` as a database-level safety net against any logic bug that slips past the lock. Defense in depth.

---

## Limitations

**What would break in production:**

1. **Google token storage on the User model** — Access tokens in a DB column are fine for a prototype, but in production they should be encrypted at rest or stored in a dedicated secrets store. A DB dump would expose them.

2. **Synchronous email trigger** — The Django view calls the serverless function synchronously and waits up to 5 seconds. If the email service is slow, the user's request is slow too. In production, this should be a background task (Celery, Django-Q) or a message queue (SQS, Redis Streams).

3. **No slot cancellation** — Bookings cannot be cancelled. A production system needs cancellation with slot re-opening, calendar event deletion, and notification emails.

4. **Single timezone (UTC)** — All slots are stored and displayed in UTC. A real system needs per-user timezones.

5. **No pagination** — Doctor slot lists and booking lists are unbounded queries. With thousands of slots, these pages would be slow.

6. **Secret key in settings** — `SECRET_KEY` should be loaded from environment, not hardcoded (the `.env.example` handles this, but the default fallback is insecure).

**I would fix #2 first** — the synchronous email call is a latency and reliability risk that directly degrades user experience and could cause request timeouts under any real load.
