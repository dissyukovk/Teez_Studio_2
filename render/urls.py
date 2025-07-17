from django.urls import path
from . import views

urlpatterns = [
    #ретушеры
    path('start-check/', views.StartCheck, name='start-check'),
    path('retoucher-render-list/', views.RetoucherRenderList.as_view(), name='retoucher-render-list'),
    path('retoucher-render-edit-list/', views.RetoucherRenderEditList.as_view(), name='retoucher-render-edit-list'),
    path('update-render/<render_id>/', views.UpdateRender, name='update-render'),
    path('update-render-edit/<render_id>/', views.UpdateRenderEdit, name='update-render-edit'),
    path('mass-update-retouchlinks/', views.MassUpdateRetouchPhotosLink, name='mass-update-retouchlinks'),
    path('send-for-check/', views.SendForCheck, name='send-for-check'),

    #старший ретушер
    path('senior-render-list/', views.SeniorRenderCheckList.as_view(), name='senior-render-list'),
    path('senior-to-edit-render/', views.SeniorToEditRender, name='senior-to-edit-render'),
    path('senior_retoucher_stats/<str:date_from>/<str:date_to>/', views.SeniorRetoucherStats, name='senior_retoucher_stats'),
    path('senior_return_to_render_list/', views.SeniorReturnToRenderList, name='senior_return_to_render_list'),
    path('list_retouchers_with_status3/', views.list_retouchers_with_status3, name='list_retouchers_with_status3'),
    path('senior-update-render/<render_id>/', views.SeniorUpdateRender, name='update-render'),

    # -- работа с отклоненными рендерами -- 
    path('moderation/rejects-to-retouch/', views.ModerationUploadRejectToRetouch.as_view(), name='moderation-rejects-to-retouch'),
    #правки ретушеру
    path('moderation-uploads/<int:pk>/send-for-edits/', views.SendModerationUploadForEdits.as_view(), name='moderation-upload-send-for-edits'),
    #вернуть в очередь рендера
    path('moderation-uploads/<int:pk>/return-to-render-queue/', views.ReturnModerationUploadToRenderQueue.as_view(), name='moderation-upload-return-to-render'),
    #вернуть в очередь загрузки
    path('moderation-uploads/<int:pk>/mark-fixed-return-to-upload/', views.MarkModerationUploadFixed.as_view(), name='moderation-upload-mark-fixed'),
    #на съемку
    path('moderation-uploads/<int:pk>/send-for-reshoot/', views.SendModerationUploadForReshoot.as_view(), name='moderation-upload-send-for-reshoot'),
    
    #Модераторы
    path('moderator-upload-start/', views.ModeratorUploadStart, name='moderator-upload-start'),
    path('moderation_upload_result/', views.ModerationUploadResult, name='moderation_upload_result'),
    path('moderation_upload_edit/', views.ModerationUploadEdit, name='moderation_upload_edit'),
    path('moderator_list_by_date/<str:date_str>/', views.ModeratorListByDate, name='moderator_list_by_date'),
    path('moderator_list_by_date/', views.ModeratorListByDate, name='moderator_list_by_date'),
    path('moderator-studio-upload-start/', views.ModerationStudioUploadStart, name='moderator-studio-upload-start'),
    path('moderator_studio_list/', views.ModerationStudioUploadListView.as_view(), name='moderator_studio_list'),
    path('moderation_studio_upload_result/', views.ModerationStudioUploadResult, name='moderation_studio_upload_result'),
    path('moderation_studio_upload_edit/', views.ModerationStudioUploadEdit, name='moderation_studio_upload_edit'),
    path('MyUploadStat/<str:date_from>/<str:date_to>/', views.MyUploadStatView.as_view(), name='my_upload_stat'),

    #Старший модератор
    path('senior_moderation_stats/<str:date_from>/<str:date_to>/', views.SeniorModerationStats, name='senior_moderation_stats'),

    #Забрать отклоненные рендеры
    path('RejectToShooting/<int:count>/', views.get_rejected_photos_for_shooting, name='get_rejected_photos'),

    #заблокировать рендеры
    path('block-for-retouch/', views.BlockProductsForRetouch.as_view(), name='block-products-for-retouch'),

    #Инфо по загрузкам
    path('uploaded_sku_data/', views.UploadedModerationDataView.as_view(), name='uploaded-moderation-data'),
    path('recent_uploaded_sku_data/<int:days_ago>/', views.RecentUploadedModerationDataView.as_view(), name='recent_uploaded_data_days'),

    #All renders
    path('all-renders/', views.AllRenderListView.as_view(), name='all-renders-list'),

    ## Среднее время незаказанных
    path('average-check-time/', views.get_render_check_stats, name='get_average_render_check_time'),
]
