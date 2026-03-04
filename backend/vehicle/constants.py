from django.db import models


class ManufacturerChoices(models.TextChoices):
    TOYOTA = "Toyota", "Toyota"
    FORD = "Ford", "Ford"
    HONDA = "Honda", "Honda"
    CHEVROLET = "Chevrolet", "Chevrolet"
    BMW = "BMW", "BMW"
    LEXUS = "Lexus", "Lexus"
    AUDI = "Audi", "Audi"


class FuelType(models.TextChoices):
    GASOLINE = "GASOLINE", "Gasoline"
    DIESEL = "DIESEL", "Diesel"
    LPG = "LPG", "LPG"
    LPG_GASOLINE = "LPG_GASOLINE", "LPG + Gasoline"
    ELECTRIC = "ELECTRIC", "Electric"
    HYBRID = "HYBRID", "Hybrid"


class VehicleStatus(models.TextChoices):
    CTO = "CTO", "CTO"
    FOCUS = "FOCUS", "Focus"
    CLEANING = "CLEANING", "Cleaning"
    PREPARATION = "PREPARATION", "Preparation"
    READY = "READY", "Ready"
    LEASING = "LEASING", "Leasing"
    RENT = "RENT", "Rent"
    SELLING = "SELLING", "Selling"
    SOLD = "SOLD", "Sold"
