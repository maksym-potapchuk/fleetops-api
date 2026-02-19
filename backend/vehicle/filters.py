# from rest_framework import filters
# from .models import Vehicle

# class VehicleFilter(filters.FilterSet):
#     model = filters.CharFilter(field_name="model", lookup_expr="icontains")
#     manufacturer = filters.CharFilter(field_name="manufacturer", lookup_expr="icontains")
#     year = filters.NumberFilter(field_name="year")
#     status = filters.CharFilter(field_name="status", lookup_expr="icontains")

#     class Meta:
#         model = Vehicle
#         fields = ["model", "manufacturer", "year", "status"]
