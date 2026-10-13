# Open-Meteo Weather Applet for MATE Desktop

A **MatePanelApplet** that shows the current temperature as text in the panel and opens a 5-day forecast on click. Simple stuff, nothing fancy. 

Uses the free [Open-Meteo](https://open-meteo.com/) API (no API key required).

## Features

- Current temperature displayed as a normal `Gtk.Label`
- Left-click opens a 5-day forecast menu
- Location search powered by Open-Meteo Geocoding
- Optional automatic location via IP geolocation
- Configurable update interval
- Config stored in `~/.config/open-meteo-weather/config.json`

## Requirements

- MATE Desktop (tested on Debian 12 / Ubuntu MATE)
- Python 3
- `python3-gi` (PyGObject)
- `gir1.2-gtk-3.0`
- `gir1.2-matepanelapplet-4.0` (usually provided by `mate-panel` / `libmate-panel-applet`)

On Debian/Ubuntu:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 mate-panel
```

## Installation

```bash
cd open-meteo-weather-applet
chmod +x install.sh
sudo ./install.sh
```

Then:

1. Right-click the MATE panel → **Add to Panel…**
2. Find **Open-Meteo Weather** and add it.

If it does not appear immediately:

```bash
mate-panel --replace &
```

or simply log out and back in.

## Uninstall

```bash
sudo rm /usr/lib/mate-panel/open_meteo_weather_applet.py
sudo rm /usr/share/mate-panel/applets/org.mate.panel.OpenMeteoWeather.mate-panel-applet
sudo rm /usr/share/dbus-1/services/org.mate.panel.applet.OpenMeteoWeatherFactory.service
```

## Configuration

Edit `~/.config/open-meteo-weather/config.json` or use the **Change Location…** menu item.

Useful keys:

| Key                   | Default | Description                          |
|-----------------------|---------|--------------------------------------|
| `city`                | Grays   | Display name                         |
| `latitude` / `longitude` | …    | Coordinates for the API              |
| `update_interval_min` | 30      | How often to refresh (minutes)       |
| `auto_ip`             | true    | Try IP geolocation on first start    |

## Panel display options

Near the top of `open_meteo_weather_applet.py`:

```python
SHOW_UNIT_IN_PANEL = False   # True → "15°C"   False → "15°"
```

Restart the panel (or remove + re-add the applet) after changing this.

## License

MIT / do whatever you want. Weather data © Open-Meteo.
