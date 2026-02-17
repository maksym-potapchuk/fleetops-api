from django.shortcuts import render
from rest_framework import viewsets
from .models import (
    FleetService,
    ServiceHistory,
    FleetVehicleRegulation,
    FleetVehicleRegulationNotification,
)
from rest_framework.permissions import IsAuthenticated
from .serializers import FleetServiceSerializer


class FleetServiceViewSet(viewsets.ModelViewSet):
    queryset = FleetService.objects.all()
    serializer_class = FleetServiceSerializer
    permission_classes = [IsAuthenticated]
    