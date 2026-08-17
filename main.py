import os
import sqlite3
from datetime import datetime, date
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

DB_PATH = os.environ.get("DB_PATH", "attendance.db")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "change-me")  # set this in Render env vars

app = FastAPI(title="Office Attendance")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                att_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('present','absent')),
                marked_at TEXT NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                UNIQUE(employee_id, att_date)
            )
        """)


init_db()


# ---------- Schemas ----------

class MarkRequest(BaseModel):
    employee_id: int
    status: str  # "present" or "absent"


class EmployeeRequest(BaseModel):
    name: str


# ---------- Employee endpoints ----------

@app.get("/api/employees")
def list_employees():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name FROM employees WHERE active = 1 ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/admin/employees")
def add_employee(req: EmployeeRequest, x_admin_key: Optional[str] = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    with get_db() as conn:
        try:
            conn.execute("INSERT INTO employees (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Employee already exists")
    return {"ok": True}


@app.delete("/api/admin/employees/{employee_id}")
def remove_employee(employee_id: int, x_admin_key: Optional[str] = Header(None)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    with get_db() as conn:
        conn.execute("UPDATE employees SET active = 0 WHERE id = ?", (employee_id,))
    return {"ok": True}


# ---------- Attendance endpoints ----------

@app.post("/api/mark")
def mark_attendance(req: MarkRequest):
    if req.status not in ("present", "absent"):
        raise HTTPException(status_code=400, detail="status must be 'present' or 'absent'")
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    with get_db() as conn:
        emp = conn.execute(
            "SELECT id FROM employees WHERE id = ? AND active = 1", (req.employee_id,)
        ).fetchone()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")
        conn.execute("""
            INSERT INTO attendance (employee_id, att_date, status, marked_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(employee_id, att_date)
            DO UPDATE SET status = excluded.status, marked_at = excluded.marked_at
        """, (req.employee_id, today, req.status, now))
    return {"ok": True, "date": today, "status": req.status}


@app.get("/api/today")
def today_status():
    today = date.today().isoformat()
    with get_db() as conn:
        rows = conn.execute("""
            SELECT e.id as employee_id, e.name, a.status, a.marked_at
            FROM employees e
            LEFT JOIN attendance a ON a.employee_id = e.id AND a.att_date = ?
            WHERE e.active = 1
            ORDER BY e.name
        """, (today,)).fetchall()
        return {"date": today, "records": [dict(r) for r in rows]}


@app.get("/api/calendar")
def calendar_month(year: int, month: int):
    """Returns attendance grouped by date for a given month (1-12)."""
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year+1:04d}-01-01"
    else:
        end = f"{year:04d}-{month+1:02d}-01"
    with get_db() as conn:
        rows = conn.execute("""
            SELECT a.att_date, e.name, a.status
            FROM attendance a
            JOIN employees e ON e.id = a.employee_id
            WHERE a.att_date >= ? AND a.att_date < ?
            ORDER BY a.att_date, e.name
        """, (start, end)).fetchall()
    result = {}
    for r in rows:
        result.setdefault(r["att_date"], []).append(
            {"name": r["name"], "status": r["status"]}
        )
    return result


@app.get("/api/day")
def day_detail(day: str):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT e.name, a.status, a.marked_at
            FROM employees e
            LEFT JOIN attendance a ON a.employee_id = e.id AND a.att_date = ?
            WHERE e.active = 1
            ORDER BY e.name
        """, (day,)).fetchall()
        return {"date": day, "records": [dict(r) for r in rows]}


# ---------- Serve frontend ----------

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
