import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from route_optimizer.models import FuelStation


class Command(BaseCommand):
    help = 'Load geocoded fuel station data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path to fuel_stations_geocoded.json file (defaults to route_optimizer/data/fuel_stations_geocoded.json)',
            default=None
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing fuel stations before loading'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        if not file_path:
            file_path = os.path.join(
                settings.BASE_DIR,
                'route_optimizer',
                'data',
                'fuel_stations_geocoded.json'
            )

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"Data file not found at {file_path}"))
            return

        if options['clear']:
            deleted_count, _ = FuelStation.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing stations."))

        self.stdout.write(f"Reading {file_path}...")
        with open(file_path, 'r', encoding='utf-8') as f:
            stations_data = json.load(f)

        self.stdout.write(f"Parsed {len(stations_data)} station records. Importing to database...")

        # Bulk insert
        station_objects = [
            FuelStation(
                opis_id=item['opis_id'],
                name=item['name'],
                address=item['address'],
                city=item['city'],
                state=item['state'],
                retail_price=item['retail_price'],
                latitude=item['latitude'],
                longitude=item['longitude'],
            )
            for item in stations_data
        ]

        FuelStation.objects.bulk_create(
            station_objects,
            batch_size=1000,
            ignore_conflicts=True
        )

        total_count = FuelStation.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Successfully loaded fuel data! Total stations in database: {total_count}"))
