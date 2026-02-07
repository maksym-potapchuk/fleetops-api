from django.db import models
import uuid
# Create your models here.
class Driver(models.Model):
    id=models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number=models.CharField(max_length=15, unique=True)
    has_vehicle=models.BooleanField(default=False)
    is_active_driver=models.BooleanField(default=False)
    last_active_at=models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)