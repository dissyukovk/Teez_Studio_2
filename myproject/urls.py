from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from django.conf import settings
from django.views.static import serve
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('ft/', include('ftback.urls')),
    path('st/', include('stockman.urls')),
    path('mn/', include('manager.urls')),
    path('okz/', include('okz.urls')),
    path('auto/', include('auto.urls')),
    path('rd/', include('render.urls')),
    path('ph/', include('photographer.urls')),
    path('srt/', include('SeniorRetoucher.urls')),
    path('rt/', include('retoucher.urls')),
    path('el/', include('ElectronAPI.urls')),
    path('public/', include('guest.urls')),
    path('bot/', include('telegram_bot.urls')),
    path('api/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns.append(re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}))

