# filters.py
import django_filters
from .models import FleetVehicleRegulationSchema

class FleetVehicleRegulationSchemaFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(lookup_expr='icontains')
    is_default = django_filters.BooleanFilter()                 
    min_km = django_filters.NumberFilter(                       
        field_name='items__every_km', 
        lookup_expr='gte'
    )
    max_km = django_filters.NumberFilter(                      
        field_name='items__every_km', 
        lookup_expr='lte'
    )

    class Meta:
        model = FleetVehicleRegulationSchema
        fields = ['title', 'is_default', 'min_km', 'max_km']