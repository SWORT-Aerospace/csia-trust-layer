# Syncora — container image for a hosted pilot / staging.
# One image, two processes: the web server (default CMD) and the timer worker
# (`python manage.py run_dispatch_worker`). Run migrations as a release step.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN useradd --create-home --uid 10001 app

COPY requirements.txt .
# Builds behind a TLS-inspecting proxy can pass that proxy's CA bundle:
#   docker build --secret id=build_ca,src=/path/to/ca-bundle.crt .
# It is used for this pip step only and is never stored in the image.
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install -r requirements.txt

COPY . .
# collectstatic needs settings to import; these build-time values are not
# secrets and are never used at runtime.
RUN DJANGO_DEBUG=false DJANGO_SECRET_KEY=collectstatic-only DISPATCH_ALLOW_DEMO_LOGINS=false \
    DISPATCH_REDIS_URL=redis://build-only-unused:6379/0 \
    python manage.py collectstatic --noinput

USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "30", "--access-logfile", "-"]
