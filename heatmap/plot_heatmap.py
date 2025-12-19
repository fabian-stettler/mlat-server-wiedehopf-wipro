#!/usr/bin/env python3
import json
import matplotlib
matplotlib.use('Agg')  # Für Server ohne Display
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# JSON-Daten laden
json_file = './extractedEntries/entries.json'
with open(json_file, 'r') as f:
    data = json.load(f)

# Koordinaten extrahieren
adsb_lat = []
adsb_lon = []
mode_s_lat = []
mode_s_lon = []

for icao, entries in data.items():
    for entry_data in entries:
        entry = entry_data['entry']
        if 'lat' in entry and 'lon' in entry:
            source = entry.get('mlat_result_source', 'unknown')
            lat = entry['lat']
            lon = entry['lon']
            if source == 'adsb':
                adsb_lat.append(lat)
                adsb_lon.append(lon)
            else:
                mode_s_lat.append(lat)
                mode_s_lon.append(lon)

total_positions = len(adsb_lat) + len(mode_s_lat)
print(f"Gefundene Positionen: {total_positions}")

# Schweizer Grenzen
swiss_bounds = {
    'lat_min': 45.8,
    'lat_max': 47.8,
    'lon_min': 5.9,
    'lon_max': 10.5
}

# Figure mit Mercator-Karte
fig = plt.figure(figsize=(12, 10))
ax = plt.axes(projection=ccrs.Mercator())

# Grenzen setzen
ax.set_extent([
    swiss_bounds['lon_min'],
    swiss_bounds['lon_max'],
    swiss_bounds['lat_min'],
    swiss_bounds['lat_max']
], crs=ccrs.PlateCarree())

# Hintergrund / Features
ax.add_feature(cfeature.LAND.with_scale('50m'), facecolor='beige')
ax.add_feature(cfeature.OCEAN.with_scale('50m'), facecolor='lightblue')
ax.add_feature(cfeature.BORDERS.with_scale('50m'), linewidth=1.0)
ax.add_feature(cfeature.COASTLINE.with_scale('50m'), linewidth=0.7)
ax.add_feature(cfeature.LAKES.with_scale('50m'), facecolor='lightblue')

# Flugzeugpositionen plotten
if total_positions > 0:
    if mode_s_lat:
        ax.scatter(
            mode_s_lon,
            mode_s_lat,
            color='blue',
            s=50,
            alpha=0.6,
            edgecolor='navy',
            linewidth=0.5,
            transform=ccrs.PlateCarree(),
            label="Mode S"
        )
    if adsb_lat:
        ax.scatter(
            adsb_lon,
            adsb_lat,
            color='red',
            s=50,
            alpha=0.6,
            edgecolor='darkred',
            linewidth=0.5,
            transform=ccrs.PlateCarree(),
            label="ADS-B"
        )
else:
    print("WARNUNG: Keine Positionen zum Plotten gefunden!")

# Titel
plt.title(
    f"Flugzeugpositionen über der Schweiz\n({total_positions} Positionen)",
    fontsize=14,
    fontweight="bold"
)

# Legende
plt.legend(loc='upper right')

# Statistiken anzeigen
stats_text = f'Positionen: {total_positions}'
plt.text(
    0.02, 0.98, stats_text, transform=ax.transAxes,
    verticalalignment='top', fontsize=10,
    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
)

plt.tight_layout()
plt.savefig('swiss_flights_map.png', dpi=300, bbox_inches='tight')

print("Karte gespeichert als 'swiss_flights_map.png'")
print(f"Anzahl geploteter Positionen: {total_positions}")
