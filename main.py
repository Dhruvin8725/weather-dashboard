""" wheather Deshborad by Dhruvin Barvaliya """
import os
import json
from datetime import datetime
from math import ceil  # kept, even if not used elsewhere, to avoid altering structure

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog  # simpledialog left in place, per "no feature change"

import requests

# Matplotlib (embed-safe backend)
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# >>> API key now comes from config.py <<<
from config import API_KEY


# ====================== (Legacy) Local Config Utilities ======================
# Kept to respect the "don’t change anything except API key source" instruction.
# These helpers are no longer used for API key storage.
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".weather_config.json")


def load_local_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_local_config(data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ====================== API Manager ======================

class APIManager:
    """Thin wrapper around OpenWeatherMap endpoints."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"

    def set_api_key(self, key: str) -> None:
        self.api_key = key

    def _request(self, endpoint: str, params: dict, timeout: int = 10) -> dict:
        url = f"{self.base_url}/{endpoint}"
        params.update({"appid": self.api_key, "units": "metric"})
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def get_current_weather(self, city: str) -> dict:
        return self._request("weather", {"q": city})

    def get_forecast(self, city: str) -> dict:
        return self._request("forecast", {"q": city})

    def is_valid_city(self, city: str) -> bool:
        try:
            self.get_current_weather(city)
            return True
        except Exception:
            return False


# ====================== Favorites (Data Handler) ======================

class DataHandler:
    def __init__(self, filename: str = "favorites.json"):
        self.filename = filename

    def load_favorites(self):
        if not os.path.exists(self.filename):
            return []
        try:
            with open(self.filename, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def save_favorites(self, favs):
        try:
            with open(self.filename, "w") as f:
                json.dump(favs, f, indent=2)
        except Exception:
            pass

    def add_favorite(self, city, api_manager: APIManager):
        city = city.strip()
        if not city:
            return False, "invalid"

        # Validate via API before adding:
        if not api_manager.is_valid_city(city):
            removed = self.remove_favorite(city)
            return (False, "removed" if removed else "invalid")

        favs = self.load_favorites()
        if city not in favs:
            favs.append(city)
            self.save_favorites(favs)
            return True, "added"
        return False, "exists"

    def remove_favorite(self, city):
        favs = self.load_favorites()
        if city in favs:
            favs.remove(city)
            self.save_favorites(favs)
            return True
        return False


# ====================== Weather Data Model ======================

class WeatherData:
    def __init__(self, api_data: dict, forecast_data: dict | None = None):
        self.raw = api_data
        self.city = api_data.get("name", "Unknown")
        self.country = api_data.get("sys", {}).get("country", "")
        self.temperature = api_data.get("main", {}).get("temp", 0)
        self.feels_like = api_data.get("main", {}).get("feels_like", 0)
        self.humidity = api_data.get("main", {}).get("humidity", 0)
        self.pressure = api_data.get("main", {}).get("pressure", 0)
        self.wind_speed = api_data.get("wind", {}).get("speed", 0)
        self.description = api_data.get("weather", [{}])[0].get("description", "").title()
        self.weather_main = api_data.get("weather", [{}])[0].get("main", "").lower()
        self.visibility = api_data.get("visibility", "N/A")
        self.forecast_data = forecast_data
        self.timestamp = datetime.now()

    def icon(self) -> str:
        mapping = {
            "clear": "☀️",
            "clouds": "☁️",
            "rain": "🌧️",
            "drizzle": "🌦️",
            "thunderstorm": "⛈️",
            "snow": "❄️",
            "mist": "🌫️",
            "fog": "🌫️",
        }
        return mapping.get(self.weather_main, "🌤️")

    def process_forecast(self):
        if not self.forecast_data:
            return None

        daily = {}
        for item in self.forecast_data.get("list", []):
            date = item["dt_txt"].split(" ")[0]
            temp = item["main"]["temp"]
            if date not in daily:
                daily[date] = {"temps": [], "min": temp, "max": temp}
            daily[date]["temps"].append(temp)
            daily[date]["min"] = min(daily[date]["min"], temp)
            daily[date]["max"] = max(daily[date]["max"], temp)

        ordered = []
        for d in sorted(daily.keys()):
            ordered.append(
                {"date": d, "min": round(daily[d]["min"], 1), "max": round(daily[d]["max"], 1)}
            )
        return ordered


# ====================== UI Helpers (Card, Button) ======================

class RoundedCard(tk.Canvas):
    def __init__(self, parent, radius=12, bg="#2A2A3C", padding=10, **kwargs):
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, **kwargs)
        self.radius = radius
        self.bg = bg
        self.padding = padding
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 0 or h <= 0:
            return
        x1, y1, x2, y2 = self.padding, self.padding, w - self.padding, h - self.padding
        r = self.radius
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r,
            x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1, x1 + r, y1
        ]
        self.create_polygon(points, smooth=True, fill=self.bg, outline="")


class ModernButton(tk.Canvas):
    def __init__(
        self,
        parent,
        text,
        command=None,
        bg="#4CAF50",
        fg="white",
        radius=12,
        width=140,
        height=40,
        font=None,
        **kwargs,
    ):
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg"), highlightthickness=0, **kwargs)
        self.text = text
        self.command = command
        self.bg = bg
        self.fg = fg
        self.radius = radius
        self.font = font or ("Segoe UI", 11, "bold")
        self.width = width
        self.height = height

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self.configure(cursor="hand2"))
        self.bind("<Leave>", lambda e: self.configure(cursor=""))
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w = self.winfo_width() or self.width
        h = self.winfo_height() or self.height
        try:
            self.create_rectangle(0, 0, w, h, outline="", fill=self.bg)
        except Exception:
            pass
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fg, font=self.font)

    def _on_click(self, _):
        if self.command:
            self.command()


# ====================== Main Application ======================

class ModernWeatherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modern Weather Dashboard")
        self.root.geometry("980x720")
        self.root.minsize(840, 640)
        self.root.configure(bg="#151521")

        # Managers
        self.api_manager = APIManager(API_KEY)
        self.data_handler = DataHandler()
        self.current_data = None

        # Theme
        self.colors = {
            "bg": "#151521",
            "card": "#1F1F2B",
            "muted": "#9aa0b4",
            "primary": "#4CAF50",
            "accent": "#2196F3",
            "text": "#E6EEF3",
        }

        # Layout
        self._build_top_bar()
        self._build_main_area()
        self._build_status_bar()

        # Key bindings
        self.root.bind("<Return>", lambda e: self.fetch_weather())

        # Favorites
        self._refresh_favorites()

    # ---------- Top Bar ----------
    def _build_top_bar(self):
        top = tk.Frame(self.root, bg=self.colors["bg"])
        top.pack(fill=tk.X, padx=18, pady=(18, 6))

        title = tk.Label(
            top,
            text="🌤 Modern Weather Dashboard",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(side=tk.LEFT)

        btn_frame = tk.Frame(top, bg=self.colors["bg"])
        btn_frame.pack(side=tk.RIGHT)

        settings_btn = ModernButton(
            btn_frame,
            text="⚙ Settings",
            command=self.open_settings,
            bg="#2E2E3E",
            fg=self.colors["text"],
            width=110,
            height=34,
        )
        settings_btn.pack(side=tk.LEFT, padx=(0, 8))

        theme_btn = ModernButton(
            btn_frame,
            text="☀ Toggle Theme",
            command=self.toggle_theme,
            bg="#2E2E3E",
            fg=self.colors["text"],
            width=120,
            height=34,
        )
        theme_btn.pack(side=tk.LEFT)

    def toggle_theme(self):
        # Two-palette toggle; keep behavior identical.
        if self.colors["bg"] == "#151521":
            self.colors.update(
                {"bg": "#F5F7FA", "card": "#FFFFFF", "muted": "#6C757D", "text": "#2B2D42"}
            )
        else:
            self.colors.update(
                {"bg": "#151521", "card": "#1F1F2B", "muted": "#9aa0b4", "text": "#E6EEF3"}
            )

        self.root.configure(bg=self.colors["bg"])
        self.main_frame.configure(bg=self.colors["bg"])
        self.side_panel.configure(bg=self.colors["bg"])
        self.content_panel.configure(bg=self.colors["bg"])
        self.status_label.configure(bg=self.colors["bg"], fg=self.colors["muted"])
        self._refresh_favorites()

    # >>> Settings: now auto-loads key from config.py (no dialog) <<<
    def open_settings(self):
        if not str(API_KEY).strip():
            messagebox.showwarning(
                "API Key Missing",
                "API key is not set in config.py. Please add it.",
                parent=self.root,
            )
            return

        self.api_manager.set_api_key(API_KEY)
        messagebox.showinfo(
            "Settings",
            "API key is loaded automatically from config.py.",
            parent=self.root,
        )

    # ---------- Main Area ----------
    def _build_main_area(self):
        self.main_frame = tk.Frame(self.root, bg=self.colors["bg"])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=(6, 10))

        # Left: search + favorites
        self.side_panel = tk.Frame(self.main_frame, bg=self.colors["bg"], width=320)
        self.side_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))

        # Right: content
        self.content_panel = tk.Frame(self.main_frame, bg=self.colors["bg"])
        self.content_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_side_panel()
        self._build_content_panel()

    def _build_side_panel(self):
        # Search card
        card = RoundedCard(self.side_panel, bg=self.colors["card"])
        card.pack(fill=tk.X, pady=(0, 12))
        card.config(height=120)

        inner = tk.Frame(card, bg=self.colors["card"])
        inner.place(relx=0.02, rely=0.05, relwidth=0.96, relheight=0.9)

        tk.Label(inner, text="Search city", bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w")

        entry_frame = tk.Frame(inner, bg=self.colors["card"])
        entry_frame.pack(fill=tk.X, pady=(8, 6))

        self.city_var = tk.StringVar()
        self.city_entry = tk.Entry(
            entry_frame,
            textvariable=self.city_var,
            font=("Segoe UI", 13),
            bg="#272731",
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            bd=0,
        )
        self.city_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)

        ModernButton(
            entry_frame,
            text="🔎 Search",
            command=self.fetch_weather,
            bg=self.colors["primary"],
            fg="white",
            width=90,
            height=38,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # Favorites card
        fav_card = RoundedCard(self.side_panel, bg=self.colors["card"])
        fav_card.pack(fill=tk.X, pady=(0, 12))
        fav_card.config(height=140)

        fav_inner = tk.Frame(fav_card, bg=self.colors["card"])
        fav_inner.place(relx=0.02, rely=0.05, relwidth=0.96, relheight=0.9)

        tk.Label(
            fav_inner,
            text="Favorites",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")

        self.fav_var = tk.StringVar()
        self.fav_combo = ttk.Combobox(fav_inner, textvariable=self.fav_var, state="readonly")
        self.fav_combo.pack(fill=tk.X, pady=(8, 6))
        self.fav_combo.bind("<<ComboboxSelected>>", lambda e: self._on_favorite_select())

        btns = tk.Frame(fav_inner, bg=self.colors["card"])
        btns.pack(fill=tk.X)

        ModernButton(
            btns, text="⭐ Add", command=self._add_current_to_favorites, bg="#10B981", fg="white", width=86, height=34
        ).pack(side=tk.LEFT)

        ModernButton(
            btns, text="🗑 Remove", command=self._remove_selected_favorite, bg="#B00020", fg="white", width=86, height=34
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _build_content_panel(self):
        # Summary card
        self.summary_card = RoundedCard(self.content_panel, bg=self.colors["card"])
        self.summary_card.pack(fill=tk.X, pady=(0, 12))
        self.summary_card.config(height=160)

        self.summary_inner = tk.Frame(self.summary_card, bg=self.colors["card"])
        self.summary_inner.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)

        left = tk.Frame(self.summary_inner, bg=self.colors["card"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = tk.Frame(self.summary_inner, bg=self.colors["card"])
        right.pack(side=tk.RIGHT, fill=tk.Y)

        self.icon_lbl = tk.Label(left, text="—", font=("Segoe UI", 42), bg=self.colors["card"], fg=self.colors["primary"])
        self.icon_lbl.pack(anchor="w")

        self.temp_lbl = tk.Label(left, text="— °C", font=("Segoe UI", 28, "bold"), bg=self.colors["card"], fg=self.colors["text"])
        self.temp_lbl.pack(anchor="w")

        self.desc_lbl = tk.Label(left, text="", font=("Segoe UI", 12), bg=self.colors["card"], fg=self.colors["muted"])
        self.desc_lbl.pack(anchor="w", pady=(6, 0))

        self.details_frame = tk.Frame(right, bg=self.colors["card"])
        self.details_frame.pack()

        self._populate_details_placeholder()

        # Notebook (forecast + raw)
        nb_card = RoundedCard(self.content_panel, bg=self.colors["card"])
        nb_card.pack(fill=tk.BOTH, expand=True)
        nb_card.config(height=380)

        nb_inner = tk.Frame(nb_card, bg=self.colors["card"])
        nb_inner.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)

        self.notebook = ttk.Notebook(nb_inner)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_forecast = tk.Frame(self.notebook, bg=self.colors["card"])
        self.notebook.add(self.tab_forecast, text="Forecast")

        self.tab_raw = tk.Frame(self.notebook, bg=self.colors["card"])
        self.notebook.add(self.tab_raw, text="Raw Data")

        self.chart_container = tk.Frame(self.tab_forecast, bg=self.colors["card"])
        self.chart_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.raw_text = tk.Text(self.tab_raw, bg=self.colors["card"], fg=self.colors["text"], bd=0)
        self.raw_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.raw_text.configure(state="disabled")

    def _populate_details_placeholder(self):
        for widget in self.details_frame.winfo_children():
            widget.destroy()
        for k, v in [("Humidity", "-- %"), ("Pressure", "-- hPa"), ("Wind", "-- m/s"), ("Visibility", "-- m")]:
            tk.Label(self.details_frame, text=k, font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["muted"]).pack(anchor="e")
            tk.Label(self.details_frame, text=v, font=("Segoe UI", 11, "bold"), bg=self.colors["card"], fg=self.colors["text"]).pack(anchor="e", pady=(0, 6))

    # ---------- Status Bar ----------
    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg=self.colors["bg"])
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = tk.Label(bar, text="Ready", bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 10))
        self.status_label.pack(side=tk.LEFT, padx=12, pady=8)

    # ====================== Favorites Actions ======================

    def _refresh_favorites(self):
        favs = self.data_handler.load_favorites()
        try:
            self.fav_combo["values"] = favs
        except Exception:
            pass
        if favs:
            self.fav_combo.set(favs[0])

    def _on_favorite_select(self):
        city = self.fav_var.get()
        if city:
            self.city_var.set(city)
            self.fetch_weather()

    def _add_current_to_favorites(self):
        city = self.city_var.get().strip()
        if not city:
            messagebox.showwarning("Input", "Enter a city name first.", parent=self.root)
            return
        ok, result = self.data_handler.add_favorite(city, self.api_manager)
        if ok:
            messagebox.showinfo("Added", f"{city} added to favorites.", parent=self.root)
            self._refresh_favorites()
        else:
            if result == "exists":
                messagebox.showinfo("Exists", f"{city} is already a favorite.", parent=self.root)
            elif result == "removed":
                messagebox.showwarning("Invalid", f"{city} was not valid and removed from favorites.", parent=self.root)
            else:
                messagebox.showwarning("Invalid", f"{city} is not a valid city.", parent=self.root)
        self._refresh_favorites()

    def _remove_selected_favorite(self):
        city = self.fav_var.get().strip()
        if not city:
            messagebox.showwarning("Select", "Select a favorite to remove.", parent=self.root)
            return
        removed = self.data_handler.remove_favorite(city)
        if removed:
            messagebox.showinfo("Removed", f"{city} removed from favorites.", parent=self.root)
            self._refresh_favorites()
        else:
            messagebox.showwarning("Not found", "City not found in favorites.", parent=self.root)

    # ====================== Fetching & Display ======================

    def fetch_weather(self):
        city = self.city_var.get().strip()
        if not city:
            messagebox.showwarning("Input Required", "Please enter a city name (e.g., London, Tokyo).", parent=self.root)
            return
        if not self.api_manager.api_key:
            messagebox.showerror("API Key", "API key not set. Open Settings to add your OpenWeatherMap API key.", parent=self.root)
            return

        self.status_label.config(text="Fetching weather...")
        self.root.update()

        try:
            current = self.api_manager.get_current_weather(city)
            forecast = self.api_manager.get_forecast(city)
            self.current_data = WeatherData(current, forecast)
            self._update_ui_with_data()
            self.status_label.config(text=f"Loaded data for {self.current_data.city}, {self.current_data.country}")
        except requests.exceptions.HTTPError as e:
            self.status_label.config(text="Error")
            messagebox.showerror("API Error", f"Failed to get data: {e}", parent=self.root)
        except requests.exceptions.RequestException as e:
            self.status_label.config(text="Network error")
            messagebox.showerror("Network", f"Network error: {e}", parent=self.root)
        except Exception as e:
            self.status_label.config(text="Error")
            messagebox.showerror("Error", f"Unexpected error: {e}", parent=self.root)

    def _update_ui_with_data(self):
        if not self.current_data:
            return

        d = self.current_data

        # Summary
        self.icon_lbl.config(text=d.icon(), fg=self.colors["primary"])
        self.temp_lbl.config(text=f"{round(d.temperature)}°C")
        self.desc_lbl.config(text=d.description)

        # Details
        for widget in self.details_frame.winfo_children():
            widget.destroy()
        for k, v in [
            ("Humidity", f"{d.humidity}%"),
            ("Pressure", f"{d.pressure} hPa"),
            ("Wind", f"{d.wind_speed} m/s"),
            ("Visibility", f"{d.visibility} m"),
        ]:
            tk.Label(self.details_frame, text=k, font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["muted"]).pack(anchor="e")
            tk.Label(self.details_frame, text=v, font=("Segoe UI", 11, "bold"), bg=self.colors["card"], fg=self.colors["text"]).pack(anchor="e", pady=(0, 6))

        # Raw JSON
        try:
            self.raw_text.configure(state="normal")
            self.raw_text.delete("1.0", tk.END)
            pretty = json.dumps({"current": d.raw, "forecast_sample": d.forecast_data}, indent=2)
            self.raw_text.insert("1.0", pretty)
            self.raw_text.configure(state="disabled")
        except Exception:
            pass

        # Forecast chart
        self._draw_forecast_chart()

    def _draw_forecast_chart(self):
        for w in self.chart_container.winfo_children():
            w.destroy()

        forecast_list = None
        if self.current_data and self.current_data.forecast_data:
            forecast_list = self.current_data.process_forecast()

        if not forecast_list:
            tk.Label(self.chart_container, text="Forecast not available", bg=self.colors["card"], fg=self.colors["muted"]).pack(padx=10, pady=10)
            return

        fig = Figure(figsize=(6, 3.2), dpi=100)
        fig.patch.set_facecolor(self.colors["card"])
        ax = fig.add_subplot(111)
        ax.set_facecolor(self.colors["card"])

        dates = [datetime.strptime(x["date"], "%Y-%m-%d").strftime("%a %d") for x in forecast_list[:7]]
        mins = [x["min"] for x in forecast_list[:7]]
        maxs = [x["max"] for x in forecast_list[:7]]

        ax.plot(dates, maxs, marker="o", linewidth=2, label="Max", color=self.colors["primary"])
        ax.plot(dates, mins, marker="o", linewidth=2, label="Min", color=self.colors["accent"])

        ax.set_title("5-7 Day Forecast", color=self.colors["text"], fontsize=12, fontweight="bold")
        ax.set_ylabel("°C", color=self.colors["muted"])
        ax.tick_params(colors=self.colors["muted"])
        ax.grid(True, color="#2D2D3B", linestyle="--", linewidth=0.7)
        ax.legend(facecolor=self.colors["card"], framealpha=0.9, labelcolor=self.colors["text"])

        all_vals = mins + maxs
        margin = 2
        ax.set_ylim(min(all_vals) - margin, max(all_vals) + margin)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------- Main loop ----------
    def run(self):
        self.root.mainloop()


# ====================== Entry ======================

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernWeatherApp(root)
    root.after(100, lambda: None)
    app.run()