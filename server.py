from flask import Flask, request, jsonify, send_from_directory
import sqlite3, os, sys, socket, threading, webbrowser, configparser, re, unicodedata

# ---------- Duong dan ----------
FROZEN = getattr(sys, "frozen", False)
BASE_DIR = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))   # cho cards.db, config.ini
RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)                                            # cho thu muc static
STATIC_DIR = os.path.join(RES_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR)
DB = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "cards.db")   # tren Render: /var/data/cards.db (Disk)
os.makedirs(os.path.dirname(DB), exist_ok=True)

# ---------- Cau hinh (config.ini canh file exe, tu tao lan dau) ----------
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")
_cfg = configparser.ConfigParser()
if not os.path.exists(CONFIG_FILE):
    _cfg["server"] = {
        "admin_key": "doi-mat-khau-nay",   # mat khau dang nhap tren web
        "device_key": "doi-key-esp32",     # phai trung deviceKey trong code ESP32
        "port": "5000",
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write("# DOI 2 KHOA NAY roi chay lai app. device_key phai trung deviceKey trong code ESP32\n")
        _cfg.write(f)
_cfg.read(CONFIG_FILE, encoding="utf-8")
ADMIN_KEY = _cfg.get("server", "admin_key", fallback="doi-mat-khau-nay")
DEVICE_KEY = _cfg.get("server", "device_key", fallback="doi-key-esp32")
PORT = int(os.environ.get("PORT") or _cfg.getint("server", "port", fallback=5000))
# Tren Render dung bien moi truong (uu tien hon config.ini)
ADMIN_KEY = os.environ.get("ADMIN_KEY", ADMIN_KEY)
DEVICE_KEY = os.environ.get("DEVICE_KEY", DEVICE_KEY)
ON_RENDER = bool(os.environ.get("RENDER"))

state = {"seq": 0, "uid": None}

def db():
    return sqlite3.connect(DB, timeout=10)

with db() as c:
    c.execute("CREATE TABLE IF NOT EXISTS cards(uid TEXT PRIMARY KEY, name TEXT, balance INTEGER DEFAULT 0, card_type TEXT DEFAULT '')")
    # DB cu chua co cot card_type -> them vao (giu nguyen du lieu cu)
    if "card_type" not in [r[1] for r in c.execute("PRAGMA table_info(cards)")]:
        c.execute("ALTER TABLE cards ADD COLUMN card_type TEXT DEFAULT ''")
    c.execute("""CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY, uid TEXT, amount INTEGER, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")

def is_admin():
    return request.headers.get("X-Admin-Key") == ADMIN_KEY

def is_device():
    return request.headers.get("X-Device-Key") == DEVICE_KEY

def body():
    return request.get_json(silent=True) or {}

def norm_uid(d):
    return str(d.get("uid") or "").strip().upper()

def get_card(uid):
    with db() as c:
        return c.execute("SELECT name, balance, COALESCE(card_type, '') FROM cards WHERE uid=?", (uid,)).fetchone()

def lcd_text(s, maxlen=12):
    """Bo dau tieng Viet + ky tu la, de hien duoc tren LCD 16x2."""
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^A-Za-z0-9 ._-]", "", s).strip()
    return s[:maxlen]

def card_info(uid):
    """Thong tin the tra ve cho ESP32 (LCD) va trang web."""
    card = get_card(uid) if uid else None
    return dict(uid=uid or None,
                registered=card is not None,
                name=card[0] if card else None,
                balance=card[1] if card else None,
                card_type=card[2] if card else None,
                lcd_type=lcd_text(card[2]) if card else None)

def valid_amount(d):
    try:
        a = int(d.get("amount", 0))
    except (TypeError, ValueError):
        return None
    return a if 0 < a <= 5_000_000 else None

def do_charge(d):
    uid = norm_uid(d)
    if not uid:
        return jsonify(ok=False, msg="thieu UID"), 400
    amount = valid_amount(d)
    if amount is None:
        return jsonify(ok=False, msg="so tien khong hop le"), 400
    card = get_card(uid)
    if not card:
        return jsonify(ok=False, msg="the chua duoc luu"), 404
    with db() as c:
        cur = c.execute("UPDATE cards SET balance = balance - ? WHERE uid=? AND balance >= ?",
                        (amount, uid, amount))
        if cur.rowcount == 0:
            return jsonify(ok=False, msg="khong du tien", balance=card[1]), 402
        c.execute("INSERT INTO logs(uid, amount) VALUES(?,?)", (uid, -amount))
    return jsonify(ok=True, balance=get_card(uid)[1])

@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

# ---------- ESP32 goi ----------
@app.post("/scan")
def scan():
    if not is_device(): return jsonify(ok=False, msg="sai key"), 401
    uid = norm_uid(body())
    if not uid: return jsonify(ok=False, msg="thieu UID"), 400
    state["uid"] = uid
    state["seq"] += 1
    # tra ve thong tin the de ESP32 hien len LCD: loai the + so du / chua luu
    return jsonify(ok=True, **card_info(uid))

@app.post("/device/charge")
def device_charge():
    if not is_device(): return jsonify(ok=False, msg="sai key"), 401
    return do_charge(body())

# ---------- Web goi ----------
@app.get("/api/last")
def last():
    if not is_admin(): return jsonify(ok=False, msg="sai mat khau"), 401
    uid = state["uid"]
    return jsonify(ok=True, seq=state["seq"], **card_info(uid))

@app.get("/api/card/<uid>")
def card_lookup(uid):
    """Tra cuu the theo ma the (UID) go tay tren trang nap tien."""
    if not is_admin(): return jsonify(ok=False, msg="sai mat khau"), 401
    return jsonify(ok=True, **card_info(uid.strip().upper()))

@app.post("/api/register")
def register():
    if not is_admin(): return jsonify(ok=False, msg="sai mat khau"), 401
    d = body()
    uid = norm_uid(d)
    name = (d.get("name") or "").strip()
    if not uid or not name:
        return jsonify(ok=False, msg="can UID va ten the"), 400
    card_type = (d.get("card_type") or "").strip()[:30] or "Thuong"
    if get_card(uid):
        return jsonify(ok=False, msg="the nay da luu roi"), 409
    with db() as c:
        c.execute("INSERT INTO cards(uid, name, card_type) VALUES(?,?,?)", (uid, name, card_type))
    return jsonify(ok=True)

@app.post("/api/update_card")
def update_card():
    if not is_admin(): return jsonify(ok=False, msg="sai mat khau"), 401
    d = body()
    uid = norm_uid(d)
    name = (d.get("name") or "").strip()
    card_type = (d.get("card_type") or "").strip()[:30] or "Thuong"
    if not uid or not name:
        return jsonify(ok=False, msg="can UID va ten the"), 400
    if not get_card(uid):
        return jsonify(ok=False, msg="the chua duoc luu"), 404
    with db() as c:
        c.execute("UPDATE cards SET name=?, card_type=? WHERE uid=?", (name, card_type, uid))
    return jsonify(ok=True)

@app.post("/api/topup")
def topup():
    if not is_admin(): return jsonify(ok=False, msg="sai mat khau"), 401
    d = body()
    uid = norm_uid(d)
    amount = valid_amount(d)
    if amount is None: return jsonify(ok=False, msg="so tien khong hop le"), 400
    if not uid or not get_card(uid): return jsonify(ok=False, msg="the chua duoc luu"), 404
    with db() as c:
        c.execute("UPDATE cards SET balance = balance + ? WHERE uid=?", (amount, uid))
        c.execute("INSERT INTO logs(uid, amount) VALUES(?,?)", (uid, amount))
    return jsonify(ok=True, balance=get_card(uid)[1])

@app.post("/api/charge")
def charge():
    if not is_admin(): return jsonify(ok=False, msg="sai mat khau"), 401
    return do_charge(body())

@app.get("/api/history/<uid>")
def history(uid):
    if not is_admin(): return jsonify(ok=False), 401
    with db() as c:
        # doi gio UTC cua SQLite sang gio may tinh (gio Viet Nam)
        rows = c.execute("SELECT amount, datetime(ts, 'localtime') FROM logs WHERE uid=? ORDER BY id DESC LIMIT 10",
                         (uid.upper(),)).fetchall()
    return jsonify(ok=True, rows=rows)

def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    ip = lan_ip()
    print("=" * 50)
    print(" THE TIEN RFID - SERVER DANG CHAY")
    print(" Mo web tren may nay : http://localhost:%d" % PORT)
    print(" Dien vao code ESP32 : http://%s:%d" % (ip, PORT))
    print(" DONG cua so nay = TAT server")
    print("=" * 50)
    if not ON_RENDER:
        threading.Timer(1.5, lambda: webbrowser.open("http://localhost:%d" % PORT)).start()
    app.run(host="0.0.0.0", port=PORT)
