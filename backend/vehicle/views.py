from django.shortcuts import render
from .serializers import VehicleSerializer
from rest_framework.permissions import IsAuthenticated
from .models import Vehicle
from rest_framework import generics
from django_filters.rest_framework import DjangoFilterBackend

class VehicleListCreateView(generics.ListCreateAPIView):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['model', 'manufacturer', 'year', 'status']
    pagination_class = None
    http_method_names = ['get', 'post']


class VehicleRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'put', 'patch', 'delete']
