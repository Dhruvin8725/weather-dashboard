import tkinter as tk
from tkinter import ttk, messagebox
import requests, json, os
from datetime import datetime
import matplotlib
matplotlib.use("Agg")  # needed for tkinter
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# NOTE: create config.py with API_KEY = "xxxx" (from OpenWeather)
try:
    from config import API_KEY
except ImportError:
    APIKEY = ""  #add from config flie so we dont need to add api key it is become safe

FAV_FILE = "favorites.json"


# quick rounded card for using in app
class RoundedCard(tk.Canvas):
    def __init__(self, parent, bg="#202030", pad=6, **kw):
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, **kw)
        self._bg = bg
        self._pad = pad
        self.bind("<Configure>", self._draw)

    def _draw(self, evt=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 12 or h < 12:
            return
        self.create_rectangle(self._pad, self._pad, w - self._pad, h - self._pad,fill=self._bg, outline="")


# btn for showing result
class ModernButton(tk.Canvas):
    def __init__(self, parent, text, command=None, bg="#4CAF50", fg="white",width=120, height=34, font=("Segoe UI", 10, "bold"), **kw):
        super().__init__(parent, width=width, height=height,bg=parent.cget("bg"), highlightthickness=0, **kw)
        self.text, self.cmd = text, command
        self.bg, self.fg, self.font = bg, fg, font
        self.bind("<Configure>", self._paint)
        self.bind("<Enter>", lambda e: self.config(cursor="hand2"))
        self.bind("<Leave>", lambda e: self.config(cursor=""))
        self.bind("<Button-1>", self._click)

    def _paint(self, evt=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self.create_rectangle(2, 2, w - 2, h - 2, fill=self.bg, outline="")
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fg, font=self.font)

    def _click(self, evt):
        if self.cmd: self.cmd()

#---------------------------------------------- Main app for everything-----------------------------------------
class WeatherApp:
    def __init__(self, root):
        self.root = root
        root.title("Weather App")
        root.geometry("960x680")

        # colors – started dark mode only, later added light toggle
        self.colors = {
            "bg": "#151521",
            "card": "#1F1F2B",
            "muted": "#9aa0b4",
            "text": "#E6EEF3",
            "primary": "#4CAF50",
            "accent": "#2196F3",
        }
        root.config(bg=self.colors["bg"])

        # state
        self.api_key = API_KEY
        self.current_data = None
        self.favorites = self._load_fav()

        # ui
        self._build_ui()
        self.root.bind("<Return>", lambda e: self.getWeather())

    # ---------------- API calling -----------------
    def _api_call(self, endpoint, city):
        if not self.api_key:
            raise ValueError("Missing API key (check config.py)")
        url = f"https://api.openweathermap.org/data/2.5/{endpoint}"
        params = {"q": city, "appid": self.api_key, "units": "metric"}
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        return r.json()

    def _get_current(self, city):
        return self._api_call("weather", city)

    def _get_forecast(self, city):
        return self._api_call("forecast", city)

    # ---------------- Favorites section for cities -----------------
    def _load_fav(self):
        if not os.path.exists(FAV_FILE): return []
        if os.path.exists(FAV_FILE):
            f = open(FAV_FILE)
            favs = json.load(f)
            f.close()
            return favs
        else:
            return []

    def _save_fav(self):
        try:
            with open(FAV_FILE, "w") as f: json.dump(self.favorites, f, indent=2)
        except:
            pass

    def addFav(self, city):
        city = city.strip()
        if not city: return
        try:
            self._get_current(city)  # quick check
            if city not in self.favorites:
                self.favorites.append(city)
                self._save_fav()
                self.updateFavCombo()
        except:
            messagebox.showwarning("Bad City", f"Can't add '{city}'")

    def removeFav(self, city):
        if city in self.favorites:
            self.favorites.remove(city)
            self._save_fav()
            self.updateFavCombo()

    # ---------------- UI effect -----------------
    def _build_ui(self):
        # top bar
        top = tk.Frame(self.root, bg=self.colors["bg"])
        top.pack(fill="x", padx=20, pady=(15, 10))
        tk.Label(top, text="🌤 Weather Dashboard",
                 bg=self.colors["bg"], fg=self.colors["text"],
                 font=("Segoe UI", 15, "bold")).pack(side="left")

        btns = tk.Frame(top, bg=self.colors["bg"])
        btns.pack(side="right")
        ModernButton(btns, "Settings", self.openSettings,bg="#2E2E3E", fg=self.colors["text"]).pack(side="left", padx=4)
        ModernButton(btns, "Toggle Theme", self.toggleTheme,bg="#2E2E3E", fg=self.colors["text"]).pack(side="left")

        # ---------------- main for ui---------------
        main = tk.Frame(self.root, bg=self.colors["bg"])
        main.pack(fill="both", expand=True, padx=20, pady=10)

        # left sidebar
        self.sidebar = tk.Frame(main, bg=self.colors["bg"], width=260)
        self.sidebar.pack(side="left", fill="y", padx=(0, 12))
        self._make_search_box()
        self._make_fav_panel()

        # right content
        self.content = tk.Frame(main, bg=self.colors["bg"])
        self.content.pack(side="right", fill="both", expand=True)
        self._make_weather_area()

        # status bar
        self.status = tk.Label(self.root, text="Ready", bg=self.colors["bg"],
                               fg=self.colors["muted"], anchor="w")
        self.status.pack(fill="x", side="bottom", padx=15, pady=5)

    def _make_search_box(self):
        card = RoundedCard(self.sidebar, bg=self.colors["card"])
        card.pack(fill="x", pady=(0, 15))
        card.config(height=120)

        inner = tk.Frame(card, bg=self.colors["card"])
        inner.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)

        tk.Label(inner, text="Search City", bg=self.colors["card"],fg=self.colors["muted"]).pack(anchor="w")

        f = tk.Frame(inner, bg=self.colors["card"])
        f.pack(fill="x", pady=(8, 5))

        self.cityVar = tk.StringVar()
        e = tk.Entry(f, textvariable=self.cityVar, bg="#272731", fg=self.colors["text"], insertbackground=self.colors["text"],
                     bd=0, font=("Segoe UI", 12))
        e.pack(side="left", fill="x", expand=True, ipady=5)

        ModernButton(f, "Go", self.getWeather, bg=self.colors["primary"],fg="white", width=70, height=32).pack(side="left", padx=(6, 0))

    def _make_fav_panel(self):
        card = RoundedCard(self.sidebar, bg=self.colors["card"])
        card.pack(fill="x")
        card.config(height=150)

        inner = tk.Frame(card, bg=self.colors["card"])
        inner.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)

        tk.Label(inner, text="Favorites", bg=self.colors["card"],fg=self.colors["muted"], font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.favVar = tk.StringVar()
        self.favCombo = ttk.Combobox(inner, textvariable=self.favVar, state="readonly")
        self.favCombo.pack(fill="x", pady=6)
        self.favCombo.bind("<<ComboboxSelected>>", self._fav_selected)

        f = tk.Frame(inner, bg=self.colors["card"])
        f.pack(fill="x")
        ModernButton(f, "Add", lambda: self.addFav(self.cityVar.get()), bg="#10B981", fg="white", width=80, height=30).pack(side="left")
        ModernButton(f, "Remove", lambda: self.removeFav(self.favVar.get()), bg="#B00020", fg="white", width=80, height=30).pack(side="left", padx=6)

        self.updateFavCombo()

    def _make_weather_area(self):
        # current weather
        self.weatherCard = RoundedCard(self.content, bg=self.colors["card"])
        self.weatherCard.pack(fill="x", pady=(0, 15))
        self.weatherCard.config(height=160)

        inner = tk.Frame(self.weatherCard, bg=self.colors["card"])
        inner.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)

        self.weatherIcon = tk.Label(inner, text="—", font=("Segoe UI", 40),
                                    bg=self.colors["card"], fg=self.colors["primary"])
        self.weatherIcon.pack(anchor="w")

        self.tempLabel = tk.Label(inner, text="— °C", font=("Segoe UI", 26, "bold"),
                                  bg=self.colors["card"], fg=self.colors["text"])
        self.tempLabel.pack(anchor="w")

        self.descLabel = tk.Label(inner, text="", bg=self.colors["card"],
                                  fg=self.colors["muted"])
        self.descLabel.pack(anchor="w", pady=(5, 0))

        # forecast tabs
        self.tabs = ttk.Notebook(self.content)
        self.tabs.pack(fill="both", expand=True)
        self.tabForecast = tk.Frame(self.tabs, bg=self.colors["card"])
        self.tabRaw = tk.Frame(self.tabs, bg=self.colors["card"])
        self.tabs.add(self.tabForecast, text="Forecast")
        self.tabs.add(self.tabRaw, text="Raw Data")

        self.chartFrame = tk.Frame(self.tabForecast, bg=self.colors["card"])
        self.chartFrame.pack(fill="both", expand=True, padx=8, pady=8)

        self.rawText = tk.Text(self.tabRaw, bg=self.colors["card"], fg=self.colors["text"],
                               bd=0, font=("Consolas", 9))
        self.rawText.pack(fill="both", expand=True, padx=8, pady=8)

    # ---------------- actions -----------------
    def updateFavCombo(self):
        self.favCombo["values"] = self.favorites
        if self.favorites: self.favCombo.set(self.favorites[0])

    def _fav_selected(self, evt=None):
        city = self.favVar.get()
        if city: self.cityVar.set(city); self.getWeather()

    def getWeather(self):
        city = self.cityVar.get().strip()
        if not city:
            messagebox.showwarning("Need Input", "Enter city name first")
            return

        self.status.config(text=f"Fetching {city}...")
        self.root.update_idletasks()

        try:
            cur = self._get_current(city)
            fore = self._get_forecast(city)
            self._show_weather(cur, fore)
            self.status.config(text=f"Weather for {city}")
        except Exception as e:
            self.status.config(text="Error")
            messagebox.showerror("Error", str(e))

    def _show_weather(self, cur, fore):
        main = cur.get("main", {})
        desc = (cur.get("weather") or [{}])[0]
        temp = main.get("temp", 0)
        hum = main.get("humidity", 0)

        # quick icon map
        wtype = (desc.get("main") or "").lower()
        icons = {"clear": "☀️", "clouds": "☁️", "rain": "🌧️",
                 "snow": "❄️", "mist": "🌫️"}
        self.weatherIcon.config(text=icons.get(wtype, "🌤"))
        self.tempLabel.config(text=f"{round(temp)}°C")
        self.descLabel.config(text=f"{desc.get('description','').title()} | Hum: {hum}%")

        # raw data
        self.rawText.config(state="normal")
        self.rawText.delete("1.0", tk.END)
        self.rawText.insert("1.0", json.dumps(cur, indent=2))
        self.rawText.config(state="disabled")

        # forecast chart
        self._draw_chart(fore)

    def _draw_chart(self, forecast):
        for w in self.chartFrame.winfo_children(): w.destroy()
        lst = forecast.get("list", [])
        daily = {}
        for pt in lst:
            date = pt.get("dt_txt", "").split(" ")[0]
            if not date: continue
            t = pt.get("main", {}).get("temp")
            if t is None: continue
            if date not in daily: daily[date] = [t, t]
            else:
                daily[date][0] = min(daily[date][0], t)
                daily[date][1] = max(daily[date][1], t)

        if not daily:
            tk.Label(self.chartFrame, text="No forecast",
                     bg=self.colors["card"], fg=self.colors["muted"]).pack()
            return

        dates = list(sorted(daily.keys()))[:5]
        mins = [round(daily[d][0], 1) for d in dates]
        maxs = [round(daily[d][1], 1) for d in dates]

        fig = Figure(figsize=(6, 3), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(dates, maxs, "-o", label="High")
        ax.plot(dates, mins, "-o", label="Low")
        ax.set_title("5-Day Forecast")
        ax.legend()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, self.chartFrame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------------- top btn of theme and setting  -----------------
    def toggleTheme(self):
        if self.colors["bg"] == "#151521":
            self.colors.update({"bg": "#F5F7FA", "card": "#FFFFFF","muted": "#6C757D", "text": "#2B2D42"})
            messagebox.showinfo("Theme", "Light mode (beta)")
        else:
            self.colors.update({"bg": "#151521", "card": "#1F1F2B","muted": "#9aa0b4", "text": "#E6EEF3"})
            messagebox.showinfo("Theme", "Dark mode")
        self.root.config(bg=self.colors["bg"])

    def openSettings(self):
        if not self.api_key:
            messagebox.showwarning("Missing Key",
                                   "Put your OpenWeather API key in config.py")
        else:
            messagebox.showinfo("Settings", "API key loaded OK")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = WeatherApp(tk.Tk())
    app.run()