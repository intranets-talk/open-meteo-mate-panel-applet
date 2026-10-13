#!/usr/bin/env python3
"""
Open-Meteo Weather Applet for MATE Desktop Panel
------------------------------------------------
Displays current temperature as a Gtk.Label in the panel.
Left-click opens a 5-day forecast menu.
Supports location search, IP geolocation and periodic refresh.
"""

import os
import json
import urllib.request
import urllib.parse
import threading
import datetime
import sys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("MatePanelApplet", "4.0")
from gi.repository import Gtk, Gdk, GLib, MatePanelApplet

# ==============================================================================
# PANEL DISPLAY SETTINGS
# ==============================================================================
SHOW_UNIT_IN_PANEL = False          # True -> "15°C"   False -> "15°"
# ==============================================================================

CONFIG_DIR = os.path.expanduser("~/.config/open-meteo-weather")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "city": "Grays",
    "country": "United Kingdom",
    "latitude": 51.47566,
    "longitude": 0.32521,
    "update_interval_min": 30,
    "auto_ip": True,
}

# WMO Weather interpretation codes (WW)
WMO_WEATHER_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌧️"),
    53: ("Moderate drizzle", "🌧️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Light freezing drizzle", "🌧️"),
    57: ("Dense freezing drizzle", "🌧️"),
    61: ("Slight rain", "🌧️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    66: ("Light freezing rain", "🌧️"),
    67: ("Heavy freezing rain", "🌧️"),
    71: ("Slight snow", "🌨️"),
    73: ("Moderate snow", "🌨️"),
    75: ("Heavy snow", "🌨️"),
    77: ("Snow grains", "🌨️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌦️"),
    82: ("Violent rain showers", "⛈️"),
    85: ("Slight snow showers", "🌨️"),
    86: ("Heavy snow showers", "🌨️"),
    95: ("Thunderstorm", "🌩️"),
    96: ("Thunderstorm with hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}


def load_config():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                user_cfg = json.load(f)
                cfg.update(user_cfg)
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)

    if not isinstance(cfg.get("latitude"), (int, float)) or not isinstance(
        cfg.get("longitude"), (int, float)
    ):
        cfg["latitude"] = 51.5074
        cfg["longitude"] = -0.1278
        cfg["city"] = "London"
        cfg["country"] = "United Kingdom"
    return cfg


def save_config(cfg):
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}", file=sys.stderr)


class LocationDialog(Gtk.Dialog):
    def __init__(self, current_config, parent=None):
        super().__init__(
            title="Change Weather Location",
            transient_for=parent,
            flags=0,
        )
        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.select_btn = self.add_button("Select Location", Gtk.ResponseType.OK)
        self.select_btn.set_sensitive(False)

        self.set_default_size(420, 320)
        self.results = []

        box = self.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_left(12)
        box.set_margin_right(12)

        lbl = Gtk.Label(label="Search for your city (powered by Open-Meteo Geocoding):")
        lbl.set_xalign(0.0)
        box.pack_start(lbl, False, False, 0)

        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("e.g. London, Paris, Tokyo, New York...")
        self.entry.connect("activate", lambda e: self.on_search())
        search_box.pack_start(self.entry, True, True, 0)

        btn_search = Gtk.Button(label="Search")
        btn_search.connect("clicked", lambda b: self.on_search())
        search_box.pack_start(btn_search, False, False, 0)
        box.pack_start(search_box, False, False, 0)

        btn_auto = Gtk.Button(label="🌐 Use Automatic Location (IP Geolocation)")
        btn_auto.connect("clicked", lambda b: self.response(100))
        box.pack_start(btn_auto, False, False, 0)

        self.liststore = Gtk.ListStore(str, str, str, float, float)
        self.treeview = Gtk.TreeView(model=self.liststore)
        self.treeview.connect("cursor-changed", self.on_selection_changed)

        renderer = Gtk.CellRendererText()
        self.treeview.append_column(Gtk.TreeViewColumn("City", renderer, text=0))
        self.treeview.append_column(Gtk.TreeViewColumn("Region", renderer, text=1))
        self.treeview.append_column(Gtk.TreeViewColumn("Country", renderer, text=2))

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.treeview)
        box.pack_start(scrolled, True, True, 0)

        self.show_all()

    def on_search(self):
        query = self.entry.get_text().strip()
        if not query:
            return
        self.liststore.clear()
        self.select_btn.set_sensitive(False)
        threading.Thread(target=self._search_worker, args=(query,), daemon=True).start()

    def _search_worker(self, query):
        url = (
            f"https://geocoding-api.open-meteo.com/v1/search?"
            f"name={urllib.parse.quote(query)}&count=10&language=en&format=json"
        )
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode())
                results = data.get("results", [])
                GLib.idle_add(self._on_search_results, results)
        except Exception as e:
            print(f"Search error: {e}", file=sys.stderr)

    def _on_search_results(self, results):
        self.results = results
        self.liststore.clear()
        for r in results:
            name = r.get("name", "")
            admin = r.get("admin1", "")
            country = r.get("country", "")
            lat = r.get("latitude", 0.0)
            lon = r.get("longitude", 0.0)
            self.liststore.append([name, admin, country, lat, lon])

    def on_selection_changed(self, selection):
        model, treeiter = self.treeview.get_selection().get_selected()
        if treeiter is not None:
            self.select_btn.set_sensitive(True)

    def get_selected_location(self):
        model, treeiter = self.treeview.get_selection().get_selected()
        if treeiter is not None:
            return {
                "name": model[treeiter][0],
                "country": model[treeiter][2],
                "lat": model[treeiter][3],
                "lon": model[treeiter][4],
            }
        return None


