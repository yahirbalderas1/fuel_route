# Fuel Route Optimizer API & Interactive Map

A high-performance **Django REST API** and interactive map application that calculates the optimal driving route between any two locations within the USA, identifies cost-effective fuel stops along the route using real OPIS retail fuel prices, and computes the total money spent on fuel assuming a vehicle with a **500-mile maximum range** and **10 miles per gallon (MPG)** fuel economy.

Built with **Django 5.2**, using **Open Source Routing Machine (OSRM)** and **Nominatim (OpenStreetMap)** with **zero required API keys**.

---

## Key Features

- **Optimal Refueling Algorithm**:
  - Vehicle specs: **500-mile maximum range**, **10 MPG** fuel efficiency (50-gallon tank capacity).
  - Starts with a full tank (500 miles).
  - Safely schedules refueling stops (legs target 320–485 miles) so the vehicle never runs dry.
  - Searches for fuel stations within a highway corridor (up to 15 miles off the route).
  - Selects the cheapest stations in each reachable window to minimize total fuel expenditure.
  - Accurately accounts for every gallon consumed ($\text{Total Distance} / 10$) and computes total cost using actual station retail prices.
- **Fast Response Time (< 500 ms)**:
  - Pre-geocoded database of **6,626 US truck stops** from `fuel-prices-for-be-assessment.csv` bundled directly with the application.
  - Built-in spatial grid indexing for sub-millisecond corridor station queries.
  - Bundled US cities database resolves city/state locations in 0 ms with 0 external API calls.
  - Only **1 external API call** (to OSRM) needed for standard route calculations.
- **Dual Interface**:
  - **REST API** (`/api/route/`): Returns clean JSON with route summary, optimal fuel stop objects, cost, and GeoJSON `LineString`.
  - **Interactive Web Map** (`/` and `/map/`): Beautiful Leaflet.js map with route polyline, start/finish pins, numbered fuel stop markers with popups, and summary metrics dashboard.
- **Zero API Keys Required**: Completely free and open-source infrastructure.

---

## Quickstart & Installation

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.11)

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

*(Or install directly: `pip install django requests`)*

### 3. Database Migration & Data Loading
The database migrations and fuel dataset loader are ready to run:
```bash
python manage.py migrate
python manage.py load_fuel_data
```

### 4. Run the Development Server
```bash
python manage.py runserver 8000
```

