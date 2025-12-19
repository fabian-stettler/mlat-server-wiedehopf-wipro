#!/usr/bin/env python3
"""
MLAT vs ADS-B Position Error Calculator
Vergleicht MLAT-Positionen (pseudorange.json) mit ADS-B GPS-Referenz (entries.json)
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

def ecef_to_lla(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """
    Konvertiert ECEF (Earth-Centered Earth-Fixed) zu LLA (Lat, Lon, Alt)
    WGS84 Ellipsoid
    """
    a = 6378137.0  # WGS84 Äquatorradius in Metern
    e2 = 0.00669437999014  # Erste Exzentrizität^2
    
    # Berechne Longitude
    lon = math.atan2(y, x)
    
    # Berechne Latitude (iterativ)
    p = math.sqrt(x**2 + y**2)
    lat = math.atan2(z, p * (1 - e2))
    
    for _ in range(5):  # Iterationen für Genauigkeit
        N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
        lat = math.atan2(z + e2 * N * math.sin(lat), p)
    
    # Berechne Altitude
    N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
    alt = p / math.cos(lat) - N
    
    # Konvertiere zu Grad
    lat_deg = math.degrees(lat)
    lon_deg = math.degrees(lon)
    
    return lat_deg, lon_deg, alt

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Berechnet die horizontale Distanz zwischen zwei GPS-Koordinaten in Metern
    """
    R = 6371000  # Erdradius in Metern
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def load_pseudorange_data(filename: str) -> Dict[str, List[Dict]]:
    """
    Lädt MLAT-Positionen aus pseudorange.json (NDJSON Format)
    """
    mlat_data = {}
    
    decoder = json.JSONDecoder()
    with open(filename, 'r') as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            idx = 0
            while idx < len(line):
                if line[idx].isspace():
                    idx += 1
                    continue
                try:
                    entry, next_idx = decoder.raw_decode(line, idx)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Ungültige Daten in {filename} (Zeile {line_no}): {exc}") from exc
                idx = next_idx

                icao = entry['icao'].lower()
            
                # Konvertiere ECEF zu Lat/Lon
                x, y, z = entry['ecef']
                lat, lon, alt = ecef_to_lla(x, y, z)
            
                if icao not in mlat_data:
                    mlat_data[icao] = []
            
                mlat_data[icao].append({
                    'time': entry['time'],
                    'lat': lat,
                    'lon': lon,
                    'alt': alt,
                    'altitude_reported': entry.get('altitude'),
                    'distinct': entry.get('distinct'),
                    'dof': entry.get('dof'),
                    'ecef': entry['ecef']
                })
    
    return mlat_data

def load_adsb_data(filename: str) -> Dict[str, List[Dict]]:
    """
    Lädt ADS-B GPS-Referenzpositionen aus entries.json
    """
    with open(filename, 'r') as f:
        data = json.load(f)
    
    adsb_data = {}
    
    for icao, entries in data.items():
        icao_lower = icao.lower()
        adsb_data[icao_lower] = []
        
        for entry_wrapper in entries:
            entry = entry_wrapper['entry']
            ts = entry_wrapper['ts']
            
            # Nur Entries mit GPS-Position (ADS-B)
            if entry.get('lat') and entry.get('lon') and entry.get('adsb_seen', 0) > 0:
                adsb_data[icao_lower].append({
                    'time': ts / 1000.0,  # Konvertiere ms zu Sekunden
                    'lat': entry['lat'],
                    'lon': entry['lon'],
                    'alt': entry.get('alt'),
                    'adsb_seen': entry.get('adsb_seen', 0)
                })
    
    return adsb_data

def find_closest_adsb_position(mlat_entry: Dict, adsb_entries: List[Dict], 
                                time_window: float = 5.0) -> Optional[Dict]:
    """
    Findet die zeitlich nächste ADS-B Position zu einem MLAT-Entry
    time_window: Maximale Zeitdifferenz in Sekunden
    """
    mlat_time = mlat_entry['time']
    closest = None
    min_time_diff = float('inf')
    
    for adsb in adsb_entries:
        time_diff = abs(adsb['time'] - mlat_time)
        
        if time_diff < min_time_diff and time_diff <= time_window:
            min_time_diff = time_diff
            closest = adsb
    
    return closest

def calculate_errors(mlat_data: Dict, adsb_data: Dict, time_window: float = 5.0) -> List[Dict]:
    """
    Berechnet Positionsfehler zwischen MLAT und ADS-B
    """
    errors = []
    
    for icao in mlat_data.keys():
        if icao not in adsb_data:
            continue
        
        mlat_entries = mlat_data[icao]
        adsb_entries = adsb_data[icao]
        
        for mlat in mlat_entries:
            adsb = find_closest_adsb_position(mlat, adsb_entries, time_window)
            
            if adsb:
                # Berechne horizontalen Fehler
                horizontal_error = haversine_distance(
                    mlat['lat'], mlat['lon'],
                    adsb['lat'], adsb['lon']
                )
                
                # Berechne vertikalen Fehler (wenn verfügbar)
                vertical_error = None
                if mlat['alt'] and adsb['alt']:
                    # Konvertiere Fuß zu Meter
                    adsb_alt_m = adsb['alt'] * 0.3048
                    vertical_error = abs(mlat['alt'] - adsb_alt_m)
                
                # Berechne 3D-Fehler
                error_3d = horizontal_error
                if vertical_error is not None:
                    error_3d = math.sqrt(horizontal_error**2 + vertical_error**2)
                
                time_diff = abs(mlat['time'] - adsb['time'])
                
                errors.append({
                    'icao': icao,
                    'time': mlat['time'],
                    'time_diff': time_diff,
                    'mlat_lat': mlat['lat'],
                    'mlat_lon': mlat['lon'],
                    'mlat_alt': mlat['alt'],
                    'adsb_lat': adsb['lat'],
                    'adsb_lon': adsb['lon'],
                    'adsb_alt': adsb['alt'] * 0.3048 if adsb['alt'] else None,
                    'horizontal_error': horizontal_error,
                    'vertical_error': vertical_error,
                    'error_3d': error_3d,
                    'distinct_receivers': mlat['distinct'],
                    'dof': mlat['dof']
                })
    
    return errors

