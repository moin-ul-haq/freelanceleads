from django.urls import path

from .views import GenerateSiteView, SiteDeleteView, SiteListView

# API routes — mounted at /api/sites/ (the public page is routed in root urls)
urlpatterns = [
    path("generate/", GenerateSiteView.as_view(), name="sites-generate"),
    path("", SiteListView.as_view(), name="sites-list"),
    path("<int:pk>/", SiteDeleteView.as_view(), name="sites-delete"),
]
