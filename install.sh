#!/bin/bash
# Install Open-Meteo Weather Applet for MATE Desktop
# Run with: sudo ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing Open-Meteo Weather Applet ==="

# 1. Python script
install -d /usr/lib/mate-panel
install -m 755 "$SCRIPT_DIR/open_meteo_weather_applet.py" \
    /usr/lib/mate-panel/open_meteo_weather_applet.py
echo "Installed: /usr/lib/mate-panel/open_meteo_weather_applet.py"

# 2. Panel applet descriptor
install -d /usr/share/mate-panel/applets
install -m 644 "$SCRIPT_DIR/org.mate.panel.OpenMeteoWeather.mate-panel-applet" \
    /usr/share/mate-panel/applets/org.mate.panel.OpenMeteoWeather.mate-panel-applet
echo "Installed: /usr/share/mate-panel/applets/org.mate.panel.OpenMeteoWeather.mate-panel-applet"

# 3. D-Bus service
install -d /usr/share/dbus-1/services
install -m 644 "$SCRIPT_DIR/org.mate.panel.applet.OpenMeteoWeatherFactory.service" \
    /usr/share/dbus-1/services/org.mate.panel.applet.OpenMeteoWeatherFactory.service
echo "Installed: /usr/share/dbus-1/services/org.mate.panel.applet.OpenMeteoWeatherFactory.service"

echo ""
echo "Installation complete!"
echo ""
echo "To add the applet to your panel:"
echo "  1. Right-click on the MATE panel"
echo "  2. Choose \"Add to Panel...\""
echo "  3. Find \"Open-Meteo Weather\" and click Add"
echo ""
echo "If the applet does not appear, try:"
echo "  mate-panel --replace &"
echo "  (or log out and back in)"
echo ""
echo "Config is stored in: ~/.config/open-meteo-weather/config.json"
