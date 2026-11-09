from django.urls import path

from .views import manage, public, setup, staff

app_name = "web"

urlpatterns = [
    # Public website
    path("", public.home, name="home"),
    path("healthz", public.healthz, name="healthz"),
    path("demo/", public.demo, name="demo"),
    path("demo/start/", public.demo_start, name="demo_start"),
    path("demo/floor/", public.demo_floor, name="demo_floor"),
    path("demo/preset/", public.demo_preset, name="demo_preset"),
    path("signin/", public.signin, name="signin"),
    path("signout/", public.signout, name="signout"),
    path("pair/", public.pair, name="pair"),
    # Setup wizard
    path("setup/", setup.start, name="setup"),
    path("setup/<int:setup_id>/<slug:step>/", setup.step, name="setup_step"),
    # Staff app (every URL names the acting membership; ownership is checked)
    path("app/", public.app_home, name="app_home"),
    path("app/<int:sid>/", staff.home, name="staff_home"),
    path("app/<int:sid>/act/<slug:action>/", staff.act, name="act"),
    path("app/<int:sid>/live/<slug:name>/", staff.live, name="live"),
    path("app/<int:sid>/manage/", manage.now, name="manage_now"),
    path("app/<int:sid>/manage/floor/", manage.floor, name="manage_floor"),
    path("app/<int:sid>/manage/staff/", manage.staff_page, name="manage_staff"),
    path("app/<int:sid>/manage/rules/", manage.rules, name="manage_rules"),
    path("app/<int:sid>/manage/activity/", manage.activity, name="manage_activity"),
    path("app/<int:sid>/manage/integrations/", manage.integrations, name="manage_integrations"),
    path("app/<int:sid>/manage/integrations/test-event/", manage.integrations_test_event, name="manage_integrations_test"),
    path("app/<int:sid>/<slug:name>/", staff.screen, name="screen"),
]
