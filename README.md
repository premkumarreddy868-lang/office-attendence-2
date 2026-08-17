# Office Attendance App

FastAPI + SQLite. Shared link, pick-your-name marking, shared calendar view.

## What it does
- One link for everyone. Open it, pick your name from the dropdown, tap Present or Absent.
- Marking is per day — tapping again just overwrites today's entry, doesn't create duplicates.
- Calendar shows every employee's status for every day, with color dots (green = present, red = absent). Click a day to see the full list.
- Adding/removing employees requires an admin key — not exposed in the UI, only via API (see below), so random visitors can't add fake employees.

## Known limitation (by design, per your choice)
Anyone with the link can mark attendance for anyone else — there's no login tying a person to their own name. If this becomes a problem (people marking colleagues present who aren't there), the fix is per-employee links or a PIN, which means redoing the auth layer. Flagging it again so it's on record.

## Run locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
Open http://localhost:8000

## Add employees (do this before sharing the link)
```bash
curl -X POST http://localhost:8000/api/admin/employees \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: change-me" \
  -d '{"name":"Employee Name"}'
```
Change `change-me` to whatever you set `ADMIN_KEY` to in your environment. Don't leave it as the default in production.

## Deploy to Render
1. Push this folder to a GitHub repo.
2. In Render: New → Web Service → connect the repo. It will pick up `render.yaml` automatically.
3. Set the `ADMIN_KEY` environment variable to a real secret (Render will prompt for it since it's marked `sync: false`).
4. Deploy. Render gives you a public URL — that's the link you share with the office.

### Important: free tier disk
Render's free web service plan has **ephemeral disk by default** — if you don't attach a persistent disk, your SQLite file gets wiped on every redeploy or restart, and you lose all attendance history. `render.yaml` here already requests a 1GB persistent disk mounted at `/opt/render/project/src/data`, with `DB_PATH` pointing into it. Confirm in the Render dashboard that the disk actually attached — free tier disk availability has changed before, so don't assume it's automatic.

If Render's free tier won't give you a persistent disk, your options are:
- Pay for the disk add-on, or
- Switch to a hosted Postgres (Render gives a free Postgres instance) instead of SQLite — more setup, but survives restarts without a disk.

## API reference
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/employees` | List active employees (for the dropdown) |
| POST | `/api/mark` | `{employee_id, status}` — mark today |
| GET | `/api/today` | Everyone's status for today |
| GET | `/api/calendar?year=&month=` | Full month, grouped by date |
| GET | `/api/day?day=YYYY-MM-DD` | Full detail for one day |
| POST | `/api/admin/employees` | Add employee (needs `X-Admin-Key` header) |
| DELETE | `/api/admin/employees/{id}` | Deactivate employee (needs `X-Admin-Key` header) |
