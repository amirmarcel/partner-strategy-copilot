from django.urls import path

from . import views

urlpatterns = [
    path("gaps/", views.GapListCreateView.as_view(), name="gap-list-create"),
    path("gaps/<int:pk>/", views.GapDetailView.as_view(), name="gap-detail"),
    path("gaps/<int:pk>/approve/", views.GapApproveView.as_view(), name="gap-approve"),
]
