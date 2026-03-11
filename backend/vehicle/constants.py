from django.db import models


class ManufacturerChoices(models.TextChoices):
    TOYOTA = "Toyota", "Toyota"
    FORD = "Ford", "Ford"
    HONDA = "Honda", "Honda"
    CHEVROLET = "Chevrolet", "Chevrolet"
    BMW = "BMW", "BMW"
    LEXUS = "Lexus", "Lexus"
    AUDI = "Audi", "Audi"
    TESLA = "Tesla", "Tesla"


class FuelType(models.TextChoices):
    GASOLINE = "GASOLINE", "Gasoline"
    DIESEL = "DIESEL", "Diesel"
    LPG = "LPG", "LPG"
    LPG_GASOLINE = "LPG_GASOLINE", "LPG + Gasoline"
    ELECTRIC = "ELECTRIC", "Electric"
    HYBRID = "HYBRID", "Hybrid"


class VehicleStatus(models.TextChoices):
    AUCTION = "AUCTION", "Auction Selection"
    FOCUS = "FOCUS", "Focus"
    GAS_INSTALL = "GAS_INSTALL", "Gas Installation"
    SERVICE = "SERVICE", "Service"
    CLEANING = "CLEANING", "Cleaning"
    PRE_DELIVERY = "PRE_DELIVERY", "Pre-delivery"
    READY = "READY", "Ready for Delivery"
    RENT = "RENT", "Rent"
    LEASING = "LEASING", "Leasing"
    SELLING = "SELLING", "Report for Sale"
    SOLD = "SOLD", "Sold"
