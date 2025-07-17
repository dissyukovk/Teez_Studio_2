from django.views import View
from django.shortcuts import render
from django.utils import timezone
from django.http import JsonResponse
from django.db import transaction
from django.db.models import (
    Subquery,
    OuterRef,
    Min,
    Q,
    Count,
    Value,
    CharField,
    F,
    ExpressionWrapper,
    DurationField,
    Sum,
    Case,
    When,
    IntegerField,
    Prefetch,
    Avg
    )
from django.db.models.functions import Concat, TruncDate, Cast
from django.views.decorators.http import require_GET
from django_q.tasks import async_task
from datetime import datetime, timedelta, time
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework import status, filters, generics
from collections import OrderedDict, defaultdict
from core.models import (
    Product,
    ProductCategory,
    ProductOperation,
    ProductMoveStatus,
    ProductOperationTypes,
    Order,
    OrderProduct,
    OrderStatus,
    STRequest,
    STRequestProduct,
    STRequestPhotoTime,
    RetouchRequest,
    RetouchRequestProduct,
    RetouchStatus,
    SRetouchStatus,
    Nofoto,
    Blocked_Shops,
    Blocked_Barcode,
    UserProfile
    )
from render.models import Product as RenderProduct, Render, RetouchStatus as RenderRetouchStatus, SeniorRetouchStatus as RenderSeniorRetouchStatus, ModerationUpload, ModerationStudioUpload
from .serializers import (
    STRequestSerializer,
    STRequestDetailSerializer,
    RetouchRequestSerializer,
    RetouchRequestDetailSerializer
    )
from .pagination import StandardResultsSetPagination

# Проверка штрихкодов перед заказом
class CreateOrderCheckBarcodes(APIView):
    def post(self, request, *args, **kwargs):
        # Ожидаем, что в теле запроса придёт JSON с массивом штрихкодов в поле "barcodes"
        barcodes = request.data.get('barcodes')
        if not isinstance(barcodes, list):
            return Response(
                {'error': 'Неверный формат данных. Ожидается массив штрихкодов.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Выбираем штрихкоды, которые присутствуют в базе данных
        found_barcodes = set(
            Product.objects.filter(barcode__in=barcodes).values_list('barcode', flat=True)
        )
        
        # Определяем отсутствующие штрихкоды
        missing_barcodes = [barcode for barcode in barcodes if barcode not in found_barcodes]
        
        # Проверяем, присутствуют ли штрихкоды в заказах со статусом 2 или 3 через модель OrderProduct
        order_products = OrderProduct.objects.filter(
            product__barcode__in=barcodes,
            order__status__id__in=[2, 3]
        ).select_related('order', 'product')
        
        barcodes_in_order = []
        for op in order_products:
            barcodes_in_order.append({
                "barcode": op.product.barcode,
                "order_number": op.order.OrderNumber
            })
        
        # Если есть либо отсутствующие штрихкоды, либо штрихкоды уже привязанные к заказам со статусом 2 или 3,
        # возвращаем ошибку с соответствующими данными
        if missing_barcodes or barcodes_in_order:
            error_response = {'error': 'Найдены отсутствующие штрихкоды или штрихкоды уже находятся в заказе со статусом 2 или 3'}
            if missing_barcodes:
                error_response['missing_barcodes'] = missing_barcodes
            if barcodes_in_order:
                error_response['barcodes_in_order'] = barcodes_in_order
            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'message': 'Все штрихкоды найдены'}, status=status.HTTP_200_OK)

