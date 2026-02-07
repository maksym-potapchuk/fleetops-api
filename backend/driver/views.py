from django.shortcuts import render
from rest_framework import viewsets
from .models import Driver
from rest_framework.permissions import IsAuthenticated
from .serializers import DriverSerializer

# Create your views here.
class DriverModelViewSet(viewsets.ModelViewSet):
    queryset=Driver.objects.all()
    serializer_class=DriverSerializer
    permission_classes=[IsAuthenticated]
    