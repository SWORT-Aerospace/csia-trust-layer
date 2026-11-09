from django.urls import include, path

urlpatterns = [path("", include("web.urls"))]

handler403 = "web.views.errors.forbidden"
handler404 = "web.views.errors.not_found"
