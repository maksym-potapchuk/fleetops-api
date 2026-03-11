from django.db import models

ALLOWED_INVOICE_EXTENSIONS = (".pdf", ".doc", ".docx")


class FuelType(models.TextChoices):
    GASOLINE = "GASOLINE", "Gasoline"
    DIESEL = "DIESEL", "Diesel"
    LPG = "LPG", "LPG"
    ELECTRIC = "ELECTRIC", "Electric"


class WashType(models.TextChoices):
    EXTERIOR = "EXTERIOR", "Exterior"
    INTERIOR = "INTERIOR", "Interior"
    FULL = "FULL", "Full"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    CASHLESS = "CASHLESS", "Cashless"


class PayerType(models.TextChoices):
    COMPANY = "COMPANY", "Company"
    CLIENT = "CLIENT", "Client"


class SupplierType(models.TextChoices):
    DISASSEMBLY = "DISASSEMBLY", "Disassembly"
    INDIVIDUAL = "INDIVIDUAL", "Individual"


class ApprovalStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SENT = "SENT", "Sent"
    REVIEW = "REVIEW", "Review"
    APPROVED = "APPROVED", "Approved"
