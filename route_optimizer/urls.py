from django.urls import path
from route_optimizer.views import api_route_plan, map_view

urlpatterns = [
    path('', map_view, name='home_map'),
    path('map/', map_view, name='map_view'),
    path('api/route/', api_route_plan, name='api_route_plan'),
]
