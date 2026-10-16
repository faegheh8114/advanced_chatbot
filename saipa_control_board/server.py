# -*- coding: utf-8 -*-
"""
Saipa Mashayekh - shared server for the repair-hall control board.

Run it on ONE computer in the dealership (start_server.bat). Every other
computer or the hall monitor opens  http://<this-computer-ip>:8080  in a
browser and all of them see the same, live data.

* Only the Python standard library is used (no pip install needed).
* Data is kept in data/board.json (atomic writes, daily backups in
  data/backups, every change logged in data/changes.log).
* Changes are sent as small operations (finish task, add parts, ...) and
  applied on the server one at a time, so two people working at the same
  moment never overwrite each other's work.
"""
import json
import os
import shutil
import socket
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
DATA_FILE = os.path.join(DATA_DIR, "board.json")
LOG_FILE = os.path.join(DATA_DIR, "changes.log")
BOARD_FILE = os.path.join(BASE_DIR, "board.html")
KEEP_BACKUPS = 60
MAX_BODY = 20 * 1024 * 1024

LOCK = threading.Lock()
STATE = {"version": 0, "data": {"workers": [], "cars": []}}


class OpError(Exception):
    """Error shown to the user (Persian text)."""


# ---------------------------------------------------------------- storage
def load_state():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        STATE["version"] = int(saved.get("version", 0))
        STATE["data"] = normalize(saved.get("data", {}))


def save_state():
    daily_backup()
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(STATE, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, DATA_FILE)


def daily_backup():
    if not os.path.exists(DATA_FILE):
        return
    target = os.path.join(BACKUP_DIR, "board_%s.json" % datetime.now().strftime("%Y%m%d"))
    if not os.path.exists(target):
        shutil.copy2(DATA_FILE, target)
        backups = sorted(n for n in os.listdir(BACKUP_DIR) if n.startswith("board_") and n.endswith(".json"))
        for old in backups[:-KEEP_BACKUPS]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
            except OSError:
                pass


def log_change(ip, op, payload):
    line = json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "ip": ip, "op": op, "payload": payload},
                      ensure_ascii=False)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ------------------------------------------------------------- data model
def text(v, limit=500):
    return str(v if v is not None else "").strip()[:limit]


def normalize(data):
    """Accepts data exported from the old single-PC version (v8..v21)."""
    workers = []
    for w in data.get("workers", []) or []:
        w = text(w, 100)
        if w and w not in workers:
            workers.append(w)
    cars = []
    for c in data.get("cars", []) or []:
        if not isinstance(c, dict):
            continue
        tasks = []
        for t in c.get("tasks", []) or []:
            if not isinstance(t, dict):
                continue
            status = t.get("status") if t.get("status") in ("working", "shortage", "done") else "working"
            tasks.append({
                "id": text(t.get("id"), 60) or new_id(),
                "repair": text(t.get("repair")),
                "worker": text(t.get("worker"), 100),
                "status": status,
                "parts": clean_parts(t.get("parts")),
                "finished": text(t.get("finished"), 60),
            })
        cars.append({
            "id": text(c.get("id"), 60) or new_id(),
            "admission": text(c.get("admission"), 50),
            "plate": text(c.get("plate"), 50),
            "car": text(c.get("car"), 100),
            "date": text(c.get("date"), 20),
            "time": text(c.get("time"), 10),
            "tasks": tasks,
        })
    return {"workers": workers, "cars": cars}


def clean_parts(parts):
    out = []
    for p in parts or []:
        if not isinstance(p, dict):
            continue
        name = text(p.get("name"), 200)
        try:
            qty = int(float(p.get("qty", 1)))
        except (TypeError, ValueError):
            qty = 1
        if name and qty > 0:
            out.append({"name": name, "qty": qty})
    return out


def new_id():
    return str(int(time.time() * 1000)) + uuid.uuid4().hex[:5]


def find_car(data, car_id):
    for c in data["cars"]:
        if c["id"] == car_id:
            return c
    raise OpError("این پذیرش پیدا نشد؛ احتمالاً در سیستم دیگری حذف یا تغییر کرده است.")


def find_task(data, car_id, task_id):
    car = find_car(data, car_id)
    for t in car["tasks"]:
        if t["id"] == task_id:
            return t
    raise OpError("این ردیف تعمیر پیدا نشد؛ احتمالاً در سیستم دیگری تغییر کرده است.")