def print_statistics(errors: List[Dict]):
    """
    Gibt Statistiken über die Positionsfehler aus
    """
    if not errors:
        print("Keine Fehlerberechnungen möglich (keine übereinstimmenden Positionen)")
        return
    
    print("\n" + "=" * 70)
    print("MLAT vs ADS-B Position Error Analysis")
    print("=" * 70)
    
    # Gesamt-Statistik
    h_errors = [e['horizontal_error'] for e in errors]
    v_errors = [e['vertical_error'] for e in errors if e['vertical_error'] is not None]
    e_3d = [e['error_3d'] for e in errors]
    
    #print(f"\nAnzahl Vergleiche: {len(errors)}")
    #print(f"Verschiedene Flugzeuge: {len(set(e['icao'] for e in errors))}")
    
    print(f"\n--- Horizontale Fehler ---")
    print(f"  Durchschnitt: {sum(h_errors) / len(h_errors):.1f} m")
    print(f"  Median: {sorted(h_errors)[len(h_errors) // 2]:.1f} m")
    #print(f"  Min: {min(h_errors):.1f} m")
    #print(f"  Max: {max(h_errors):.1f} m")
    print(f"  95%-Perzentil: {sorted(h_errors)[int(len(h_errors) * 0.95)]:.1f} m")
    
    if v_errors:
        print(f"\n--- Vertikale Fehler ---")
        print(f"  Durchschnitt: {sum(v_errors) / len(v_errors):.1f} m")
        print(f"  Median: {sorted(v_errors)[len(v_errors) // 2]:.1f} m")
        #print(f"  Min: {min(v_errors):.1f} m")
        #print(f"  Max: {max(v_errors):.1f} m")
    
    print(f"\n--- 3D Fehler ---")
    print(f"  Durchschnitt: {sum(e_3d) / len(e_3d):.1f} m")
    print(f"  Median: {sorted(e_3d)[len(e_3d) // 2]:.1f} m")
    
    # Statistik nach Anzahl Empfänger
    print(f"\n--- Fehler nach Anzahl distincter Empfänger ---")
    by_distinct = {}
    for e in errors:
        d = e['distinct_receivers']
        if d not in by_distinct:
            by_distinct[d] = []
        by_distinct[d].append(e['horizontal_error'])
    
    for distinct in sorted(by_distinct.keys()):
        errs = by_distinct[distinct]
        print(f"  {distinct} Empfänger: {sum(errs)/len(errs):.1f} m (n={len(errs)})")
    
    # Statistik nach DoF (Degrees of Freedom)
    print(f"\n--- Fehler nach DoF (Degrees of Freedom) ---")
    by_dof = {}
    for e in errors:
        d = e['dof']
        if d not in by_dof:
            by_dof[d] = []
        by_dof[d].append(e['horizontal_error'])
    
    for dof in sorted(by_dof.keys()):
        errs = by_dof[dof]
        print(f"  DoF {dof}: {sum(errs)/len(errs):.1f} m (n={len(errs)})")
    
    # Zeige worst cases
    print(f"\n--- Größte Fehler ---")
    worst = sorted(errors, key=lambda x: x['horizontal_error'], reverse=True)[:5]
    for i, e in enumerate(worst, 1):
        print(f"  {i}. ICAO {e['icao']}: {e['horizontal_error']:.1f} m "
              f"({e['distinct_receivers']} Empfänger, DoF={e['dof']}, "
              f"Δt={e['time_diff']:.2f}s)")
    
    print("=" * 70)

def save_detailed_results(errors: List[Dict], filename: str = "mlat_errors.json"):
    """
    Speichert detaillierte Ergebnisse als JSON
    """
    with open(filename, 'w') as f:
        json.dump(errors, f, indent=2)
    print(f"\nDetaillierte Ergebnisse gespeichert in: {filename}")

def main():
    # Dateinamen
    pseudorange_file = "workdir/pseudorange.json"
    entries_file = "extractedEntries/entries.json"
    
    # Prüfe ob Dateien existieren
    if not Path(pseudorange_file).exists():
        print(f"Fehler: {pseudorange_file} nicht gefunden!")
        return
    
    if not Path(entries_file).exists():
        print(f"Fehler: {entries_file} nicht gefunden!")
        return
    
    print("Lade MLAT-Daten (pseudorange.json)...")
    mlat_data = load_pseudorange_data(pseudorange_file)
    print(f"  → {len(mlat_data)} Flugzeuge mit MLAT-Positionen")
    
    print("Lade ADS-B-Daten (entries.json)...")
    adsb_data = load_adsb_data(entries_file)
    print(f"  → {len(adsb_data)} Flugzeuge mit ADS-B-Positionen")
    
    print("\nBerechne Positionsfehler...")
    errors = calculate_errors(mlat_data, adsb_data, time_window=5.0)
    
    if errors:
        print_statistics(errors)
        save_detailed_results(errors)
    else:
        print("\nKeine übereinstimmenden Positionen gefunden!")
        print("Mögliche Gründe:")
        print("  - Zeitfenster zu klein (aktuell: 5 Sekunden)")
        print("  - Keine gemeinsamen ICAO-Codes")
        print("  - Keine ADS-B-Positionen in entries.json")

if __name__ == "__main__":
    main()