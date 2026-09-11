import csv
import io
import json
import os
import requests

US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
}

OVERRIDE_COORDS = {
    ('elizabethport', 'NJ'): (40.663992, -74.210701),
    ('evergreen', 'AL'): (31.433774, -86.954419),
    ('henrico', 'VA'): (37.5385, -77.3486),
    ('port wentworth', 'GA'): (32.14937, -81.16317),
    ('university park', 'IL'): (41.4442, -87.6853),
    ('saint cloud', 'MN'): (45.5579, -94.1632),
    ('saint joseph', 'MO'): (39.7674, -94.8467),
    ('saint louis', 'MO'): (38.6270, -90.1994),
    ('st louis', 'MO'): (38.6270, -90.1994),
}


def normalize_city(name: str) -> str:
    return name.strip().lower().replace(' ', '').replace('-', '').replace('.', '').replace("'", "")


def fetch_city_db():
    print("Fetching US cities database...")
    url = 'https://raw.githubusercontent.com/kelvins/US-Cities-Database/main/csv/us_cities.csv'
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    city_db = {}
    reader = csv.DictReader(io.StringIO(r.text))
    for row in reader:
        c_raw = row['CITY'].strip().lower()
        state = row['STATE_CODE'].strip().upper()
        lat, lon = float(row['LATITUDE']), float(row['LONGITUDE'])

        city_db[(c_raw, state)] = (lat, lon)
        city_db[(normalize_city(c_raw), state)] = (lat, lon)

    # Apply overrides
    for (city, state), coords in OVERRIDE_COORDS.items():
        city_db[(city, state)] = coords
        city_db[(normalize_city(city), state)] = coords

    print(f"Loaded {len(city_db)} city lookup entries.")
    return city_db


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, 'fuel-prices-for-be-assessment.csv')
    out_path = os.path.join(base_dir, 'route_optimizer', 'data', 'fuel_stations_geocoded.json')

    city_db = fetch_city_db()

    print(f"Reading {csv_path}...")
    stations_by_id = {}
    skipped_non_us = 0
    unmatched_count = 0

    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            state = row['State'].strip().upper()
            if state not in US_STATES:
                skipped_non_us += 1
                continue

            city_raw = row['City'].strip().lower()
            city_norm = normalize_city(city_raw)
            coords = city_db.get((city_raw, state)) or city_db.get((city_norm, state))

            if not coords:
                unmatched_count += 1
                print(f"Warning: Could not geocode {row['City']}, {state}")
                continue

            opis_id = int(row['OPIS Truckstop ID'])
            price = round(float(row['Retail Price']), 4)
            name = row['Truckstop Name'].strip()
            address = row['Address'].strip()
            city_display = row['City'].strip()

            # Keep lowest price if truck stop has multiple entries
            if opis_id not in stations_by_id or price < stations_by_id[opis_id]['retail_price']:
                stations_by_id[opis_id] = {
                    'opis_id': opis_id,
                    'name': name,
                    'address': address,
                    'city': city_display,
                    'state': state,
                    'retail_price': price,
                    'latitude': coords[0],
                    'longitude': coords[1],
                }

    stations_list = list(stations_by_id.values())
    print(f"Processed {len(stations_list)} unique US stations (skipped {skipped_non_us} non-US, {unmatched_count} unmatched).")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(stations_list, f, indent=2)

    print(f"Saved geocoded stations to {out_path} ({os.path.getsize(out_path)} bytes)")

    # Also save compact city dictionary: key = "city, state", value = [lat, lon]
    city_out_path = os.path.join(base_dir, 'route_optimizer', 'data', 'us_cities_compact.json')
    compact_dict = {f"{c}, {s}": [round(coords[0], 5), round(coords[1], 5)] for (c, s), coords in city_db.items() if len(s) == 2}
    with open(city_out_path, 'w', encoding='utf-8') as f:
        json.dump(compact_dict, f, separators=(',', ':'))
    print(f"Saved compact US cities to {city_out_path} ({os.path.getsize(city_out_path)} bytes)")


if __name__ == '__main__':
    main()
