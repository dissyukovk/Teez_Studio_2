from django.urls import path
from . import views

urlpatterns = [
    #Получение листа заявок на съемку
    path('strequest-list/', views.PhotographerSTRequestsStatus3List.as_view(), name='strequest-photographer-status-3'),
    #Детали заявки
    path('strequest/<str:request_number>/', views.STRequestDetail.as_view(), name='strequest-detail'),
    #Начало съемки
    path('shooting_start/<str:request_number>/<str:barcode>/', views.shooting_start, name='shooting-start'),
    #результаты съемки
    path(
        'shooting_results/<str:request_number>/<str:barcode>/',
        views.shooting_results,
        name='shooting-results'
    ),
    #обновить photo_status
    path(
        'photo_status/<str:request_number>/<str:barcode>/',
        views.update_photo_status,
        name='update-photo-status'
    ),
    #Обновить ph_to_ret_comment
    path(
        'ph_to_rt_comment/<str:request_number>/<str:barcode>/',
        views.update_ph_to_rt_comment,
        name='update-ph-to-rt-comment'
    ),
    #Получить PhotoTimes
    path(
        'photo_times/<str:request_number>/',
        views.photo_times_list,
        name='photo-times-list'
    ),

    # --- Список браков по съемке ---
    path('shooting-defects/', views.ShootingDefectsList.as_view(), name='shooting-defects-list'),
    
    # --- Статистика фотографа ---
    path(
        'photographer-stats/<str:start_date_str>/<str:end_date_str>/',
        views.PhotographerStats.as_view(),
        name='photographer-stats'
    ),

    #ОБНОВЛЕНИЕ
    path('updates/latest/', views.latest_release, name='latest_release'),
    path('updates/<str:version>/<str:platform>/', views.update_server, name='update_server'),
]