# ------------------------------------------------------------- operations
def op_save_admission(data, p):
    admission, plate = text(p.get("admission"), 50), text(p.get("plate"), 50)
    if not admission or not plate:
        raise OpError("شماره پذیرش و پلاک را وارد کنید.")
    car_id = p.get("id") or None
    if any(c["admission"] == admission and c["id"] != car_id for c in data["cars"]):
        raise OpError("این شماره پذیرش قبلاً ثبت شده است.")
    items = p.get("items") or []
    if not items or any(not text(i.get("repair")) or not text(i.get("worker")) for i in items):
        raise OpError("برای هر ردیف، شرح ایراد و نام تعمیرکار را انتخاب کنید.")
    if car_id:
        car = find_car(data, car_id)
    else:
        car = {"id": new_id(), "tasks": []}
        data["cars"].append(car)
    car.update({"admission": admission, "plate": plate, "car": text(p.get("car"), 100),
                "date": text(p.get("date"), 20), "time": text(p.get("time"), 10)})
    old = {t["id"]: t for t in car["tasks"]}
    tasks = []
    for i in items:
        repair, worker = text(i.get("repair")), text(i.get("worker"), 100)
        prev = old.get(i.get("id") or "")
        if prev and prev["repair"] == repair and prev["worker"] == worker:
            tasks.append(prev)  # keep its live status (maybe finished on another PC)
        else:
            tasks.append({"id": new_id(), "repair": repair, "worker": worker, "status": "working",
                          "parts": [], "finished": ""})
    car["tasks"] = tasks
    return {"id": car["id"]}


def op_delete_admission(data, p):
    car = find_car(data, p.get("carId"))
    data["cars"].remove(car)


def op_finish_task(data, p):
    t = find_task(data, p.get("carId"), p.get("taskId"))
    t["status"] = "done"
    t["finished"] = text(p.get("finished"), 60) or datetime.now().strftime("%Y-%m-%d %H:%M")


def op_set_parts(data, p):
    t = find_task(data, p.get("carId"), p.get("taskId"))
    parts = clean_parts(p.get("parts"))
    if not parts:
        raise OpError("نام و تعداد حداقل یک قطعه را وارد کنید.")
    t["parts"], t["status"], t["finished"] = parts, "shortage", ""


def op_resolve_shortage(data, p):
    t = find_task(data, p.get("carId"), p.get("taskId"))
    t["status"], t["parts"] = "working", []


def op_reopen_task(data, p):
    t = find_task(data, p.get("carId"), p.get("taskId"))
    t["status"], t["finished"] = "working", ""


def op_add_worker(data, p):
    w = text(p.get("name"), 100)
    if w and w not in data["workers"]:
        data["workers"].append(w)


def op_remove_worker(data, p):
    w = text(p.get("name"), 100)
    if w in data["workers"]:
        data["workers"].remove(w)


def op_import(data, p):
    """Bring in data from an old single-PC board (merge, nothing is lost)."""
    incoming = normalize(p.get("data") or {})
    skip_samples = bool(p.get("skipSamples", True))
    added = 0
    for w in incoming["workers"]:
        if w not in data["workers"]:
            data["workers"].append(w)
    existing = {c["id"] for c in data["cars"]}
    for c in incoming["cars"]:
        if skip_samples and c["id"] in ("sample1", "sample2"):
            continue
        if c["id"] in existing:
            continue
        data["cars"].append(c)
        existing.add(c["id"])
        added += 1
    return {"added": added}


OPS = {
    "saveAdmission": op_save_admission,
    "deleteAdmission": op_delete_admission,
    "finishTask": op_finish_task,
    "setParts": op_set_parts,
    "resolveShortage": op_resolve_shortage,
    "reopenTask": op_reopen_task,
    "addWorker": op_add_worker,
    "removeWorker": op_remove_worker,
    "import": op_import,
}


def apply_op(op, payload, ip):
    fn = OPS.get(op)
    if not fn:
        raise OpError("عملیات نامعتبر: %s" % op)
    with LOCK:
        work = json.loads(json.dumps(STATE["data"]))  # change a copy; commit only on success
        result = fn(work, payload or {}) or {}
        STATE["data"] = work
        STATE["version"] += 1
        save_state()
        log_change(ip, op, payload)
        return result, STATE["version"], STATE["data"]


# ------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "SaipaBoard/22"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def cors(self):
        # Lets the migration page (opened as a local file on the old PC) send its data.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/board.html"):
            with open(BOARD_FILE, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/state":
            with LOCK:
                self.send_json({"ok": True, "version": STATE["version"], "data": STATE["data"]})
        elif path == "/api/version":
            self.send_json({"ok": True, "version": STATE["version"]})
        elif path == "/api/export":
            with LOCK:
                body = json.dumps(STATE["data"], ensure_ascii=False, indent=1).encode("utf-8")
            name = "mashayekh_board_backup_%s.json" % datetime.now().strftime("%Y%m%d_%H%M")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % name)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/op":
            self.send_json({"ok": False, "error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                raise OpError("درخواست نامعتبر است.")
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            result, version, data = apply_op(req.get("op"), req.get("payload"), self.client_address[0])
            self.send_json({"ok": True, "result": result, "version": version, "data": data})
        except OpError as e:
            with LOCK:
                self.send_json({"ok": False, "error": str(e), "version": STATE["version"], "data": STATE["data"]})
        except Exception as e:  # never crash the server
            self.send_json({"ok": False, "error": "خطای سرور: %s" % e}, 500)


def local_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    load_state()
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    httpd.daemon_threads = True
    print("=" * 60)
    print(" Saipa Mashayekh control board server is running")
    print(" On this computer :  http://localhost:%d" % port)
    for ip in local_ips():
        print(" Other computers  :  http://%s:%d" % (ip, port))
    print(" Data file        :  %s" % DATA_FILE)
    print(" Keep this window open (close it = stop the server).")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
