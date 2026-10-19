#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>

// ====== SUA CAC DONG NAY ======
const char* ssid      = "TEN_WIFI";                  // wifi 2.4GHz
const char* pass      = "MAT_KHAU_WIFI";
const char* server    = "https://TEN-APP.onrender.com";   // link Render cua ban (khong co dau / cuoi)
const char* deviceKey = "doi-key-esp32";             // trung DEVICE_KEY trong server.py
// ==============================

#define SS_PIN   5
#define RST_PIN  4

MFRC522 rfid(SS_PIN, RST_PIN);
LiquidCrystal_I2C *lcd = nullptr;   // tu tim dia chi 0x27 / 0x3F

const byte ROWS = 4, COLS = 4;
char keys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[ROWS] = {13, 14, 27, 26};
byte colPins[COLS] = {25, 33, 32, 17};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// ---- Trang thai menu ----
enum State {
  ST_HOME,        // Welcome toi SuhachBank (bam * de vao menu)
  ST_MENU,        // 1.Nap tien  2.Kiem tra so du
  ST_TOPUP_SCAN,  // cho quet the de nap tien
  ST_TOPUP_URL,   // dang hien URL nap tien (bam 7 = xem ma the)
  ST_TOPUP_CODE,  // dang hien ma the (bam 7 = quay lai URL)
  ST_BAL_SCAN     // cho quet the de xem so du
};
State state = ST_HOME;
unsigned long stateStart = 0;   // thoi diem vao trang thai hien tai
String topupUid = "";           // ma the (UID) dang nap tien
unsigned long lastWifiTry = 0;

const unsigned long MENU_TIMEOUT = 20000;   // menu / cho quet the: 20 giay
const unsigned long URL_TIMEOUT  = 60000;   // man hinh URL / ma the: 60 giay

// ---------- Tien ich ----------
bool i2cExists(byte addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

void show(const String &a, const String &b) {
  lcd->clear();
  lcd->setCursor(0, 0); lcd->print(a.substring(0, 16));
  lcd->setCursor(0, 1); lcd->print(b.substring(0, 16));
}

// 1500000 -> "1.500.000"
String fmtMoney(long v) {
  String s = String(v < 0 ? -v : v);
  String out = "";
  int c = 0;
  for (int i = s.length() - 1; i >= 0; i--) {
    out = String(s[i]) + out;
    if (++c % 3 == 0 && i > 0) out = "." + out;
  }
  return (v < 0 ? "-" : "") + out;
}

void setState(State st) {
  state = st;
  stateStart = millis();
  switch (st) {
    case ST_HOME:       show("Welcome toi", "SuhachBank"); break;
    case ST_MENU:       show("1.Nap tien", "2.Kiem tra so du"); break;
    case ST_TOPUP_SCAN: show("Nap tien", "Quet the..."); break;
    case ST_BAL_SCAN:   show("Kiem tra so du", "Quet the..."); break;
    case ST_TOPUP_URL: {
      // URL trang nap tien (bo "http://"), LCD 16 ky tu nen tach 2 dong neu dai
      String addr = String(server);
      addr.replace("https://", ""); addr.replace("http://", "");
      // URL dai hon 16 ky tu thi dong 1 tu chay chu (xem loop)
      show(addr.substring(0, 16), "Bam 7 xem ma the");
      break;
    }
    case ST_TOPUP_CODE: show("Ma the can nap:", topupUid); break;
  }
}

// ---------- Goi server ----------
String post(const String &path, const String &body, int &code) {
  if (WiFi.status() != WL_CONNECTED) {
    code = -1;
    return "";
  }
  HTTPClient http;
  WiFiClientSecure sclient;
  WiFiClient pclient;
  http.setConnectTimeout(10000);
  http.setTimeout(35000);          // Render goi free "ngu" sau 15 phut, lan dau goi mat ~30-50 giay
  bool ok;
  if (String(server).startsWith("https://")) {
    sclient.setInsecure();         // khong kiem tra chung chi (du cho do an nho)
    ok = http.begin(sclient, String(server) + path);
  } else {
    ok = http.begin(pclient, String(server) + path);
  }
  if (!ok) {
    code = -1;
    return "";
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", deviceKey);
  code = http.POST(body);
  String res = (code > 0) ? http.getString() : "";
  if (code <= 0) {
    Serial.printf("HTTP loi %d: %s (URL: %s%s)\n", code, HTTPClient::errorToString(code).c_str(),
                  server, path.c_str());
  }
  http.end();
  return res;
}

String compact(String s) {
  s.replace(" ", "");
  return s;
}

long getBalance(const String &res) {
  String r = compact(res);
  int i = r.indexOf("\"balance\":");
  if (i < 0) return -1;
  return r.substring(i + 10).toInt();
}

// Lay gia tri chuoi trong JSON, vd {"lcd_type":"Vang"} -> "Vang"
String jsonStr(const String &res, const char *key) {
  String pat = String("\"") + key + "\"";
  int i = res.indexOf(pat);
  if (i < 0) return "";
  i += pat.length();
  while (i < (int)res.length() && (res[i] == ':' || res[i] == ' ')) i++;
  if (i >= (int)res.length() || res[i] != '"') return "";
  i++;
  int j = res.indexOf('"', i);
  if (j < 0) return "";
  return res.substring(i, j);
}

bool isRegistered(const String &res) {
  return compact(res).indexOf("\"registered\":true") >= 0;
}

void showNetError(int code) {
  if (code == 401) {
    show("Sai device key", "");
  } else if (code <= 0) {
    if (WiFi.status() != WL_CONNECTED) {
      show("Mat WiFi", "Kiem tra ssid/pass");
    } else {
      String addr = String(server);
      addr.replace("https://", ""); addr.replace("http://", "");
      show("Khong toi server", addr);   // dung IP:port cua may tinh chua?
    }
  } else {
    show("Loi server", String(code));
  }
}

// ---------- Setup ----------
void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  byte addr = 0x27;
  if (!i2cExists(0x27) && i2cExists(0x3F)) addr = 0x3F;
  lcd = new LiquidCrystal_I2C(addr, 16, 2);
  lcd->init();
  lcd->backlight();

  SPI.begin();
  rfid.PCD_Init();
  byte ver = rfid.PCD_ReadRegister(MFRC522::VersionReg);
  Serial.printf("RC522 version: 0x%02X\n", ver);
  if (ver == 0x00 || ver == 0xFF) {
    // chi canh bao, van chay tiep (mot so module clone tra gia tri la nhung van doc duoc the)
    Serial.println("CANH BAO: RC522 tra ve version la, thu quet the xem co doc duoc khong");
    show("Canh bao RC522", "Thu quet the...");
    delay(2000);
  }

  show("Dang ket noi", "wifi...");
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(ssid, pass);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) delay(300);

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("ESP32 IP: " + WiFi.localIP().toString());
    Serial.println(String("Server: ") + server);
    show("WiFi OK", WiFi.localIP().toString());
  } else {
    show("Khong co WiFi", "Se thu lai...");
  }
  delay(1500);
  setState(ST_HOME);
}