class OpenMeteoWeatherApplet:
    def __init__(self, applet):
        self.applet = applet
        self.config = load_config()
        self.weather_data = None
        self.is_fetching = False

        # Main UI: EventBox so we can catch clicks + Label for the temperature
        self.event_box = Gtk.EventBox()
        self.event_box.set_visible_window(False)

        self.label = Gtk.Label()
        self.label.set_use_markup(True)
        self.label.set_margin_start(6)
        self.label.set_margin_end(6)
        self.label.set_markup("<b>--°</b>")

        self.event_box.add(self.label)
        self.event_box.connect("button-press-event", self.on_button_press)

        self.applet.add(self.event_box)
        self.applet.show_all()

        # Tooltip
        self.applet.set_tooltip_text("Open-Meteo Weather")

        # Build the popup menu
        self.menu = Gtk.Menu()
        self.rebuild_menu_loading()

        # Optional: allow the applet to expand a little if the panel wants it
        self.applet.set_flags(MatePanelApplet.AppletFlags.EXPAND_MINOR)

        # Start location detection + weather
        if self.config.get("auto_ip", True) and (
            self.config.get("city") in ("London", "Auto (IP)", "Grays")
        ):
            threading.Thread(target=self._ip_locate_worker, daemon=True).start()

        self.refresh_weather_async()

        interval_sec = max(5, self.config.get("update_interval_min", 30)) * 60
        GLib.timeout_add_seconds(interval_sec, self.on_timer_tick)

    # ------------------------------------------------------------------
    # Panel interaction
    # ------------------------------------------------------------------
    def on_button_press(self, widget, event):
        # Only left-click (and middle-click) open the forecast menu.
        # Right-click must be left for the panel so it can show
        # the standard "Move / Remove / …" menu.
        if event.button in (1, 2):
            self.menu.popup_at_widget(
                self.event_box,
                Gdk.Gravity.SOUTH_WEST,
                Gdk.Gravity.NORTH_WEST,
                event,
            )
            return True          # we handled the event

        # button 3 (right-click) → return False so the panel handles it
        return False

    def on_timer_tick(self):
        self.refresh_weather_async()
        return True

    # ------------------------------------------------------------------
    # Weather fetching
    # ------------------------------------------------------------------
    def _ip_locate_worker(self):
        try:
            req = urllib.request.Request(
                "http://ip-api.com/json/",
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                ip_data = json.loads(response.read().decode())
                lat = ip_data.get("lat")
                lon = ip_data.get("lon")
                city = ip_data.get("city")
                country = ip_data.get("country", "")
                if lat and lon and city:
                    self.config["latitude"] = lat
                    self.config["longitude"] = lon
                    self.config["city"] = city
                    self.config["country"] = country
                    self.config["auto_ip"] = False
                    save_config(self.config)
                    GLib.idle_add(self.refresh_weather_async)
        except Exception as e:
            print(f"IP Geolocation error: {e}", file=sys.stderr)

    def refresh_weather_async(self):
        if self.is_fetching:
            return
        self.is_fetching = True
        threading.Thread(target=self._fetch_weather_worker, daemon=True).start()

    def _fetch_weather_worker(self):
        lat = self.config.get("latitude", 51.5074)
        lon = self.config.get("longitude", -0.1278)
        city = self.config.get("city", "Local Weather")
        country = self.config.get("country", "")

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            f"&temperature_unit=celsius"
            f"&timezone=auto"
        )

        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                data["_location_name"] = f"{city}{', ' + country if country else ''}"
                data["_fetched_at"] = datetime.datetime.now().strftime("%H:%M")
                GLib.idle_add(self._on_weather_fetched_success, data)
        except Exception as e:
            print(f"Error fetching weather: {e}", file=sys.stderr)
            GLib.idle_add(self._on_weather_fetched_error, str(e))
        finally:
            self.is_fetching = False

    def _on_weather_fetched_success(self, data):
        self.weather_data = data
        current = data.get("current", {})
        temp = current.get("temperature_2m")

        if temp is not None:
            if SHOW_UNIT_IN_PANEL:
                display = f"{round(temp)}°C"
            else:
                display = f"{round(temp)}°"
        else:
            display = "--°"

        self.label.set_markup(display)
        self.applet.set_tooltip_text(
            f"Weather: {display} ({self.config.get('city', '')})"
        )
        self.rebuild_menu_full()

    def _on_weather_fetched_error(self, err_msg):
        self.label.set_markup('<span foreground="#ff6b6b">Err°</span>')
        self.rebuild_menu_error(err_msg)

    # ------------------------------------------------------------------
    # Menu construction
    # ------------------------------------------------------------------
    def clear_menu(self):
        for child in self.menu.get_children():
            self.menu.remove(child)

    def rebuild_menu_loading(self):
        self.clear_menu()
        item = Gtk.MenuItem(label="Loading weather data...")
        item.set_sensitive(False)
        self.menu.append(item)
        self.menu.show_all()

    def rebuild_menu_error(self, err_msg):
        self.clear_menu()

        err_item = Gtk.MenuItem()
        lbl = Gtk.Label()
        lbl.set_markup(
            f"<span foreground='#ff6b6b'><b>Unable to update weather</b></span>\n"
            f"<small>{GLib.markup_escape_text(err_msg)}</small>"
        )
        lbl.set_xalign(0.0)
        err_item.add(lbl)
        err_item.set_sensitive(False)
        self.menu.append(err_item)

        self.menu.append(Gtk.SeparatorMenuItem())
        self.append_action_items()
        self.menu.show_all()

    def rebuild_menu_full(self):
        self.clear_menu()
        if not self.weather_data:
            self.rebuild_menu_loading()
            return

        data = self.weather_data
        current = data.get("current", {})
        current_units = data.get("current_units", {})
        daily = data.get("daily", {})

        location_name = data.get("_location_name", "Local Weather")
        fetched_at = data.get("_fetched_at", "")
        temp = current.get("temperature_2m", 0)
        wind = current.get("wind_speed_10m", 0)
        code = current.get("weather_code", 0)

        wind_unit = current_units.get("wind_speed_10m", "km/h")
        cond_desc, emoji = WMO_WEATHER_CODES.get(code, ("Clear", "☀️"))

        # --- HEADER ---
        hdr_item = Gtk.MenuItem()
        hdr_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        hdr_box.set_margin_start(12)
        hdr_box.set_margin_end(20)
        hdr_box.set_margin_top(6)
        hdr_box.set_margin_bottom(6)

        lbl_loc = Gtk.Label()
        lbl_loc.set_markup(
            f"<span foreground='#ffffff' size='large'><b>{GLib.markup_escape_text(location_name)}</b></span>"
        )
        lbl_loc.set_xalign(0.0)

        lbl_curr = Gtk.Label()
        lbl_curr.set_markup(
            f"<span foreground='#ffffff'><b>{round(temp, 1)}°C</b></span> "
            f"<span foreground='#e0e0e0'>• {emoji} {cond_desc}</span>"
        )
        lbl_curr.set_xalign(0.0)

        lbl_sub = Gtk.Label()
        lbl_sub.set_markup(
            f"<span foreground='#b0b0b0' size='small'>"
            f"💨 Wind: {wind} {wind_unit}  |  🕒 Updated {fetched_at}"
            f"</span>"
        )
        lbl_sub.set_xalign(0.0)

        hdr_box.pack_start(lbl_loc, False, False, 0)
        hdr_box.pack_start(lbl_curr, False, False, 0)
        hdr_box.pack_start(lbl_sub, False, False, 0)
        hdr_item.add(hdr_box)
        hdr_item.set_sensitive(False)
        self.menu.append(hdr_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        # --- SECTION TITLE ---
        title_item = Gtk.MenuItem()
        lbl_title = Gtk.Label()
        lbl_title.set_markup(
            "<span foreground='#80deea'><b>5-DAY FORECAST</b></span>"
        )
        lbl_title.set_xalign(0.0)
        lbl_title.set_margin_start(12)
        lbl_title.set_margin_end(20)
        title_item.add(lbl_title)
        title_item.set_sensitive(False)
        self.menu.append(title_item)

        # --- 5-DAY ROWS ---
        times = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])

        for i in range(min(5, len(times))):
            date_str = times[i]
            t_max = max_temps[i] if i < len(max_temps) else 0
            t_min = min_temps[i] if i < len(min_temps) else 0

            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            day_name = "Today" if i == 0 else dt.strftime("%a %d %b")

            item = Gtk.MenuItem()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            box.set_margin_start(12)
            box.set_margin_end(20)

            lbl_day = Gtk.Label()
            lbl_day.set_markup(
                f"<span foreground='#ffffff'><b>{day_name}</b></span>"
            )
            lbl_day.set_xalign(0.0)

            lbl_temp = Gtk.Label()
            lbl_temp.set_markup(
                f"<span foreground='#ffffff'><b>{round(t_min)}°C  /  {round(t_max)}°C</b></span>"
            )
            lbl_temp.set_xalign(1.0)

            box.pack_start(lbl_day, True, True, 0)
            box.pack_end(lbl_temp, False, False, 0)
            item.add(box)
            self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())
        self.append_action_items()
        self.menu.show_all()

    def append_action_items(self):
        ref_item = Gtk.MenuItem(label="Refresh Weather")
        ref_item.connect("activate", lambda w: self.refresh_weather_async())
        self.menu.append(ref_item)

        loc_item = Gtk.MenuItem(label="Change Location...")
        loc_item.connect("activate", lambda w: self.show_location_dialog())
        self.menu.append(loc_item)

        #self.menu.append(Gtk.SeparatorMenuItem())
        # Note: "Quit" is less useful for a panel applet (panel manages lifetime),
        # but we keep it for convenience while testing.
        #quit_item = Gtk.MenuItem(label="Quit")
        #quit_item.connect("activate", lambda w: Gtk.main_quit())
        #self.menu.append(quit_item)

    def show_location_dialog(self):
        dialog = LocationDialog(self.config, parent=None)
        res = dialog.run()
        if res == Gtk.ResponseType.OK:
            selected = dialog.get_selected_location()
            if selected:
                self.config["city"] = selected["name"]
                self.config["country"] = selected["country"]
                self.config["latitude"] = selected["lat"]
                self.config["longitude"] = selected["lon"]
                self.config["auto_ip"] = False
                save_config(self.config)
                self.rebuild_menu_loading()
                self.refresh_weather_async()
        elif res == 100:  # Auto IP
            self.config["auto_ip"] = True
            save_config(self.config)
            self.rebuild_menu_loading()
            threading.Thread(target=self._ip_locate_worker, daemon=True).start()
        dialog.destroy()


# ==============================================================================
# Applet factory (required by MatePanelApplet)
# ==============================================================================
def applet_factory(applet, iid, data):
    if iid != "OpenMeteoWeatherApplet":
        return False
    OpenMeteoWeatherApplet(applet)
    return True


MatePanelApplet.Applet.factory_main(
    "OpenMeteoWeatherAppletFactory",
    True,  # out-of-process
    MatePanelApplet.Applet.__gtype__,
    applet_factory,
    None,
)
