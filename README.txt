THE TIEN RFID - SUHACHBANK
==========================

THU MUC:
  app/                       -> server + trang web + tao file TheTien.exe
  esp32/                     -> code nap vao ESP32 (mo bang VS Code + PlatformIO)

MENU TREN THIET BI (MOI)
  Man hinh cho ........... Welcome toi / SuhachBank
  Bam *  -> menu:  1.Nap tien / 2.Kiem tra so du
  Phim 1 (NAP TIEN):
      quet the -> hien URL trang nap tien (vd 192.168.11.158 / :5000)
      bam 7    -> hien MA THE (UID) can nap; bam 7 lan nua de ve man hinh URL
      mo URL tren may tinh/dien thoai, go ma the vao o "Ma the" roi nap tien
  Phim 2 (KIEM TRA SO DU): y nhu cu
      quet the -> Man hinh 1 (2 giay): The <loai the> / SuhachBank
                  Man hinh 2 (3 giay): So du hien tai: / <so tien> d
      The chua luu: SuhachBank / The chua luu
  Phim D hoac # = huy, ve man hinh chinh. Qua 20 giay (menu/cho quet the)
  hoac 60 giay (man hinh URL/ma the) khong bam gi thi tu ve man hinh chinh.
  LUU Y: tru tien bang ban phim da bo (phim * gio la vao menu).
         Van tru tien duoc o tab "2. Tru tien" tren web.
  LCD khong hien duoc tieng Viet co dau -> loai the tu dong bo dau.

TRANG WEB (MOI)
  Them o "Ma the": go ma hien tren thiet bi (phim 7) de chon the can nap.
  Quet the o thiet bi thi o nay tu dien.

TRANG WEB - TAB "3. LUU THE" (MOI)
  Co 2 o: "Ten the" (vd Nguyen Van A) va "Loai the" (vd Vang, VIP, Hoc sinh).
  - The moi: quet the -> nhap ten + loai -> Luu the.
  - The DA LUU truoc day (chua co loai): quet the, nut doi thanh "Cap nhat the",
    nhap loai the -> bam Cap nhat. So du khong bi mat.
  - De trong "Loai the" thi mac dinh la "Thuong".

CACH CAP NHAT
  1) Server/web:
       - Dang dung python:  chep de app/server.py va app/static/index.html
         vao thu muc cu, chay lai python server.py
       - Dang dung exe:     vao thu muc app/, bam dup build_exe.bat de tao
         TheTien.exe moi (copy file cards.db + config.ini cu canh exe moi
         neu muon giu du lieu va mat khau). Tat TheTien.exe cu truoc.
       DB cu duoc nang cap tu dong, khong mat the va so du.
  2) ESP32 (VS Code + PlatformIO):
       - Mo thu muc esp32 trong VS Code, mo src/main.cpp
       - Sua 3 dong dau: ssid, pass, server (IP may tinh)
         (chep lai tu code cu cua ban, file nay de trong)
       - Cam ESP32, bam Upload (mui ten ->) o thanh duoi
         (neu hien Connecting... thi giu nut BOOT; dong Serial Monitor truoc khi nap)

CHAY TREN RENDER (MOI)
  1) Day thu muc thetien_suhachbank len GitHub, tren Render chon New > Blueprint
     (dung render.yaml) hoac New > Web Service: Root Directory = app,
     Build = pip install -r requirements.txt,
     Start = gunicorn server:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT
  2) Environment: ADMIN_KEY (mat khau web), DEVICE_KEY (trung deviceKey trong ESP32)
  3) QUAN TRONG - du lieu the: SQLite nam tren dia cua Render. Goi FREE khong co
     Disk -> moi lan deploy/khoi dong lai se MAT the va so du. Can goi tra phi
     + Disk mount /var/data va DB_PATH=/var/data/cards.db (da co trong render.yaml).
  4) ESP32: dong "server" = "https://ten-app.onrender.com" (khong dau / cuoi).
     Goi free "ngu" sau 15 phut khong dung, lan quet dau co the cho 30-50 giay.
