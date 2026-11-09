from django.conf import settings


def product_flags(request):
    return {
        "DEMO_ENABLED": settings.DISPATCH_DEMO_ENABLED,
        "SETUP_OPEN": settings.DISPATCH_SETUP_OPEN,
    }