Open your browser at:
- **Interactive Map UI**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **REST API Endpoint**: [http://127.0.0.1:8000/api/route/?start=New+York,NY&finish=Los+Angeles,CA](http://127.0.0.1:8000/api/route/?start=New+York,NY&finish=Los+Angeles,CA)

---

## API Documentation

### Endpoint: `GET /api/route/` or `POST /api/route/`

Calculates driving route and optimal fuel stops between two locations in the USA.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start` | string | **Yes** | — | Starting location ("City, State", address, or "lat,lon") |
| `finish` | string | **Yes** | — | Destination location ("City, State", address, or "lat,lon") |
| `max_range` | float | No | `500.0` | Maximum vehicle driving range on a full tank (miles) |
| `mpg` | float | No | `10.0` | Vehicle fuel efficiency (miles per gallon) |

#### Example GET Request
```bash
curl "http://127.0.0.1:8000/api/route/?start=New+York,NY&finish=Los+Angeles,CA"
```

#### Example POST Request
```bash
curl -X POST "http://127.0.0.1:8000/api/route/" \
  -H "Content-Type: application/json" \
  -d '{"start": "Austin, TX", "finish": "Dallas, TX"}'
```

#### Example Response
```json
{
  "status": "success",
  "query": {
    "start_input": "New York, NY",
    "finish_input": "Los Angeles, CA"
  },
  "start": {
    "name": "New York, NY",
    "latitude": 40.7128,
    "longitude": -74.006
  },
  "finish": {
    "name": "Los Angeles, CA",
    "latitude": 34.0522,
    "longitude": -118.2437
  },
  "summary": {
    "total_distance_miles": 2800.63,
    "total_duration_hours": 49.87,
    "total_fuel_gallons": 280.06,
    "total_fuel_cost_dollars": 867.36,
    "average_fuel_price_per_gallon": 3.097,
    "fuel_stops_count": 6,
    "vehicle_range_miles": 500.0,
    "vehicle_mpg": 10.0
  },
  "fuel_stops": [
    {
      "stop_number": 1,
      "opis_id": 9699,
      "truckstop_name": "SHEETZ #639",
      "address": "I-80 Exit 223",
      "city": "Youngstown",
      "state": "OH",
      "coordinates": [41.1398, -80.6843],
      "retail_price": 3.059,
      "mile_marker": 392.18,
      "leg_distance_miles": 392.18,
      "gallons_pumped": 39.22,
      "cost_dollars": 119.97
    },
    {
      "stop_number": 2,
      "opis_id": 70744,
      "truckstop_name": "CASEYS #3686",
      "address": "I-80 EXIT 81",
      "city": "Utica",
      "state": "IL",
      "coordinates": [41.3414, -89.0118],
      "retail_price": 2.969,
      "mile_marker": 854.24,
      "leg_distance_miles": 462.06,
      "gallons_pumped": 46.21,
      "cost_dollars": 137.17
    },
    {
      "stop_number": 3,
      "opis_id": 68368,
      "truckstop_name": "AKAL TRAVEL CENTER",
      "address": "I-80 EX 360",
      "city": "Waco",
      "state": "NE",
      "coordinates": [40.897, -97.4623],
      "retail_price": 2.799,
      "mile_marker": 1335.75,
      "leg_distance_miles": 481.51,
      "gallons_pumped": 48.15,
      "cost_dollars": 134.77
    },
    {
      "stop_number": 4,
      "opis_id": 71101,
      "truckstop_name": "7-ELEVEN 42279",
      "address": "I-76, Exit 39",
      "city": "Keenesburg",
      "state": "CO",
      "coordinates": [40.1086, -104.5205],
      "retail_price": 3.149,
      "mile_marker": 1739.29,
      "leg_distance_miles": 403.54,
      "gallons_pumped": 40.35,
      "cost_dollars": 127.06
    },
    {
      "stop_number": 5,
      "opis_id": 71712,
      "truckstop_name": "MAVERIK COUNTRY STORE #693",
      "address": "I-70, Exit 160 & hwy 191",
      "city": "Green River",
      "state": "UT",
      "coordinates": [38.9953, -110.1596],
      "retail_price": 3.2823,
      "mile_marker": 2121.0,
      "leg_distance_miles": 381.71,
      "gallons_pumped": 38.17,
      "cost_dollars": 125.29
    },
    {
      "stop_number": 6,
      "opis_id": 72965,
      "truckstop_name": "Maverik #674",
      "address": "I-15, Exit 45",
      "city": "North Las Vegas",
      "state": "NV",
      "coordinates": [36.1989, -115.1175],
      "retail_price": 3.2823,
      "mile_marker": 2499.46,
      "leg_distance_miles": 378.46,
      "gallons_pumped": 67.96,
      "cost_dollars": 223.08
    }
  ],
  "route_geometry": {
    "type": "LineString",
    "coordinates": [
      [-74.006, 40.7128],
      ...
    ]
  },
  "map_url": "/map/?start=New+York%2C+NY&finish=Los+Angeles%2C+CA"
}
```

---

## Optimization Methodology

1. **Route Discretization**:
   - The route is fetched from OSRM as a GeoJSON polyline.
   - Cumulative distances $d_k$ (in miles) are computed for all polyline vertices.
2. **Corridor Filtering**:
   - Route points are binned into a $0.25^\circ \times 0.25^\circ$ spatial grid.
   - All fuel stations within 15 miles of the route are identified in $\sim 25\text{ ms}$.
   - Stations within 3 miles of each other (at the same highway exit) are deduplicated, keeping the lowest retail price.
3. **Refueling Window Selection**:
   - Starting with a full tank (500 miles range), the vehicle travels until the tank is approximately 60%–95% depleted (between 300 and 485 miles).
   - In that forward window, the algorithm selects the station with the minimum retail fuel price.
   - If the remaining distance to destination is $\le 500$ miles, no further stops are needed and the vehicle proceeds directly to the destination.
   - For shorter routes ($\le 500$ miles total), the entire trip is completed on the initial tank with 0 stops required.

---

## Running Automated Tests

Run the full test suite with Django's test runner:
```bash
python manage.py test
```

All 19 tests verify:
- Coordinate parsing and US boundary validation
- Local city lookup and Nominatim geocoding fallback
- Haversine calculations and route distance scaling
- Short routes ($\le 500$ mi) with 0 stops
- Long multi-stop routes with vehicle range constraint ($\le 500$ mi per leg)
- Sum of gallons pumped equals $\text{Total Distance} / 10$
- API GET and POST endpoints, JSON validation, and error handling
- Interactive map HTML view rendering

---

## Project Structure

```
fuel_route/
├── manage.py
├── fuel-prices-for-be-assessment.csv    # Original OPIS fuel prices dataset
├── db.sqlite3                           # Pre-populated SQLite database (6,626 stations)
├── fuel_route_project/                  # Django project configuration
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── route_optimizer/                     # Main Django application
│   ├── models.py                        # FuelStation database model
│   ├── views.py                         # API and Map view handlers
│   ├── urls.py                          # Application URL routing
│   ├── data/
│   │   ├── fuel_stations_geocoded.json  # Pre-geocoded fuel stations dataset
│   │   └── us_cities_compact.json       # Compact US cities coordinates database
│   ├── services/
│   │   ├── geocoding.py                 # Fast local lookup & Nominatim geocoding
│   │   ├── routing.py                   # OSRM routing client & polyline distance tracker
│   │   └── fuel_optimizer.py            # Corridor filter & optimal refueling algorithm
│   ├── templates/
│   │   └── map.html                     # Leaflet.js interactive map interface
│   ├── management/commands/
│   │   └── load_fuel_data.py            # Management command to load stations into DB
│   └── tests/
│       ├── test_geocoding.py            # Geocoding unit tests
│       ├── test_routing.py              # Routing unit tests
│       ├── test_fuel_optimizer.py       # Fuel optimizer unit tests
│       └── test_api.py                  # API and view integration tests
└── scripts/
    └── build_geocoded_dataset.py        # Offline dataset builder script
```
