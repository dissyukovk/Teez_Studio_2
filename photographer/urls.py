from django.urls import path
from . import views

urlpatterns = [
    #Получение списка заявок со статусом 2
    path('strequests2/', views.STRequest2ListView.as_view(), name='st-request2-list'),
    #Получение списка заявок со статусом 3
    path('strequests3/', views.STRequest3ListView.as_view(), name='st-request3-list'),
    #Получение списка заявок со статусом 5
    path('strequests5/', views.STRequest5ListView.as_view(), name='st-request5-list'),
    #Получение списка фотографов
    path('photographers/working/', views.WorkingPhotographerListView.as_view(), name='working-photographer-list'),
    #Получение списка ассистентов
    path('assistants/all/', views.AssistantsListView.as_view(), name='assistatns-list'),
    #Назначение фотографа
    path('st-requests/assign-photographer/', views.AssignPhotographerView.as_view(), name='assign-photographer'),
    #убрать фотографа
    path('st-requests/remove-photographer/', views.RemovePhotographerView.as_view(), name='remove-photographer'),
    #1 - Назначить ассистента
    path('st-requests/assign-assistant/', views.AssignAssistantView.as_view(), name='assign-assistant'),
    #2 - Сброс ассистента
    path('st-requests/remove-assistant/', views.RemoveAssistantView.as_view(), name='remove-assistant'),
    #3 - Nofoto - Поставить Без фото
    path('st-requests/product/<str:barcode>/nofoto/', views.NoFotoView.as_view(), name='product-nofoto'),
    #4 - Получение детальной информации об одной заявке STRequest (e.g., /api/v1/st-requests/REQ123/)
    path('st-requests/<str:request_number>/', views.STRequestDetailView.as_view(), name='st-request-detail'),
    #5 - Изменить STRequestProduct.photo_status
    path('st-requests/product/update-photo-status/', views.UpdateSTRequestProductPhotoStatusView.as_view(), name='update-product-photo-status'),
    #6 - Изменить STRequestProduct.sphoto_status
    path('st-requests/product/update-sphoto-status/', views.UpdateSTRequestProductSPhotoStatusView.as_view(), name='update-product-sphoto-status'),
    #7 - Вернуть заявку на съемку
    path('st-requests/return-to-shooting/', views.ReturnSTRequestToShootingView.as_view(), name='return-st-request-to-shooting-func'),
    #ИЗменение ph_to_rt_comment
    path('update-ph-to-rt-comment/', views.UpdateSTRequestProductPhToRtCommentView.as_view(), name='update-ph-to-rt-comment'),
]
