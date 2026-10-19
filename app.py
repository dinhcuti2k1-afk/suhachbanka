# Ung dung desktop THE TIEN: co server rieng ben trong + cua so dieu khieu
import os, sys, threading, webbrowser
import tkinter as tk
from tkinter import messagebox
from werkzeug.serving import make_server
import server


class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.srv = make_server("0.0.0.0", server.PORT, server.app, threaded=True)

    def run(self):
        self.srv.serve_forever()

    def stop(self):
        self.srv.shutdown()


def main():
    root = tk.Tk()
    root.title("The Tien RFID")
    root.geometry("460x420")
    root.resizable(False, False)

    try:
        th = ServerThread()
    except OSError:
        messagebox.showerror(
            "Khong chay duoc",
            "Cong %d dang bi chuong trinh khac dung.\n"
            "Hay tat server cu (python server.py hoac ban TheTien khac) roi mo lai." % server.PORT)
        return
    th.start()

    ip = server.lan_ip()
    web_local = "http://localhost:%d" % server.PORT
    web_esp = "http://%s:%d" % (ip, server.PORT)

    pad = {"padx": 16, "anchor": "w"}
    tk.Label(root, text="THE TIEN RFID", font=("Segoe UI", 16, "bold")).pack(pady=(14, 0), **pad)
    tk.Label(root, text="Server dang chay. Dong cua so nay = tat server.",
             fg="#16a34a", font=("Segoe UI", 10, "bold")).pack(pady=(0, 10), **pad)

    def row(title, value):
        tk.Label(root, text=title, font=("Segoe UI", 9)).pack(pady=(6, 0), **pad)
        e = tk.Entry(root, font=("Consolas", 11), width=44)
        e.insert(0, value)
        e.configure(state="readonly")
        e.pack(padx=16, anchor="w")

    row("Mo web tren may nay:", web_local)
    row("Dien vao code ESP32 (dong server):", web_esp)
    row("Mat khau web (admin_key):", server.ADMIN_KEY)
    row("deviceKey trong code ESP32 phai la:", server.DEVICE_KEY)

    tk.Label(root, text="Doi mat khau: sua file config.ini canh app roi mo lai.",
             fg="#555", font=("Segoe UI", 9)).pack(pady=(10, 0), **pad)

    bar = tk.Frame(root)
    bar.pack(pady=14)
    tk.Button(bar, text="Mo web", width=12, command=lambda: webbrowser.open(web_local)).pack(side="left", padx=4)
    tk.Button(bar, text="Thu muc du lieu", width=14, command=lambda: os.startfile(server.BASE_DIR)).pack(side="left", padx=4)
    tk.Button(bar, text="Thoat", width=10, command=root.destroy).pack(side="left", padx=4)

    root.after(1200, lambda: webbrowser.open(web_local))   # tu mo web luc khoi dong

    def on_close():
        try:
            th.stop()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