// ---------- Loop ----------
void loop() {
  // tu noi lai wifi neu mat
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiTry > 10000) {
    lastWifiTry = millis();
    WiFi.reconnect();
  }

  // ---- ban phim ----
  char k = keypad.getKey();
  if (k) {
    if (k == 'D' || k == '#') {
      // huy / ve man hinh chinh
      if (state != ST_HOME) setState(ST_HOME);
    } else {
      switch (state) {
        case ST_HOME:
          if (k == '*') setState(ST_MENU);            // * = vao menu
          break;
        case ST_MENU:
          if (k == '1') setState(ST_TOPUP_SCAN);      // 1 = nap tien
          else if (k == '2') setState(ST_BAL_SCAN);   // 2 = kiem tra so du
          break;
        case ST_TOPUP_URL:
          if (k == '7') setState(ST_TOPUP_CODE);      // 7 = hien ma the
          break;
        case ST_TOPUP_CODE:
          if (k == '7') setState(ST_TOPUP_URL);       // 7 lan nua = ve URL
          break;
        default:
          break;
      }
    }
  }

  // ---- chay chu URL tren dong 1 neu dai hon 16 ky tu ----
  if (state == ST_TOPUP_URL) {
    static unsigned long lastScroll = 0;
    String addr = String(server);
    addr.replace("https://", ""); addr.replace("http://", "");
    if (addr.length() > 16 && millis() - lastScroll > 450) {
      lastScroll = millis();
      String pad = addr + "   ";
      int off = ((millis() - stateStart) / 450) % pad.length();
      String win = (pad + pad).substring(off, off + 16);
      lcd->setCursor(0, 0);
      lcd->print(win);
    }
  }

  // ---- het gio thi ve man hinh chinh ----
  if (state != ST_HOME) {
    unsigned long limit = (state == ST_TOPUP_URL || state == ST_TOPUP_CODE) ? URL_TIMEOUT : MENU_TIMEOUT;
    if (millis() - stateStart > limit) {
      if (state == ST_MENU || state == ST_TOPUP_SCAN || state == ST_BAL_SCAN) {
        show("Het gio", "Da huy");
        delay(1500);
      }
      setState(ST_HOME);
    }
  }

  // ---- doc the ----
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;

  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  Serial.println("UID: " + uid);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  // chi nhan the khi dang o che do cho quet the
  if (state == ST_HOME || state == ST_MENU) {
    show("Bam * vao menu", "");
    delay(1500);
    setState(state);   // ve lai man hinh cu
    return;
  }
  if (state != ST_TOPUP_SCAN && state != ST_BAL_SCAN) return;

  int code = 0;
  show("Dang ket noi", "server...");
  String res = post("/scan", "{\"uid\":\"" + uid + "\"}", code);

  if (state == ST_TOPUP_SCAN) {
    // ---- NAP TIEN: kiem tra the roi hien URL, bam 7 de xem ma the ----
    if (code == 200 && isRegistered(res)) {
      topupUid = uid;
      setState(ST_TOPUP_URL);
    } else if (code == 200) {
      show("SuhachBank", "The chua luu");
      delay(3000);
      setState(ST_HOME);
    } else {
      showNetError(code);
      delay(3000);
      setState(ST_HOME);
    }
  } else {
    // ---- KIEM TRA SO DU: y nhu code cu ----
    if (code == 200) {
      if (isRegistered(res)) {
        String t = jsonStr(res, "lcd_type");     // loai the (da bo dau) dat o phan Luu the
        if (t.length() == 0) t = "Thuong";
        show("The " + t, "SuhachBank");          // man hinh 1: [loai the] [SuhachBank]
        delay(2000);
        show("So du hien tai:", fmtMoney(getBalance(res)) + " d");   // man hinh 2: so du
        delay(3000);
      } else {
        show("SuhachBank", "The chua luu");
        delay(3000);
      }
    } else {
      showNetError(code);
      delay(3000);
    }
    setState(ST_HOME);
  }
}