#Создание заказа
class CreateOrderEnd(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        barcodes_input = request.data.get('barcodes') # Получаем исходный список штрихкодов

        if not isinstance(barcodes_input, list):
            return Response(
                {'error': 'Неверный формат данных. Ожидается массив штрихкодов.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # --- НАЧАЛО ОБРАБОТКИ ШТРИХКОДОВ (дополнение нулями и валидация) ---
        processed_barcodes_list = []
        # Опционально: можно собирать информацию о пропущенных/невалидных штрихкодах
        # processing_feedback = [] 

        for bc_item in barcodes_input:
            temp_barcode_str = None
            if isinstance(bc_item, (int, float)): # Обработка числовых входов (например, из Excel)
                temp_barcode_str = str(int(bc_item)) # Сначала в int для удаления .0, потом в строку
            elif isinstance(bc_item, str):
                temp_barcode_str = bc_item.strip() # Удаляем пробелы по краям для строк
            else:
                # Пропускаем элементы, которые не являются строкой или числом
                # processing_feedback.append(f"Пропущен элемент '{bc_item}': неверный тип ({type(bc_item)}).")
                continue 

            if not temp_barcode_str:
                # Пропускаем пустые строки после обработки
                # processing_feedback.append("Пропущен пустой штрихкод.")
                continue 

            if not temp_barcode_str.isdigit():
                # Пропускаем штрихкоды, содержащие нецифровые символы
                # processing_feedback.append(f"Пропущен штрихкод '{temp_barcode_str}': должен содержать только цифры.")
                continue 

            if len(temp_barcode_str) > 13:
                # Пропускаем штрихкоды, длина которых изначально больше 13 символов
                # processing_feedback.append(f"Пропущен штрихкод '{temp_barcode_str}': длина ({len(temp_barcode_str)}) превышает 13 символов.")
                continue 

            # Если штрихкод прошел все проверки (строка, не пустой, только цифры, длина <= 13),
            # дополняем его нулями спереди до 13 символов.
            processed_barcodes_list.append(temp_barcode_str.zfill(13))
        
        # Используем обработанный список штрихкодов для всех последующих операций.
        # Остальной код использует переменную 'barcodes'.
        barcodes = list(dict.fromkeys(processed_barcodes_list))
        # --- КОНЕЦ ОБРАБОТКИ ШТРИХКОДОВ ---

        # Если после обработки список штрихкодов пуст, существующая логика ниже должна это обработать
        # (например, initial_valid_barcodes будет пуст, что приведет к соответствующему Response).

        # --- Фильтрация штрихкодов --- (Остальной код без изменений)
        blocked_shop_ids = list(Blocked_Shops.objects.values_list('shop_id', flat=True))
        blocked_barcodes_set = set(Blocked_Barcode.objects.values_list('barcode', flat=True))

        initial_valid_barcodes = []
        products_map = {}

        # Оптимизация: Получаем все продукты одним запросом, используя обработанные 'barcodes'
        if barcodes: # Выполняем запрос только если есть штрихкоды после обработки
            products_query = Product.objects.filter(barcode__in=barcodes).select_related('category')
            for product in products_query:
                products_map[product.barcode] = product
        else: # Если список barcodes пуст после обработки
            products_query = Product.objects.none() # Пустой QuerySet


        for barcode in barcodes: # Итерация по обработанным и отфильтрованным штрихкодам
            product = products_map.get(barcode)
            if not product:
                continue

            if product.category and product.category.IsBlocked:
                continue

            if product.seller in blocked_shop_ids:
                continue

            if barcode in blocked_barcodes_set:
                continue
            
            # В модели Product поле move_status является ForeignKey на ProductMoveStatus.
            # Сравнение должно идти по ID или по объекту статуса.
            # product.move_status_id == 3 (если move_status_id существует и доступно)
            # или product.move_status.id == 3 (если move_status не None)
            if product.move_status and product.move_status.id == 3: # Предполагаем, что id - это числовой идентификатор статуса
                continue

            initial_valid_barcodes.append(barcode)

        if not initial_valid_barcodes:
                 return Response(
                    {'error': 'Нет доступных штрихкодов после первичной фильтрации (возможно, все штрихкоды были невалидны или отфильтрованы).'},
                    status=status.HTTP_400_BAD_REQUEST
                 )

        order_blocked_barcodes = set(OrderProduct.objects.filter(
            product__barcode__in=initial_valid_barcodes,
            order__status__in=[2, 3] # Предполагаем, что 2 и 3 - это ID статусов заказа
        ).values_list('product__barcode', flat=True))

        valid_barcodes = [
            barcode for barcode in initial_valid_barcodes
            if barcode not in order_blocked_barcodes
        ]

        if not valid_barcodes:
            return Response(
                {'error': 'Нет доступных штрихкодов для создания заказа после фильтрации.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_priority = request.data.get('priority', False)
        if is_priority:
            Product.objects.filter(barcode__in=valid_barcodes).update(priority=True)

        last_order = Order.objects.order_by('-OrderNumber').first()
        next_order_number = (last_order.OrderNumber + 1) if last_order and last_order.OrderNumber is not None else 1

        try:
            order_status_obj = OrderStatus.objects.get(id=2)
            product_move_status_obj = ProductMoveStatus.objects.get(id=2)
            operation_type_obj = ProductOperationTypes.objects.get(id=2)
        except OrderStatus.DoesNotExist:
            return Response({'error': 'OrderStatus с id=2 не найден.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ProductMoveStatus.DoesNotExist:
            return Response({'error': 'ProductMoveStatus с id=2 не найден.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ProductOperationTypes.DoesNotExist:
            return Response({'error': 'ProductOperationTypes с id=2 не найден.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        created_order_numbers = []
        chunk_size = 30
        
        # Получаем все валидные объекты Product один раз перед циклом по чанкам
        # valid_products_dict используется далее, так что это название сохраним
        valid_products_dict = {p.barcode: p for p in Product.objects.filter(barcode__in=valid_barcodes)}


        for i in range(0, len(valid_barcodes), chunk_size):
            chunk_barcodes = valid_barcodes[i:i+chunk_size]
            
            # Используем transaction.atomic для гарантии целостности при создании заказа и связанных объектов
            with transaction.atomic():
                order = Order.objects.create(
                    OrderNumber=next_order_number,
                    date=timezone.now(),
                    creator=request.user,
                    status=order_status_obj
                )
                created_order_numbers.append(next_order_number)
                next_order_number += 1

                order_products_in_chunk = []
                operations_in_chunk = []
                
                products_to_update_status_in_chunk = [] # Для обновления статуса конкретных продуктов

                for barcode_in_chunk in chunk_barcodes: # Изменено имя переменной для ясности
                    product = valid_products_dict.get(barcode_in_chunk)
                    if product:
                        products_to_update_status_in_chunk.append(product.id) # Собираем ID для обновления

                        order_products_in_chunk.append(OrderProduct(order=order, product=product))
                        
                        comment_text = product.cell if product.cell is not None else "" # Убедимся, что comment_text не None
                        operations_in_chunk.append(ProductOperation(
                            product=product,
                            operation_type=operation_type_obj,
                            user=request.user,
                            comment=comment_text,
                            ProductStatus=product.ProductStatus,
                            ProductModerationStatus=product.ProductModerationStatus,
                            PhotoModerationStatus=product.PhotoModerationStatus,
                            SKUStatus=product.SKUStatus
                        ))

                if order_products_in_chunk:
                    OrderProduct.objects.bulk_create(order_products_in_chunk)

                if operations_in_chunk:
                    ProductOperation.objects.bulk_create(operations_in_chunk)
        
        # Обновление статуса движения для ВСЕХ обработанных валидных продуктов ОДНИМ запросом после всех чанков
        if valid_barcodes: # Убедимся, что список не пуст
             Product.objects.filter(barcode__in=valid_barcodes).update(move_status=product_move_status_obj)


        if created_order_numbers:
            first_order_number = created_order_numbers[0]
            last_order_number = created_order_numbers[-1]
            orders_range = f"{first_order_number} - {last_order_number}" if len(created_order_numbers) > 1 else str(first_order_number)
            sku_count = len(valid_barcodes)
            order_type_text = "приоритетные заказы" if is_priority else "заказы"
            message_text = (
                f"Созданы {order_type_text} {orders_range}\n\n"
                f"Количество SKU - {sku_count}"
            )
            chat_id="-1002453118841"
            message_thread_id = 9
            try:
                async_task(
                    'telegram_bot.tasks.send_message_task', # Путь к нашей функции
                    chat_id=chat_id,
                    text=message_text,
                    message_thread_id=message_thread_id
                )
                print(f"TELEGRAM MOCK SEND: {message_text}") 
            except Exception as e:
                print(f"Error sending Telegram message: {e}")


            return Response(
                {'orders_range': orders_range},
                status=status.HTTP_201_CREATED
            )
        else:
             # Этот случай может возникнуть, если valid_barcodes был не пуст, но ни одного заказа не создалось (маловероятно при текущей логике)
             # Или если valid_barcodes изначально был пуст и проверки выше это не отловили (что тоже маловероятно)
             return Response(
                 {'error': 'Не удалось создать заказы, или нет подходящих товаров для обработки.'},
                 status=status.HTTP_400_BAD_REQUEST # Изменено на 400, так как это скорее проблема данных
             )

#Массовая загрузка штрихкодов
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manager_bulk_upload(request):
    data = request.data.get('data')
    if not isinstance(data, list):
        return Response(
            {"error": "Неверный формат данных. Ожидается массив объектов."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    errors = []
    valid_data = []
    
    # Обрабатываем каждую строку данных
    for index, row in enumerate(data, start=1):
        row_errors = []
        
        required_fields = ["barcode", "name", "category_id", "seller", "in_stock_sum", "cell"]
        # Проверка наличия всех необходимых полей
        for field in required_fields:
            if field not in row:
                row_errors.append(f"Отсутствует поле '{field}'")
        
        if row_errors: # Если основные поля отсутствуют, нет смысла продолжать с этой строкой
            errors.append(f"Строка {index}: " + ", ".join(row_errors))
            continue

        # Переменные для хранения валидированных значений
        processed_barcode = None
        validated_name = None
        validated_category = None
        validated_seller = None
        validated_in_stock_sum = None
        # cell_from_row будет использоваться для cell

        # 1. Валидация и обработка штрихкода (barcode) - ИЗМЕНЕННАЯ ЛОГИКА
        barcode_input = row.get('barcode') 
        
        if barcode_input is None:
            row_errors.append("Поле 'barcode' не может быть null.")
        else:
            # Конвертируем в строку, так как из Excel может прийти число (например, если штрихкод 0123, Excel может передать 123)
            barcode_str_candidate = str(barcode_input).strip()

            if not barcode_str_candidate:
                row_errors.append("Поле 'barcode' не должно быть пустым после обработки.")
            elif not barcode_str_candidate.isdigit():
                row_errors.append(f"Поле 'barcode' ('{barcode_str_candidate}') должно содержать только цифры.")
            elif len(barcode_str_candidate) > 13:
                # Ошибка, если исходный штрихкод (до дополнения нулями) уже длиннее 13 символов
                row_errors.append(f"Длина исходного штрихкода '{barcode_str_candidate}' ({len(barcode_str_candidate)}) не должна превышать 13 цифр.")
            else:
                # Если длина <= 13 и состоит из цифр, дополняем ведущими нулями до 13 символов
                processed_barcode = barcode_str_candidate.zfill(13)
        
        # 2. Валидация наименования (name) - оригинальная логика
        name_from_row = row.get('name')
        if not isinstance(name_from_row, str) or not name_from_row.strip():
            row_errors.append("Поле 'name' должно быть непустой строкой")
        else:
            validated_name = name_from_row.strip()
        
        # 3. Валидация id категории (category_id) и проверка существования - оригинальная логика
        category_id_from_row = row.get('category_id')
        try:
            category_id = int(category_id_from_row)
            try:
                validated_category = ProductCategory.objects.get(id=category_id)
            except ProductCategory.DoesNotExist:
                row_errors.append(f"Категория с id {category_id} не существует")
        except (ValueError, TypeError):
            row_errors.append("Поле 'category_id' должно быть числом")
        
        # 4. Валидация поля seller - оригинальная логика
        seller_from_row = row.get('seller')
        try:
            validated_seller = int(seller_from_row)
        except (ValueError, TypeError):
            row_errors.append("Поле 'seller' должно быть числом")
        
        # 5. Валидация количества (in_stock_sum) - оригинальная логика
        in_stock_sum_from_row = row.get('in_stock_sum')
        try:
            validated_in_stock_sum = int(in_stock_sum_from_row)
        except (ValueError, TypeError):
            row_errors.append("Поле 'in_stock_sum' должно быть числом")
        
        # 6. Валидация поля ячейки (cell) - оригинальная логика
        cell_from_row = row.get('cell')
        if not isinstance(cell_from_row, str):
            # Эта оригинальная проверка добавит ошибку, если cell_from_row будет None или числом.
            # Оставляем как есть, согласно требованию "не трогать остальной функционал".
            row_errors.append("Поле 'cell' должно быть строкой")
        # Значение для 'cell' будет отформатировано при добавлении в valid_data, как в оригинале

        if row_errors:
            errors.append(f"Строка {index}: " + ", ".join(row_errors))
        else:
            # Если ошибок на этой строке нет, добавляем данные в список для загрузки
            # Используем оригинальную логику для cell при добавлении в словарь
            cell_value_for_dict = cell_from_row.strip() if isinstance(cell_from_row, str) else cell_from_row
            
            valid_data.append({
                'barcode': processed_barcode,      # Используем обработанный штрихкод
                'name': validated_name,
                'category': validated_category,
                'seller': validated_seller,
                'in_stock_sum': validated_in_stock_sum,
                'cell': cell_value_for_dict,
            })
    
    if errors:
        return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)
    
    # Если все данные валидны – создаем или обновляем продукты
    created_count = 0
    updated_count = 0
    for item in valid_data:
        product, created = Product.objects.get_or_create(
            barcode=item['barcode'], # Поиск по обработанному (дополненному) штрихкоду
            defaults={
                'name': item['name'],
                'category': item['category'],
                'seller': item['seller'],
                'in_stock_sum': item['in_stock_sum'],
                'cell': item['cell'],
                # 'move_status' and other fields with defaults/null=True will use their defaults
                # or can be added here if they come from the input file and are validated.
            }
        )
        if not created:
            # Обновляем данные существующего продукта
            product.name = item['name']
            product.category = item['category']
            product.seller = item['seller']
            product.in_stock_sum = item['in_stock_sum']
            product.cell = item['cell']
            product.save()
            updated_count += 1
        else:
            created_count += 1
            
    return Response({
        "message": f"Данные успешно загружены. Создано: {created_count}, Обновлено: {updated_count}."
    }, status=status.HTTP_200_OK)

#Статистика фс
def FSAllstats(request):
    # Получаем даты из GET-параметров (формат: ГГГГ-MM-DD)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if not start_date_str or not end_date_str:
        return JsonResponse({'error': 'Укажите start_date и end_date в формате ГГГГ-MM-DD.'}, status=400)

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Неверный формат дат. Используйте ГГГГ-MM-DD.'}, status=400)

    if start_date > end_date:
        return JsonResponse({'error': 'start_date должна быть меньше или равна end_date.'}, status=400)

    # Границы диапазона по времени
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    # 1. Агрегация "Заказано" – считаем OrderProduct по дате заказа
    orders_agg = OrderProduct.objects.filter(
        order__date__range=(start_dt, end_dt)
    ).annotate(day=TruncDate('order__date')
    ).values('day').annotate(count=Count('id'))
    orders_dict = {item['day']: item['count'] for item in orders_agg}

    # 2. Агрегация операций (Принято, Отправлено, Брак товара) по ProductOperation
    ops_agg = ProductOperation.objects.filter(
        date__range=(start_dt, end_dt)
    ).annotate(day=TruncDate('date')
    ).values('day').annotate(
        accepted=Sum(Case(When(operation_type__id=3, then=1), default=0, output_field=IntegerField())),
        sent=Sum(Case(When(operation_type__id=4, then=1), default=0, output_field=IntegerField())),
        defective_product=Sum(Case(When(operation_type__id__in=[25, 30], then=1), default=0, output_field=IntegerField()))
    )
    ops_dict = {}
    for item in ops_agg:
        ops_dict[item['day']] = {
            'Принято': item['accepted'] or 0,
            'Отправлено': item['sent'] or 0,
            'Брак товара': item['defective_product'] or 0
        }

    # 3. Агрегация "Сфотографировано" – напрямую по STRequestProduct
    st_agg = STRequestProduct.objects.filter(
        request__photo_date__range=(start_dt, end_dt),
        photo_status__id__in=[1, 2, 25],
        sphoto_status__id=1
    ).annotate(day=TruncDate('request__photo_date')
    ).values('day').annotate(total_photographed=Count('id'))
    st_dict = {item['day']: item['total_photographed'] for item in st_agg}

    # 4. Агрегация "Отретушировано" и "Брак по съемке" – напрямую по RetouchRequestProduct
    retouch_agg = RetouchRequestProduct.objects.filter(
        retouch_request__retouch_date__range=(start_dt, end_dt)
    ).annotate(day=TruncDate('retouch_request__retouch_date')
    ).values('day').annotate(
        total_retouched=Count('id', filter=Q(retouch_status__id=2, sretouch_status__id=1)),
        total_defective_shooting=Count('id', filter=Q(retouch_status__id=3, sretouch_status__id=1))
    )
    retouch_dict = {}
    for item in retouch_agg:
        retouch_dict[item['day']] = {
            'Отретушировано': item['total_retouched'] or 0,
            'Брак по съемке': item['total_defective_shooting'] or 0
        }

    # --- Новые агрегации ---

    # 5. Агрегация "Сделано рендеров" (status=6) и "Отклонено на рендерах" (status=7) - из Render по CheckTimeStart
    renders_agg = Render.objects.filter(
        CheckTimeStart__range=(start_dt, end_dt)
    ).annotate(day=TruncDate('CheckTimeStart')
    ).values('day').annotate(
        renders_done=Count('id', filter=Q(RetouchStatus__id=6)),
        renders_rejected=Count('id', filter=Q(RetouchStatus__id=7))
    )
    renders_dict = {}
    for item in renders_agg:
        renders_dict[item['day']] = {
            'Сделано рендеров': item['renders_done'] or 0,
            'Отклонено на рендерах': item['renders_rejected'] or 0
        }

    # 6. Агрегация "Загружено рендеров" - из ModerationUpload по UploadTimeStart (status=2)
    moderation_upload_agg = ModerationUpload.objects.filter(
        UploadTimeStart__range=(start_dt, end_dt),
        UploadStatus__id=2
    ).annotate(day=TruncDate('UploadTimeStart')
    ).values('day').annotate(count=Count('id'))
    moderation_upload_dict = {item['day']: item['count'] for item in moderation_upload_agg}

    # 7. Агрегация "Загружено фото от фс" - из ModerationStudioUpload по UploadTimeStart (status=2)
    moderation_studio_upload_agg = ModerationStudioUpload.objects.filter(
        UploadTimeStart__range=(start_dt, end_dt),
        UploadStatus__id=2
    ).annotate(day=TruncDate('UploadTimeStart')
    ).values('day').annotate(count=Count('id'))
    moderation_studio_upload_dict = {item['day']: item['count'] for item in moderation_studio_upload_agg}

    # --- Конец новых агрегаций ---


    # 8. Формирование итогового словаря с данными для каждого дня
    result = {}
    current_date = start_date
    while current_date <= end_date:
        day_key = current_date  # объект date

        # Получаем данные по рендерам для текущего дня
        render_stats = renders_dict.get(day_key, {})

        result[str(current_date)] = {
            # Старые метрики
            'Заказано': orders_dict.get(day_key, 0),
            'Принято': ops_dict.get(day_key, {}).get('Принято', 0),
            'Отправлено': ops_dict.get(day_key, {}).get('Отправлено', 0),
            'Брак товара': ops_dict.get(day_key, {}).get('Брак товара', 0),
            'Сфотографировано': st_dict.get(day_key, 0),
            'Отретушировано': retouch_dict.get(day_key, {}).get('Отретушировано', 0),
            'Брак по съемке': retouch_dict.get(day_key, {}).get('Брак по съемке', 0),

            # Новые метрики
            'Сделано рендеров': render_stats.get('Сделано рендеров', 0),
            'Отклонено на рендерах': render_stats.get('Отклонено на рендерах', 0),
            'Загружено рендеров': moderation_upload_dict.get(day_key, 0),
            'Загружено фото от фс': moderation_studio_upload_dict.get(day_key, 0),
        }
        current_date += timedelta(days=1)

    return JsonResponse(result)

#производительность по фотографам
class PhotographersStatistic(View):
    def get(self, request, *args, **kwargs):
        # Получаем даты из GET-параметров
        date_from_str = request.GET.get('date_from')
        date_to_str = request.GET.get('date_to')
        
        # Удаляем лишние пробелы, если они есть
        if date_from_str:
            date_from_str = date_from_str.strip()
        if date_to_str:
            date_to_str = date_to_str.strip()
        
        # Выводим полученные значения для отладки
        print("Получены параметры:", "date_from_str =", repr(date_from_str), ", date_to_str =", repr(date_to_str))
        
        try:
            date_from = datetime.strptime(date_from_str, '%d.%m.%Y')
            date_to = datetime.strptime(date_to_str, '%d.%m.%Y')
        except Exception as e:
            print("Ошибка преобразования даты:", e)
            return JsonResponse({'error': 'Неверный формат дат. Используйте дд.мм.гггг'}, status=400)

        # Устанавливаем время начала и конца дня
        date_from = date_from.replace(hour=0, minute=0, second=0)
        date_to = date_to.replace(hour=23, minute=59, second=59)

        # Фильтруем STRequest по диапазону photo_date и наличию фотографа
        qs = STRequest.objects.filter(
            photo_date__range=(date_from, date_to),
            photographer__isnull=False
        )

        # Аннотируем каждый STRequest количеством связанных STRequestProduct,
        # где photo_status в [1, 2, 25] и sphoto_status равен 1.
        qs = qs.annotate(
            products_count=Count(
                'strequestproduct',
                filter=Q(strequestproduct__photo_status__id__in=[1, 2, 25]) &
                       Q(strequestproduct__sphoto_status__id=1)
            )
        )

        # Словари для хранения результатов по датам и итоговых значений
        result = {}
        total_counts = {}

        for req in qs:
            # Форматируем дату в строку dd.mm.yyyy
            date_key = req.photo_date.strftime('%d.%m.%Y')
            # Получаем имя фотографа: FirstName+LastName, если пусто – используем username
            photographer_name = f"{req.photographer.first_name} {req.photographer.last_name}".strip()
            if not photographer_name:
                photographer_name = req.photographer.username

            # Инициализируем вложенный словарь для данной даты, если необходимо
            if date_key not in result:
                result[date_key] = {}
            # Накапливаем количество для каждого фотографа по дате
            result[date_key][photographer_name] = result[date_key].get(photographer_name, 0) + req.products_count
            # Обновляем общий итог по фотографу
            total_counts[photographer_name] = total_counts.get(photographer_name, 0) + req.products_count

        # Добавляем итоговый результат
        result['Total'] = total_counts

        # Сортируем словарь по ключам (датам) и оставляем ключ "Total" в конце
        ordered_result = OrderedDict()
        # Сначала сортируем ключи, исключая 'Total'
        day_keys = sorted(
            [key for key in result.keys() if key != 'Total'],
            key=lambda date_str: datetime.strptime(date_str, '%d.%m.%Y')
        )
        for date_key in day_keys:
            ordered_result[date_key] = result[date_key]
        ordered_result['Total'] = result['Total']

        return JsonResponse(ordered_result)

#Очередь ФС
@require_GET
def get_current_queues(request):
    # --- Существующий функционал (без изменений) ---
    # Очередь созданных заказов: Order со статусом 2
    created_orders = Order.objects.filter(status__id=2)
    created_orders_count = created_orders.count()
    created_orders_products_count = OrderProduct.objects.filter(order__in=created_orders).count()

    # Очередь заказов на сборке: Order со статусом 3
    assembly_orders = Order.objects.filter(status__id=3)
    assembly_orders_count = assembly_orders.count()
    assembly_orders_products_count = OrderProduct.objects.filter(order__in=assembly_orders).count()

    # Очередь на съемку: STRequest со статусом 2
    shooting_requests_qs = STRequest.objects.filter(status__id=2)
    shooting_requests_count = shooting_requests_qs.count()
    shooting_requests_products_count = STRequestProduct.objects.filter(request__in=shooting_requests_qs).count()

    # Очередь на ретушь: STRequestProduct с photo_status=1, sphoto_status=1 и OnRetouch=False
    # !! Убедитесь, что модель STRequestProduct и поле OnRetouch существуют !!
    try:
        retouch_queue_count = STRequestProduct.objects.filter(
            photo_status__id=1,
            sphoto_status__id=1,
            OnRetouch=False # Проверьте актуальность этого поля
        ).count()
    except AttributeError: # Пример обработки, если поле OnRetouch отсутствует
        print("Warning: Field 'OnRetouch' not found on STRequestProduct model.")
        retouch_queue_count = 0 # Или другое значение по умолчанию

    # Очередь на проверку фото:
    # STRequestProduct: photo_status IN (1, 2, 25) AND sphoto_status != 1
    photo_check_products_qs = STRequestProduct.objects.filter(
        photo_status_id__in=[1, 2, 25]
    ).exclude(
        sphoto_status_id__in=[1, 2, 3] # Исключаем статусы 1, 2, 3
    )
    photo_check_products_count = photo_check_products_qs.count()
    # Считаем уникальные STRequest, связанные с этими продуктами
    photo_check_requests_count = photo_check_products_qs.values('request_id').distinct().count()

    # Очередь на проверку ретуши:
    # RetouchRequestProduct: retouch_status = 2 AND (sretouch_status IS NULL OR sretouch_status = 0)
    retouch_check_products_qs = RetouchRequestProduct.objects.filter(
        Q(retouch_status_id=2) &
        (Q(sretouch_status_id__isnull=True) | Q(sretouch_status_id=0))
    )
    retouch_check_products_count = retouch_check_products_qs.count()
    # Считаем уникальные RetouchRequest, связанные с этими продуктами
    retouch_check_requests_count = retouch_check_products_qs.values('retouch_request_id').distinct().count()

    # Очередь рендеры:
    # render.Product: PhotoModerationStatus IN ('Отклонено', 'На модерации'), IsOnRender=False, IsRetouchBlock=False, WMSQuantity > 0
    render_queue_count = RenderProduct.objects.filter(
        PhotoModerationStatus="Отклонено",
        IsOnRender=False,
        IsRetouchBlock=False,
        # WMSQuantity__gt=0
    ).count()

    # Очередь на загрузку рендеров:
    # Render: RetouchStatus=6, RetouchSeniorStatus=1, IsOnUpload=false
    render_upload_queue_count = Render.objects.filter(
        RetouchStatus_id=6,      # Используем _id для ForeignKey
        RetouchSeniorStatus_id=1,# Используем _id для ForeignKey
        IsOnUpload=False
    ).count()

    # Очередь на загрузку фото от фс:
    # RetouchRequestProduct: retouch_status=2, sretouch_status=1, IsOnUpload=False
    # !! Убедитесь, что модель RetouchRequestProduct и поле IsOnUpload существуют !!
    try:
        fs_photo_upload_queue_count = RetouchRequestProduct.objects.filter(
            retouch_status_id=2,
            sretouch_status_id=1,
            IsOnUpload=False # Проверьте актуальность этого поля
        ).count()
    except AttributeError: # Пример обработки, если поле IsOnUpload отсутствует
        print("Warning: Field 'IsOnUpload' not found on RetouchRequestProduct model.")
        fs_photo_upload_queue_count = 0 # Или другое значение по умолчанию

    # --- Новый функционал: Реальная очередь на съемку ---
    # Определяем ID статусов RenderCheckResult, которые означают необходимость пересъемки
    rejected_check_result_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 50]

    photo_moderation_statuses = ["Отклонено"]
    
    blocked_shop_ids = Blocked_Shops.objects.values_list('shop_id', flat=True)
    blocked_category_ids = ProductCategory.objects.filter(IsBlocked=True).values_list('id', flat=True)
    blocked_barcodes = Blocked_Barcode.objects.values_list('barcode', flat=True)

    # Считаем количество уникальных продуктов (RenderProduct), которые:
    # 1. Не находятся в заказе (IsOnOrder=False).
    # 2. Имеют хотя бы одну связанную запись Render, у которой CheckResult ID
    #    находится в списке rejected_check_result_ids.
    
    real_shooting_queue_count = RenderProduct.objects.filter(
        IsOnOrder=False, # Фильтр по полю самого продукта
        WMSQuantity__gt=0,
        PhotoModerationStatus__in=photo_moderation_statuses,
        render__CheckResult__id__in=rejected_check_result_ids
    ).exclude(
        ShopID__in=blocked_shop_ids
    ).exclude(
        CategoryID__in=blocked_category_ids
    ).exclude(
        Barcode__in=blocked_barcodes
    ).distinct().count() # Считаем только уникальные продукты

    # --- Формирование ответа ---
    data = {
        # --- Существующие ключи ---
        "created_orders": {
            "orders_count": created_orders_count,
            "products_count": created_orders_products_count,
        },
        "assembly_orders": {
            "orders_count": assembly_orders_count,
            "products_count": assembly_orders_products_count,
        },
        "shooting_requests": {
            "requests_count": shooting_requests_count,
            "products_count": shooting_requests_products_count,
        },
        "retouch_queue": {
            "count": retouch_queue_count
        },
        "photo_check_queue": {
             "requests_count": photo_check_requests_count,
             "products_count": photo_check_products_count,
        },
        "retouch_check_queue": {
            "requests_count": retouch_check_requests_count,
            "products_count": retouch_check_products_count,
        },
        "render_queue": {
            "count": render_queue_count
        },
        "render_upload_queue": {
            "count": render_upload_queue_count
        },
        "fs_photo_upload_queue": {
            "count": fs_photo_upload_queue_count
        },
        # --- Добавленный ключ для новой очереди ---
        "real_shooting_queue": {
             "count": real_shooting_queue_count
        }
    }

    return JsonResponse(data)

#Лист заявок на съемку
class STRequestListView(ListAPIView):
    serializer_class = STRequestSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = [
        'RequestNumber',
        'status__name',
        'creation_date',
        'stockman_full_name',
        'photo_date',
        'photographer_full_name',
        'total_products',
        'count_priority',
        'count_info'
    ]
    ordering = ['-RequestNumber']  # значение по умолчанию

    def get_queryset(self):
        qs = STRequest.objects.all()
        # Фильтрация по номеру заявки (массив)
        request_numbers = self.request.query_params.getlist('request_number')
        if request_numbers:
            q_filter = Q()
            for num in request_numbers:
                q_filter |= Q(RequestNumber__icontains=num)
            qs = qs.filter(q_filter)

        # Фильтрация по штрихкоду (через связь с Product через STRequestProduct)
        barcodes = self.request.query_params.getlist('barcode')
        if barcodes:
            # Разбиваем каждую строку на отдельные штрихкоды и объединяем в один список
            barcode_list = []
            for code in barcodes:
                barcode_list.extend(code.split(','))
            # Убираем лишние пробелы, если они есть
            barcode_list = [c.strip() for c in barcode_list if c.strip()]
            if barcode_list:
                q_filter = Q()
                for code in barcode_list:
                    q_filter |= Q(strequestproduct__product__barcode__icontains=code)
                qs = qs.filter(q_filter)


        # Фильтрация по наименованию (через поле Product.name)
        names = self.request.query_params.getlist('name')
        if names:
            q_filter = Q()
            for n in names:
                q_filter |= Q(strequestproduct__product__name__icontains=n)
            qs = qs.filter(q_filter)

        # Фильтрация по датам создания и фото (формат dd.mm.YYYY)
        creation_date_from = self.request.query_params.get('creation_date_from')
        creation_date_to = self.request.query_params.get('creation_date_to')
        if creation_date_from and creation_date_to:
            try:
                from_date = datetime.strptime(creation_date_from, '%d.%m.%Y').replace(hour=0, minute=0, second=0)
                to_date = datetime.strptime(creation_date_to, '%d.%m.%Y').replace(hour=23, minute=59, second=59)
                qs = qs.filter(creation_date__range=(from_date, to_date))
            except ValueError:
                pass

        photo_date_from = self.request.query_params.get('photo_date_from')
        photo_date_to = self.request.query_params.get('photo_date_to')
        if photo_date_from and photo_date_to:
            try:
                from_date = datetime.strptime(photo_date_from, '%d.%m.%Y').replace(hour=0, minute=0, second=0)
                to_date = datetime.strptime(photo_date_to, '%d.%m.%Y').replace(hour=23, minute=59, second=59)
                qs = qs.filter(photo_date__range=(from_date, to_date))
            except ValueError:
                pass

        # Фильтрация по ID категории
        category_ids = self.request.query_params.getlist('category_ids')
        if category_ids:
            qs = qs.filter(strequestproduct__product__category__id__in=category_ids)

        # Фильтрация по статусу
        status_ids = self.request.query_params.get('status_ids')
        if status_ids:
            status_ids_list = [int(s) for s in status_ids.split(',') if s.strip().isdigit()]
            qs = qs.filter(status__id__in=status_ids_list)

        # Фильтрация по наличию приоритетных товаров
        has_priority = self.request.query_params.get('has_priority')
        if has_priority is not None:
            if has_priority.lower() in ['true', '1']:
                qs = qs.filter(strequestproduct__product__priority=True)
            elif has_priority.lower() in ['false', '0']:
                qs = qs.exclude(strequestproduct__product__priority=True)

        # Фильтрация по наличию инфо
        has_info = self.request.query_params.get('has_info')
        if has_info is not None:
            if has_info.lower() in ['true', '1']:
                qs = qs.filter(strequestproduct__product__info__isnull=False).exclude(strequestproduct__product__info='')
            elif has_info.lower() in ['false', '0']:
                qs = qs.filter(Q(strequestproduct__product__info__isnull=True) | Q(strequestproduct__product__info=''))

        # Аннотации для подсчёта товаров
        qs = qs.annotate(
            total_products=Count('strequestproduct', distinct=True),
            count_priority=Count('strequestproduct', filter=Q(strequestproduct__product__priority=True), distinct=True),
            count_photo=Count('strequestproduct', filter=Q(strequestproduct__photo_status__id__in=[1, 2, 25]), distinct=True),
            count_checked=Count('strequestproduct', filter=Q(strequestproduct__sphoto_status__id=1), distinct=True),
            count_info=Count('strequestproduct', filter=Q(strequestproduct__product__info__isnull=False) & ~Q(strequestproduct__product__info=''), distinct=True)
        )

        # Аннотации для сортировки по ФИО
        qs = qs.annotate(
            stockman_full_name=Concat('stockman__first_name', Value(' '), 'stockman__last_name', output_field=CharField()),
            photographer_full_name=Concat('photographer__first_name', Value(' '), 'photographer__last_name', output_field=CharField())
        )

        return qs

#детали заявки на съемку
class STRequestDetailView(RetrieveAPIView):
    serializer_class = STRequestDetailSerializer
    lookup_field = 'RequestNumber'
    lookup_url_kwarg = 'requestnumber'

    def get_queryset(self):
        qs = STRequest.objects.all()
        qs = qs.annotate(
            total_products=Count('strequestproduct', distinct=True),
            count_priority=Count('strequestproduct', filter=Q(strequestproduct__product__priority=True), distinct=True),
            count_photo=Count('strequestproduct', filter=Q(strequestproduct__photo_status__id__in=[1, 2, 25]), distinct=True),
            count_checked=Count('strequestproduct', filter=Q(strequestproduct__sphoto_status__id=1), distinct=True),
            count_info=Count('strequestproduct', filter=Q(strequestproduct__product__info__isnull=False) & ~Q(strequestproduct__product__info=''), distinct=True)
        )
        qs = qs.annotate(
            stockman_full_name=Concat('stockman__first_name', Value(' '), 'stockman__last_name', output_field=CharField()),
            photographer_full_name=Concat('photographer__first_name', Value(' '), 'photographer__last_name', output_field=CharField())
        )
        return qs

#лист заявок на ретушь
class RetouchRequestList(generics.ListAPIView):
    serializer_class = RetouchRequestSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        qs = RetouchRequest.objects.all()

        # --- Фильтры (ваш код) ---
        request_numbers = self.request.query_params.getlist('request_numbers')
        if request_numbers:
            q_obj = Q()
            for num in request_numbers:
                q_obj |= Q(RequestNumber__icontains=num)
            qs = qs.filter(q_obj)

        barcodes = self.request.query_params.getlist('barcode')
        if barcodes:
            # Разбиваем каждую строку на отдельные штрихкоды и объединяем в один список
            barcode_list = []
            for code in barcodes:
                barcode_list.extend(code.split(','))
            barcode_list = [c.strip() for c in barcode_list if c.strip()]
            if barcode_list:
                q_filter = Q()
                for code in barcode_list:
                    q_filter |= Q(retouch_products__st_request_product__product__barcode__icontains=code)
                qs = qs.filter(q_filter)

        creation_date_from = self.request.query_params.get('creation_date_from')
        creation_date_to = self.request.query_params.get('creation_date_to')
        date_format = "%d.%m.%Y"
        if creation_date_from:
            try:
                dt_from = datetime.strptime(creation_date_from, date_format)
                dt_from = datetime.combine(dt_from.date(), time.min)
                qs = qs.filter(creation_date__gte=dt_from)
            except ValueError:
                pass
        if creation_date_to:
            try:
                dt_to = datetime.strptime(creation_date_to, date_format)
                dt_to = datetime.combine(dt_to.date(), time.max)
                qs = qs.filter(creation_date__lte=dt_to)
            except ValueError:
                pass

        retouch_date_from = self.request.query_params.get('retouch_date_from')
        retouch_date_to = self.request.query_params.get('retouch_date_to')
        if retouch_date_from:
            try:
                dt_from = datetime.strptime(retouch_date_from, date_format)
                dt_from = datetime.combine(dt_from.date(), time.min)
                qs = qs.filter(retouch_date__gte=dt_from)
            except ValueError:
                pass
        if retouch_date_to:
            try:
                dt_to = datetime.strptime(retouch_date_to, date_format)
                dt_to = datetime.combine(dt_to.date(), time.max)
                qs = qs.filter(retouch_date__lte=dt_to)
            except ValueError:
                pass

        statuses = self.request.query_params.getlist('statuses')
        if statuses:
            qs = qs.filter(status__id__in=statuses)

        # --- Аннотации для подсчёта товаров ---
        qs = qs.annotate(
            products_count=Count('retouch_products', distinct=True),
            priority_products_count=Count(
                'retouch_products',
                filter=Q(retouch_products__st_request_product__product__priority=True),
                distinct=True
            ),
            # --- Добавляем аннотацию для сортировки по времени ---
            retouch_time_seconds=ExpressionWrapper(
                F('retouch_date') - F('creation_date'),
                output_field=DurationField()
            )
        )

        # --- Обработка параметров сортировки ---
        ordering = self.request.query_params.getlist('ordering')
        if ordering:
            # Мы хотим заменить "retouch_time" на "retouch_time_seconds"
            updated_ordering = []
            for field in ordering:
                sign = ''
                # Проверяем, нет ли у поля префикса "-"
                if field.startswith('-'):
                    sign = '-'
                    field = field[1:]
                # Если пользователь указал "retouch_time", заменяем на "retouch_time_seconds"
                if field == 'retouch_time':
                    field = 'retouch_time_seconds'
                # Можно добавить другие проверки, если нужно
                updated_ordering.append(sign + field)

            qs = qs.order_by(*updated_ordering)
        else:
            qs = qs.order_by('-creation_date')

        return qs

#Детали заявки на ретушь
class RetouchRequestDetail(generics.RetrieveAPIView):
    serializer_class = RetouchRequestDetailSerializer
    lookup_field = 'RequestNumber'
    queryset = RetouchRequest.objects.all()

    def get_object(self):
        obj = super().get_object()
        # Вычисляем количество товаров и количество приоритетных товаров
        obj.products_count = obj.retouch_products.count()
        obj.priority_products_count = obj.retouch_products.filter(st_request_product__product__priority=True).count()
        return obj

#Статистика товароведов
class ProductOperationStatsView(View):
    def get(self, request):
        date_from_str = request.GET.get('date_from')
        date_to_str = request.GET.get('date_to')

        if not date_from_str or not date_to_str:
            return JsonResponse({'error': 'Параметры date_from и date_to обязательны'}, status=400)

        try:
            # Парсим дату из строки
            date_from = datetime.strptime(date_from_str, '%d.%m.%Y').date()
            date_to = datetime.strptime(date_to_str, '%d.%m.%Y').date()
        except ValueError:
            return JsonResponse({'error': 'Неверный формат даты. Используйте дд.мм.гггг'}, status=400)

        # Задаём временной интервал: от 00:00:00 первого дня до 23:59:59 последнего дня
        start_datetime = datetime.combine(date_from, time.min)
        end_datetime = datetime.combine(date_to, time.max)

        # Фильтруем операции по дате и по типам (3 и 4)
        operations = ProductOperation.objects.filter(
            date__range=(start_datetime, end_datetime),
            operation_type__id__in=[3, 4]
        ).select_related('user', 'operation_type')

        # Результат будет иметь следующую структуру:
        # {
        #    "12.03.2025": {
        #         "Иван Иванов": {"Принято": 30, "Отправлено": 20, "Итого": 50},
        #         "Петр Петров": {"Принято": 30, "Отправлено": 30, "Итого": 60}
        #    },
        #    "13.03.2025": { ... },
        #    "Итого": {
        #         "Иван Иванов": {"Принято": X, "Отправлено": Y, "Итого": Z},
        #         "Петр Петров": { ... }
        #    }
        # }
        data = {}
        overall = {}

        for op in operations:
            # Форматируем дату операции
            date_key = op.date.strftime('%d.%m.%Y')

            # Формируем имя пользователя
            if op.user:
                username = f"{op.user.first_name} {op.user.last_name}"
            else:
                username = "Unknown User"

            # Инициализируем вложенную структуру для дня
            if date_key not in data:
                data[date_key] = {}
            if username not in data[date_key]:
                data[date_key][username] = {'Принято': 0, 'Отправлено': 0, 'Итого': 0}

            # Инициализируем общие итоги для пользователя
            if username not in overall:
                overall[username] = {'Принято': 0, 'Отправлено': 0, 'Итого': 0}

            # Подсчёт: если тип операции равен 3 – "Принято", если 4 – "Отправлено"
            if op.operation_type_id == 3:
                data[date_key][username]['Принято'] += 1
                overall[username]['Принято'] += 1
            elif op.operation_type_id == 4:
                data[date_key][username]['Отправлено'] += 1
                overall[username]['Отправлено'] += 1

            # Подсчитываем общее количество для дня и общего итога
            data[date_key][username]['Итого'] += 1
            overall[username]['Итого'] += 1

        # Добавляем итоговую статистику
        data['Итого'] = overall

        return JsonResponse(data, json_dumps_params={'ensure_ascii': False})

@api_view(['POST'])
def update_info_tgbot(request):
    telegram_id = request.data.get('telegram_id')
    barcodes = request.data.get('barcodes')
    info_text = request.data.get('info') # Имя поля в JSON от бота

    # --- Валидация входных данных ---
    if not telegram_id:
        return Response({"error": "Параметр 'telegram_id' обязателен."}, status=status.HTTP_400_BAD_REQUEST)
    if not barcodes or not isinstance(barcodes, list):
        return Response({"error": "Параметр 'barcodes' должен быть непустым списком."}, status=status.HTTP_400_BAD_REQUEST)
    if info_text is None: # Пустая строка допустима, None - нет
        return Response({"error": "Параметр 'info' (содержащий текст информации) обязателен."}, status=status.HTTP_400_BAD_REQUEST)

    # --- Авторизация пользователя ---
    try:
        # Модель UserProfile у вас в core.models.UserProfile
        user_profile = UserProfile.objects.select_related('user').get(telegram_id=str(telegram_id))
        user = user_profile.user
    except UserProfile.DoesNotExist:
        return Response({"error": "Пользователь с таким Telegram ID не найден в системе."}, status=status.HTTP_403_FORBIDDEN)
    
    # Проверяем, состоит ли пользователь в группе "Менеджер"
    # Убедитесь, что группа 'Менеджер' существует в вашей БД Django
    if not user.groups.filter(name="Менеджер").exists():
        return Response({"error": "У вас нет доступа к этой функции."}, status=status.HTTP_403_FORBIDDEN)

    # --- Логика обновления информации о товарах ---
    try:
        with transaction.atomic(): # Гарантирует, что все обновления либо пройдут, либо нет
            # Модель Product у вас в core.models.Product
            products_qs = Product.objects.filter(barcode__in=barcodes)
            updated_count = products_qs.update(info=info_text)

            existing_barcodes_db = list(products_qs.values_list('barcode', flat=True))
            missing_barcodes = [barcode for barcode in barcodes if barcode not in existing_barcodes_db]
            
            # Опционально: логирование операции обновления информации, если необходимо
            # try:
            #     operation_type_info_update = ProductOperationTypes.objects.get(name="Информация обновлена ботом") # Пример
            #     operations_to_create = []
            #     for product_obj in products_qs:
            #         operations_to_create.append(
            #             ProductOperation(
            #                 product=product_obj,
            #                 operation_type=operation_type_info_update,
            #                 user=user, # Пользователь, чьим telegram_id воспользовались
            #                 comment=f"Info установлено: '{info_text[:100]}...'" # Краткий комментарий
            #             )
            #         )
            #     if operations_to_create:
            #         ProductOperation.objects.bulk_create(operations_to_create)
            # except ProductOperationTypes.DoesNotExist:
            #     print("Тип операции для логирования обновления Info не найден.")
            # except Exception as log_e:
            #     print(f"Ошибка при логировании обновления Info: {log_e}")

    except Exception as e:
        # Здесь хорошо бы добавить логирование ошибки 'e' на стороне сервера
        print(f"Ошибка Django при обновлении информации о товарах: {e}")
        return Response({"error": f"Внутренняя ошибка сервера при обновлении данных."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        "message": f"Информация обновлена для {updated_count} товаров.",
        "updated_count": updated_count,
        "missing_barcodes": missing_barcodes
    }, status=status.HTTP_200_OK)

#Среднее время хранения на ФС и срок поставки заказов
def format_timedelta_response(delta: timedelta | None) -> dict:
    """Преобразует timedelta в словарь для JSON-ответа."""
    if not delta:
        return {
            "average_duration_seconds": 0,
            "average_duration_human_readable": "Нет данных для расчета"
        }

    total_seconds = int(delta.total_seconds())
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    human_readable = f"{days} дн. {hours} ч. {minutes} мин. {seconds} сек."

    return {
        "average_duration_seconds": total_seconds,
        "average_duration_human_readable": human_readable
    }

#Среднее время хранения на ФС и срок поставки заказов
class AverageProcessingTimeView(APIView):
    """
    Эндпоинт для расчета средних временных интервалов:
    1. Среднее время нахождения товара на складе (outcome_date - income_date).
    2. Среднее время от создания заказа до приемки товара (OrderProduct.accepted_date - Order.date).
    """
    def get(self, request, *args, **kwargs):
        # 1. Получаем и валидируем параметры даты (без изменений)
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response(
                {"error": "Параметры 'start_date' и 'end_date' обязательны."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            start_datetime = datetime.combine(start_date, time.min)
            end_datetime = datetime.combine(end_date, time.max)
        except ValueError:
            return Response(
                {"error": "Неверный формат даты. Используйте гггг-ММ-ДД."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Первое вычисление: среднее время нахождения товара на складе
        product_processing_agg = Product.objects.filter(
            outcome_date__range=(start_datetime, end_datetime),
            income_date__isnull=False,
            # ✅ Новое условие: дата отправки должна быть позже даты приемки
            outcome_date__gt=F('income_date') 
        ).aggregate(
            average_duration=Avg(F('outcome_date') - F('income_date'))
        )
        product_delta = product_processing_agg.get('average_duration')

        # 3. Второе вычисление: среднее время от заказа до приемки (без изменений)
        order_processing_agg = OrderProduct.objects.filter(
            accepted_date__range=(start_datetime, end_datetime),
            accepted_date__isnull=False,
            order__date__isnull=False
        ).aggregate(
            average_duration=Avg(F('accepted_date') - F('order__date'))
        )
        order_delta = order_processing_agg.get('average_duration')

        # 4. Формируем структурированный ответ (без изменений)
        response_data = {
            "period": {
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
            "product_storage_time": format_timedelta_response(product_delta),
            "order_to_acceptance_time": format_timedelta_response(order_delta),
        }

        return Response(response_data, status=status.HTTP_200_OK)

#Проверка ШК
class BarcodeCheckView(APIView):

    def post(self, request):
        # 1. Валидация входных данных
        barcodes_input = request.data.get('barcodes')
        if not isinstance(barcodes_input, list):
            return Response(
                {'error': 'Неверный формат данных. Ожидается массив штрихкодов.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Приводим к строкам и дополняем до 13 цифр, отбрасывая невалидные
        processed = set()
        for bc in barcodes_input:
            if bc is None:
                continue
            bc_str = str(bc).strip()
            if not bc_str.isdigit() or len(bc_str) > 13:
                continue
            processed.add(bc_str.zfill(13))

        if not processed:
            return Response(
                {'error': 'Нет валидных штрихкодов после обработки.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        barcodes_to_check = processed.copy()

        # Результирующие списки для штрихкодов
        has_photo_list = []
        in_retouch_queue_list = []
        nofoto_list = []
        blocked_by_shop_list = []
        blocked_by_category_list = []
        blocked_by_barcode_list = []
        ordered_list = []
        onfs_list = []
        possible_zero_stock_list = [] # ✨ Новый список

        # 3. Проверка "Есть фото"
        if barcodes_to_check:
            found_barcodes = set(
                RetouchRequestProduct.objects
                                     .filter(
                                         st_request_product__product__barcode__in=barcodes_to_check,
                                         retouch_status__id=2,
                                         sretouch_status__id=1
                                     )
                                     .values_list('st_request_product__product__barcode', flat=True)
            )
            if found_barcodes:
                has_photo_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes

        # 4. Проверка "В очереди на ретушь"
        if barcodes_to_check:
            three_days_ago = timezone.now() - timedelta(hours=30)
            found_barcodes = set(
                STRequestProduct.objects
                                .filter(
                                    product__barcode__in=barcodes_to_check,
                                    photo_status__id=1,
                                    sphoto_status__id=1,
                                    senior_check_date__gte=three_days_ago
                                )
                                .values_list('product__barcode', flat=True)
            )
            if found_barcodes:
                in_retouch_queue_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes

        # 5. Проверка "Без фото" (Nofoto)
        if barcodes_to_check:
            found_barcodes = set(
                Nofoto.objects
                      .filter(product__barcode__in=barcodes_to_check)
                      .values_list('product__barcode', flat=True)
            )
            if found_barcodes:
                nofoto_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes

        # 6. Проверка "Заблокирован по магазину"
        if barcodes_to_check:
            blocked_shop_ids = set(Blocked_Shops.objects.values_list('shop_id', flat=True))
            found_barcodes = set(
                Product.objects
                       .filter(barcode__in=barcodes_to_check, seller__in=blocked_shop_ids)
                       .values_list('barcode', flat=True)
            )
            if found_barcodes:
                blocked_by_shop_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes

        # 7. Проверка "Заблокирован по категории"
        if barcodes_to_check:
            found_barcodes = set(
                Product.objects
                       .filter(barcode__in=barcodes_to_check, category__IsBlocked=True)
                       .values_list('barcode', flat=True)
            )
            if found_barcodes:
                blocked_by_category_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes

        # 8. Проверка "Заблокирован по штрихкоду"
        if barcodes_to_check:
            blocked_barcode_set = set(Blocked_Barcode.objects.values_list('barcode', flat=True))
            found_barcodes = barcodes_to_check & blocked_barcode_set
            if found_barcodes:
                blocked_by_barcode_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes

        # 9. Проверка "Заказан"
        if barcodes_to_check:
            found_barcodes = set(
                OrderProduct.objects
                            .filter(product__barcode__in=barcodes_to_check, order__status__id__in=[2, 3])
                            .values_list('product__barcode', flat=True)
            )
            if found_barcodes:
                ordered_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes

        # 10. Проверка "Принят на складе" (onfs)
        if barcodes_to_check:
            found_barcodes = set(
                Product.objects
                       .filter(barcode__in=barcodes_to_check, move_status__id=3)
                       .values_list('barcode', flat=True)
            )
            if found_barcodes:
                onfs_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes
        
        # 11. ✨ Новая проверка "Возможно нет остатков"
        if barcodes_to_check:
            found_barcodes = set(
                Product.objects
                       .filter(barcode__in=barcodes_to_check, in_stock_sum=0)
                       .values_list('barcode', flat=True)
            )
            if found_barcodes:
                possible_zero_stock_list.extend(list(found_barcodes))
                barcodes_to_check -= found_barcodes

        # 12. Все оставшиеся - "Не найдено" (missed)
        missed_list = list(barcodes_to_check)

        # 13. Отправляем результат на фронт
        return Response({
            'has_photo': sorted(has_photo_list),
            'in_retouch_queue': sorted(in_retouch_queue_list),
            'nofoto': sorted(nofoto_list),
            'blocked_by_shop': sorted(blocked_by_shop_list),
            'blocked_by_category': sorted(blocked_by_category_list),
            'blocked_by_barcode': sorted(blocked_by_barcode_list),
            'ordered': sorted(ordered_list),
            'onfs': sorted(onfs_list),
            'possible_zero_stock': sorted(possible_zero_stock_list), # ✨ Добавлено в ответ
            'missed': sorted(missed_list),
        }, status=status.HTTP_200_OK)

# Новый эндпоинт для последовательной проверки статуса штрихкодов
class BarcodeSequentialCheckView(APIView):
    def post(self, request, *args, **kwargs):
        barcodes_input = request.data.get('barcodes')
        if not isinstance(barcodes_input, list):
            return Response(
                {'error': 'Неверный формат данных. Ожидается массив штрихкодов.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Обработка и валидация входных штрихкодов
        processed_barcodes = []
        for bc in barcodes_input:
            if bc is None:
                continue
            bc_str = str(bc).strip()
            if bc_str.isdigit() and len(bc_str) <= 13:
                processed_barcodes.append(bc_str.zfill(13))
        
        if not processed_barcodes:
            return Response(
                {'error': 'Не найдено валидных штрихкодов для обработки.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        barcodes_to_check = set(processed_barcodes)
        results_map = {}

        # 1. Проверка: Есть фото с ретуши
        if barcodes_to_check:
            recent_photos = RetouchRequestProduct.objects.filter(
                st_request_product__product__barcode__in=barcodes_to_check,
                retouch_status__id=2,
                sretouch_status__id=1,
            ).select_related(
                'st_request_product__product',
                'st_request_product__request'
            )
            for rp in recent_photos:
                barcode = rp.st_request_product.product.barcode
                if barcode in barcodes_to_check:
                    results_map[barcode] = {
                        "barcode": barcode,
                        "retouch_link": rp.retouch_link,
                        "photo_date": rp.st_request_product.request.photo_date,
                        "barcode_status": "Есть фото"
                    }
                    barcodes_to_check.remove(barcode)

        # 2. Проверка: В очереди на ретушь
        if barcodes_to_check:
            three_days_ago = timezone.now() - timedelta(hours=30)
            retouch_queue_entries = STRequestProduct.objects.filter(
                product__barcode__in=barcodes_to_check,
                photo_status__id=1,
                sphoto_status__id=1,
                senior_check_date__gte=three_days_ago
            ).select_related('product', 'request')

            for srp in retouch_queue_entries:
                barcode = srp.product.barcode
                if barcode in barcodes_to_check:
                    results_map[barcode] = {
                        "barcode": barcode,
                        "date": srp.request.photo_date,
                        "barcode_status": "В очереди на ретушь"
                    }
                    barcodes_to_check.remove(barcode)
        
        # 3. Проверка: Запись в Nofoto
        if barcodes_to_check:
            nofoto_entries = Nofoto.objects.filter(
                product__barcode__in=barcodes_to_check
            ).select_related('product')
            for entry in nofoto_entries:
                barcode = entry.product.barcode
                if barcode in barcodes_to_check:
                    results_map[barcode] = {
                        "barcode": barcode,
                        "date": entry.date,
                        "barcode_status": "Без фото"
                    }
                    barcodes_to_check.remove(barcode)

        # 4. Проверка: Заблокирован магазин
        if barcodes_to_check:
            blocked_shop_ids = set(Blocked_Shops.objects.values_list('shop_id', flat=True))
            if blocked_shop_ids:
                products_in_blocked_shops = Product.objects.filter(
                    barcode__in=barcodes_to_check,
                    seller__in=blocked_shop_ids
                )
                for product in products_in_blocked_shops:
                    barcode = product.barcode
                    if barcode in barcodes_to_check:
                        results_map[barcode] = {
                            "barcode": barcode,
                            "barcode_status": "Заблокирован магазин"
                        }
                        barcodes_to_check.remove(barcode)

        # 5. Проверка: Заблокирован SKU
        if barcodes_to_check:
            blocked_skus = Blocked_Barcode.objects.filter(barcode__in=barcodes_to_check)
            for blocked in blocked_skus:
                barcode = blocked.barcode
                if barcode in barcodes_to_check:
                    results_map[barcode] = {
                        "barcode": barcode,
                        "barcode_status": "Заблокирован SKU"
                    }
                    barcodes_to_check.remove(barcode)

        # 6. Проверка: Заблокирована категория
        if barcodes_to_check:
            products_in_blocked_cats = Product.objects.filter(
                barcode__in=barcodes_to_check,
                category__IsBlocked=True
            )
            for product in products_in_blocked_cats:
                barcode = product.barcode
                if barcode in barcodes_to_check:
                    results_map[barcode] = {
                        "barcode": barcode,
                        "barcode_status": "Заблокирована категория"
                    }
                    barcodes_to_check.remove(barcode)
        
        # 7. Проверка: Заказан
        if barcodes_to_check:
            ordered_products = OrderProduct.objects.filter(
                product__barcode__in=barcodes_to_check,
                order__status__id__in=[2, 3]
            ).select_related('product', 'order')
            for op in ordered_products:
                barcode = op.product.barcode
                if barcode in barcodes_to_check:
                    results_map[barcode] = {
                        "barcode": barcode,
                        "order_date": op.order.date,
                        "barcode_status": "Заказан"
                    }
                    barcodes_to_check.remove(barcode)
        
        # 8. Проверка: Принят на складе
        if barcodes_to_check:
            on_fs_products = Product.objects.filter(
                barcode__in=barcodes_to_check,
                move_status__id=3
            )
            for product in on_fs_products:
                barcode = product.barcode
                if barcode in barcodes_to_check:
                    results_map[barcode] = {
                        "barcode": barcode,
                        "income_date": product.income_date,
                        "barcode_status": "Принят"
                    }
                    barcodes_to_check.remove(barcode)

        # 10. Если ничего не найдено
        for barcode in barcodes_to_check:
            results_map[barcode] = {
                "barcode": barcode,
                "barcode_status": "Не найдено"
            }

        # Сборка итогового ответа в порядке исходного запроса
        final_results = [results_map[bc] for bc in processed_barcodes if bc in results_map]

        return Response(final_results, status=status.HTTP_200_OK)


# ПОДСЧЕТ СРЕДНЕГО ВРЕМЕНИ СЪЕМКИ
class AverageShootingTimeView(APIView):
    def get(self, request, *args, **kwargs):
        # 1. Получение и валидация параметров даты (код без изменений)
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response(
                {"error": "Параметры 'start_date' и 'end_date' обязательны. Формат: гггг-ММ-ДД."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            start_datetime = datetime.combine(start_date, time.min)
            end_datetime = datetime.combine(end_date, time.max)
        except ValueError:
            return Response(
                {"error": "Неверный формат даты. Используйте гггг-ММ-ДД."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Основной запрос к БД (код без изменений)
        photo_times = STRequestPhotoTime.objects.filter(
            photo_date__range=(start_datetime, end_datetime)
        ).select_related(
            'st_request_product__request',
            'st_request_product__product__category'
        ).order_by('st_request_product__request_id', 'photo_date')

        if not photo_times:
            return Response({"message": "За указанный период нет данных для анализа."}, status=status.HTTP_200_OK)

        # 3. Вычисление длительностей с фильтрацией
        category_durations = defaultdict(list)
        for i in range(len(photo_times) - 1):
            current = photo_times[i]
            following = photo_times[i+1]

            if current.st_request_product.request_id == following.st_request_product.request_id:
                duration = following.photo_date - current.photo_date
                
                # ⭐ ИЗМЕНЕНИЕ 1: Игнорируем записи короче 45 секунд
                if duration.total_seconds() >= 45:
                    category = current.st_request_product.product.category
                    if category:
                        category_durations[category].append(duration)

        if not category_durations:
            return Response({"message": "Не найдено данных для расчета (возможно, все съемки были короче 30 секунд)."}, status=status.HTTP_200_OK)

        # 4. Удаление выбросов и расчет среднего
        category_averages_result = []
        overall_trimmed_durations = []

        for category, durations in category_durations.items():
            durations.sort()
            trim_count = int(len(durations) * 0.01)
            trimmed = durations[trim_count:-trim_count]
            
            # ⭐ ИЗМЕНЕНИЕ 2: Считаем категорию, только если в ней осталось 10+ записей
            if len(trimmed) >= 10:
                average_duration = sum(trimmed, timedelta()) / len(trimmed)
                overall_trimmed_durations.extend(trimmed)
                
                category_averages_result.append({
                    "category_id": category.id,
                    "category_name": category.name,
                    "average_seconds": int(average_duration.total_seconds()),
                    "average_human_readable": str(average_duration).split('.')[0]
                })
        
        # 5. Расчет общего среднего (код без изменений)
        overall_average = {}
        if overall_trimmed_durations:
            total_average_duration = sum(overall_trimmed_durations, timedelta()) / len(overall_trimmed_durations)
            overall_average = {
                "average_seconds": int(total_average_duration.total_seconds()),
                "average_human_readable": str(total_average_duration).split('.')[0]
            }

        # 6. Обработка опциональной сортировки (код без изменений)
        ordering = request.query_params.get('ordering')
        sort_key = 'category_id'
        reverse_order = False

        if ordering:
            if ordering.startswith('-'):
                reverse_order = True
                ordering = ordering[1:]
            
            if ordering == 'average_shooting_time':
                sort_key = 'average_seconds'

        sorted_category_averages = sorted(category_averages_result, key=lambda x: x.get(sort_key, 0), reverse=reverse_order)

        # 7. Формирование ответа (код без изменений)
        response_data = {
            "period": {
                "start_date": start_date_str,
                "end_date": end_date_str,
            },
            "category_averages": sorted_category_averages,
            "overall_average": overall_average
        }

        return Response(response_data, status=status.HTTP_200_OK)
    
######Дэборд по заказам и приемке#####
def format_duration_human_readable(duration):
    """Helper to format timedelta into a human-readable string."""
    if not isinstance(duration, timedelta) or duration.total_seconds() < 0:
        return "N/A"
    
    total_seconds = int(duration.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return f"{days}д {hours}ч {minutes}м {seconds}с"


class AcceptanceDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # --- 1. Date Validation ---
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            return Response(
                {"error": "Please provide 'start_date' and 'end_date' in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

            # Создаем "наивные" datetime
            naive_start_dt = datetime.combine(start_date, time.min)
            naive_end_dt = datetime.combine(end_date, time.max)

            # Делаем их "осведомленными" о часовом поясе
            start_dt = timezone.make_aware(naive_start_dt)
            end_dt = timezone.make_aware(naive_end_dt)

        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # --- Initialize daily data structure ---
        response = defaultdict(lambda: defaultdict(dict))
        delta = end_date - start_date
        all_dates = [start_date + timedelta(days=i) for i in range(delta.days + 1)]

        # --- 2. Ordered Products (by day and by STRequestType) ---
        ordered_products_qs = OrderProduct.objects.filter(order__date__range=(start_dt, end_dt))\
            .select_related('product__category__STRequestType')\
            .annotate(day=TruncDate('order__date'))\
            .values('day', 'product__category__STRequestType__name')\
            .annotate(count=Count('id'))\
            .order_by('day')

        total_ordered_count = 0
        total_by_type = defaultdict(int)

        for item in ordered_products_qs:
            date_str = item['day'].strftime('%Y-%m-%d')
            type_name = item['product__category__STRequestType__name'] or "Не указан"
            count = item['count']

            response[date_str]['ordered_products']['count'] = response[date_str]['ordered_products'].get('count', 0) + count
            response[date_str]['ordered_products_by_type'][type_name] = response[date_str]['ordered_products_by_type'].get(type_name, 0) + count
            total_ordered_count += count
            total_by_type[type_name] += count
        
        # Calculate ratios for ordered products
        for date_str, data in response.items():
            daily_total = data.get('ordered_products', {}).get('count', 0)
            if daily_total > 0:
                for type_name, count in data.get('ordered_products_by_type', {}).items():
                    data['ordered_products_by_type'][type_name] = round(count / daily_total, 2)
        
        # --- 3. Accepted Products & Stats (based on Order.accept_date) ---
        orders_in_range = Order.objects.filter(accept_date__range=(start_dt, end_dt))\
            .select_related('accept_user')\
            .annotate(
                day=TruncDate('accept_date'),
                total_products=Count('orderproduct'),
                accepted_products=Count('orderproduct', filter=Q(orderproduct__accepted=True)),
                assembly_duration=ExpressionWrapper(F('accept_date') - F('date'), output_field=DurationField())
            ).order_by('day')

        total_accepted_products = 0
        total_assembly_duration = timedelta()
        total_assembly_orders = 0
        total_accuracy_numerator = 0
        total_accuracy_denominator = 0
        total_acceptance_time_per_product = timedelta()
        total_acceptance_orders_with_time = 0
        user_acceptance_time = defaultdict(lambda: {'total_duration': timedelta(), 'count': 0})
        
        for order in orders_in_range:
            date_str = order.day.strftime('%Y-%m-%d')
            
            # Assembly Time
            response[date_str]['assembly_time']['total_seconds'] = response[date_str]['assembly_time'].get('total_seconds', 0) + order.assembly_duration.total_seconds()
            response[date_str]['assembly_time']['count'] = response[date_str]['assembly_time'].get('count', 0) + 1
            total_assembly_duration += order.assembly_duration
            total_assembly_orders += 1

            # Assembly Accuracy
            response[date_str]['assembly_accuracy']['accepted'] = response[date_str]['assembly_accuracy'].get('accepted', 0) + order.accepted_products
            response[date_str]['assembly_accuracy']['total'] = response[date_str]['assembly_accuracy'].get('total', 0) + order.total_products
            total_accuracy_numerator += order.accepted_products
            total_accuracy_denominator += order.total_products

            # Accepted Count (from this query)
            response[date_str]['accepted_count'] = response[date_str].get('accepted_count', 0) + order.accepted_products
            total_accepted_products += order.accepted_products

            # Acceptance Time per Product
            # Проверяем, что есть принятые товары, чтобы избежать деления на ноль
            if order.accept_time and order.accepted_products > 0:
                # Делим на количество ПРИНЯТЫХ товаров
                time_per_product = order.accept_time / order.accepted_products
                
                # Остальная логика остается без изменений
                response[date_str]['acceptance_time_per_product']['total_seconds'] = response[date_str]['acceptance_time_per_product'].get('total_seconds', 0) + time_per_product.total_seconds()
                response[date_str]['acceptance_time_per_product']['count'] = response[date_str]['acceptance_time_per_product'].get('count', 0) + 1
                total_acceptance_time_per_product += time_per_product
                total_acceptance_orders_with_time += 1
                if order.accept_user:
                    username = f"{order.accept_user.first_name} {order.accept_user.last_name}".strip() or order.accept_user.username
                    user_acceptance_time[username]['total_duration'] += time_per_product
                    user_acceptance_time[username]['count'] += 1

        # --- 4. Top Accepted Categories ---
        top_categories_qs = OrderProduct.objects.filter(accepted=True, accepted_date__range=(start_dt, end_dt))\
            .values('product__category__id', 'product__category__name')\
            .annotate(count=Count('id'))\
            .order_by('-count')

        top_accepted_categories = [
            {"category_id": cat['product__category__id'], "category_name": cat['product__category__name'], "count": cat['count']}
            for cat in top_categories_qs
        ]

        # --- 5. New Products Ratio & PhotoModerationStatus breakdown ---
        first_acceptance_subquery = ProductOperation.objects.filter(
            product=OuterRef('product'), operation_type_id=3
        ).order_by('date').values('date')[:1]

        acceptance_ops = ProductOperation.objects.filter(date__range=(start_dt, end_dt), operation_type_id=3)\
            .annotate(
                day=TruncDate('date'),
                first_acceptance_date=Subquery(first_acceptance_subquery)
            ).values('day', 'first_acceptance_date', 'PhotoModerationStatus')

        total_new_accepted = 0
        total_ops_accepted = 0
        total_by_photo_status = defaultdict(int)

        for op in acceptance_ops:
            date_str = op['day'].strftime('%Y-%m-%d')
            # Changed variable name from 'status' to 'photo_moderation_status'
            photo_moderation_status = op['PhotoModerationStatus'] or "Не указан"
            is_new = op['day'] == op['first_acceptance_date'].date()

            response[date_str]['new_products']['total'] = response[date_str]['new_products'].get('total', 0) + 1
            # Use the new variable name here
            response[date_str]['by_photo_status'][photo_moderation_status] = response[date_str]['by_photo_status'].get(photo_moderation_status, 0) + 1
            total_ops_accepted += 1
            # And also here
            total_by_photo_status[photo_moderation_status] += 1
            if is_new:
                response[date_str]['new_products']['new_count'] = response[date_str]['new_products'].get('new_count', 0) + 1
                total_new_accepted += 1

        # --- Final Calculations and Formatting ---
        final_response = {'daily_data': {}, 'totals': {}}

        for date_obj in all_dates:
            date_str = date_obj.strftime('%Y-%m-%d')
            day_data = response[date_str]
            final_day = {}

            # Ordered
            final_day['ordered_products_count'] = day_data.get('ordered_products', {}).get('count', 0)
            final_day['ordered_products_by_type_ratio'] = day_data.get('ordered_products_by_type', {})
            
            # Accepted
            final_day['accepted_products_count'] = day_data.get('accepted_count', 0)

            # Assembly Time
            assembly_info = day_data.get('assembly_time', {})
            if assembly_info.get('count', 0) > 0:
                avg_assembly_seconds = assembly_info['total_seconds'] / assembly_info['count']
                final_day['average_assembly_time'] = format_duration_human_readable(timedelta(seconds=avg_assembly_seconds))
            else:
                final_day['average_assembly_time'] = "N/A"

            # Assembly Accuracy
            accuracy_info = day_data.get('assembly_accuracy', {})
            if accuracy_info.get('total', 0) > 0:
                final_day['assembly_accuracy_ratio'] = round(accuracy_info.get('accepted', 0) / accuracy_info['total'], 2)
            else:
                final_day['assembly_accuracy_ratio'] = 0
            
            # Acceptance Time per Product
            acceptance_time_info = day_data.get('acceptance_time_per_product', {})
            if acceptance_time_info.get('count', 0) > 0:
                avg_seconds = acceptance_time_info['total_seconds'] / acceptance_time_info['count']
                final_day['average_acceptance_time_per_product'] = format_duration_human_readable(timedelta(seconds=avg_seconds))
            else:
                final_day['average_acceptance_time_per_product'] = "N/A"
            
            # New Products Ratio
            new_prod_info = day_data.get('new_products', {})
            if new_prod_info.get('total', 0) > 0:
                final_day['new_products_ratio'] = round(new_prod_info.get('new_count', 0) / new_prod_info['total'], 2)
            else:
                final_day['new_products_ratio'] = 0

            # Photo Moderation Status Ratio
            photo_status_info = day_data.get('by_photo_status', {})
            total_status_count = sum(photo_status_info.values())
            if total_status_count > 0:
                final_day['photo_moderation_status_ratio'] = {k: round(v / total_status_count, 2) for k, v in photo_status_info.items()}
            else:
                final_day['photo_moderation_status_ratio'] = {}

            final_response['daily_data'][date_str] = final_day
        
        # Calculate Totals
        final_response['totals']['ordered_products_count'] = total_ordered_count
        if total_ordered_count > 0:
            final_response['totals']['ordered_products_by_type_ratio'] = {k: round(v / total_ordered_count, 2) for k, v in total_by_type.items()}
        else:
            final_response['totals']['ordered_products_by_type_ratio'] = {}
            
        final_response['totals']['accepted_products_count'] = total_accepted_products
        
        if total_assembly_orders > 0:
            avg_assembly = total_assembly_duration / total_assembly_orders
            final_response['totals']['average_assembly_time'] = format_duration_human_readable(avg_assembly)
        else:
            final_response['totals']['average_assembly_time'] = "N/A"

        if total_accuracy_denominator > 0:
            final_response['totals']['assembly_accuracy_ratio'] = round(total_accuracy_numerator / total_accuracy_denominator, 2)
        else:
            final_response['totals']['assembly_accuracy_ratio'] = 0
        
        if total_acceptance_orders_with_time > 0:
            avg_acceptance_time = total_acceptance_time_per_product / total_acceptance_orders_with_time
            final_response['totals']['average_acceptance_time_per_product'] = format_duration_human_readable(avg_acceptance_time)
        else:
            final_response['totals']['average_acceptance_time_per_product'] = "N/A"
        
        final_response['totals']['average_acceptance_time_by_user'] = {
            user: format_duration_human_readable(data['total_duration'] / data['count'])
            for user, data in user_acceptance_time.items() if data['count'] > 0
        }

        final_response['totals']['top_accepted_categories'] = top_accepted_categories
        
        final_response['totals']['total_newly_accepted_products'] = total_new_accepted
        if total_ops_accepted > 0:
            final_response['totals']['new_products_ratio'] = round(total_new_accepted / total_ops_accepted, 2)
            final_response['totals']['photo_moderation_status_ratio'] = {k: round(v / total_ops_accepted, 2) for k, v in total_by_photo_status.items()}
        else:
            final_response['totals']['new_products_ratio'] = 0
            final_response['totals']['photo_moderation_status_ratio'] = {}

        return Response(final_response, status=status.HTTP_200_OK)
