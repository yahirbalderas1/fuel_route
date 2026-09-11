import json
import urllib.parse
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from route_optimizer.services.geocoding import geocode_location
from route_optimizer.services.routing import RoutingService
from route_optimizer.services.fuel_optimizer import FuelOptimizerService


def calculate_fuel_route(start_query: str, finish_query: str, max_range: float = 500.0, mpg: float = 10.0):
    """
    Core business logic:
    1. Geocode start and finish locations (validating within USA)
    2. Obtain driving route from OSRM
    3. Calculate optimal refueling stops and cost based on OPIS fuel prices
    """
    start_loc = geocode_location(start_query)
    finish_loc = geocode_location(finish_query)

    route_data = RoutingService.get_route(
        {'lat': start_loc['lat'], 'lon': start_loc['lon']},
        {'lat': finish_loc['lat'], 'lon': finish_loc['lon']}
    )

    if not route_data.get('success'):
        raise ValueError(f"Failed to generate route between {start_query} and {finish_query}")

    optimizer_result = FuelOptimizerService.optimize(
        route_data=route_data,
        max_range=max_range,
        mpg=mpg
    )

    encoded_start = urllib.parse.quote_plus(start_query)
    encoded_finish = urllib.parse.quote_plus(finish_query)
    map_url = f"/map/?start={encoded_start}&finish={encoded_finish}"

    return {
        'status': 'success',
        'query': {
            'start_input': start_query,
            'finish_input': finish_query
        },
        'start': {
            'name': start_loc['name'],
            'latitude': start_loc['lat'],
            'longitude': start_loc['lon']
        },
        'finish': {
            'name': finish_loc['name'],
            'latitude': finish_loc['lat'],
            'longitude': finish_loc['lon']
        },
        'summary': {
            'total_distance_miles': route_data['total_distance_miles'],
            'total_duration_hours': route_data['total_duration_hours'],
            'total_fuel_gallons': optimizer_result['total_fuel_gallons'],
            'total_fuel_cost_dollars': optimizer_result['total_fuel_cost_dollars'],
            'average_fuel_price_per_gallon': optimizer_result['average_price_per_gallon'],
            'fuel_stops_count': optimizer_result['fuel_stops_count'],
            'vehicle_range_miles': max_range,
            'vehicle_mpg': mpg
        },
        'fuel_stops': optimizer_result['fuel_stops'],
        'route_geometry': {
            'type': 'LineString',
            'coordinates': route_data['coordinates']  # GeoJSON format [[lon, lat], ...]
        },
        'map_url': map_url
    }


@csrf_exempt
def api_route_plan(request):
    """
    API endpoint:
    GET /api/route/?start=New+York,NY&finish=Los+Angeles,CA
    POST /api/route/ with JSON body {"start": "New York, NY", "finish": "Los Angeles, CA"}
    """
    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8'))
            start = body.get('start')
            finish = body.get('finish')
            max_range = float(body.get('max_range', 500.0))
            mpg = float(body.get('mpg', 10.0))
        except (json.JSONDecodeError, ValueError) as e:
            return JsonResponse({'status': 'error', 'message': f'Invalid JSON payload: {e}'}, status=400)
    else:
        start = request.GET.get('start')
        finish = request.GET.get('finish')
        try:
            max_range = float(request.GET.get('max_range', 500.0))
            mpg = float(request.GET.get('mpg', 10.0))
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'max_range and mpg must be numeric'}, status=400)

    if not start or not finish:
        return JsonResponse({
            'status': 'error',
            'message': "Missing required parameters: both 'start' and 'finish' locations within the USA must be provided."
        }, status=400)

    try:
        data = calculate_fuel_route(start, finish, max_range=max_range, mpg=mpg)
        return JsonResponse(data)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': f'Internal error calculating route: {exc}'}, status=500)


def map_view(request):
    """
    Web View:
    Renders an interactive Leaflet.js map with route polyline, start/finish markers, and fuel stops.
    Accessible at / and /map/
    """
    start = request.GET.get('start', '')
    finish = request.GET.get('finish', '')

    route_json = None
    error_message = None

    if start and finish:
        try:
            result = calculate_fuel_route(start, finish)
            route_json = json.dumps(result)
        except Exception as exc:
            error_message = str(exc)

    return render(request, 'map.html', {
        'start': start,
        'finish': finish,
        'route_json': route_json,
        'error_message': error_message
    })
