from django.db import models


class FuelStation(models.Model):
    """Represents a truck stop / fuel station with retail diesel price and GPS coordinates."""
    opis_id = models.IntegerField(unique=True, db_index=True, help_text="OPIS Truckstop ID")
    name = models.CharField(max_length=255, help_text="Truckstop Name")
    address = models.CharField(max_length=255, blank=True, help_text="Street address or highway exit")
    city = models.CharField(max_length=100, db_index=True)
    state = models.CharField(max_length=2, db_index=True)
    retail_price = models.DecimalField(max_digits=7, decimal_places=4, db_index=True, help_text="Retail price per gallon in USD")
    latitude = models.FloatField(db_index=True)
    longitude = models.FloatField(db_index=True)

    class Meta:
        ordering = ['state', 'city', 'retail_price']
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['state', 'retail_price']),
        ]

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) - ${self.retail_price:.3f}/gal"
