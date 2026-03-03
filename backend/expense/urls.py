from django.urls import path

from . import views

urlpatterns = [
    path(
        "categories/",
        views.ExpenseCategoryListView.as_view(),
        name="expense-categories",
    ),
    path("", views.ExpenseListCreateView.as_view(), name="expense-list-create"),
    path(
        "<uuid:pk>/",
        views.ExpenseRetrieveUpdateDestroyView.as_view(),
        name="expense-detail",
    ),
]
