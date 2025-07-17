import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
    Layout,
    Table,
    Descriptions,
    Typography,
    message,
    Spin,
    Button,
    Modal,
    Select,
    Input,
    Space,
    Tooltip,
    Popover, // <-- Добавлено
} from 'antd';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar'; // Adjust path
import { API_BASE_URL } from '../../utils/config'; // Adjust path
import { requestTypeOptions } from '../../utils/requestTypeOptions';
import {
    CheckCircleOutlined,
    CloseCircleOutlined,
    DeleteOutlined,
    RollbackOutlined,
    EyeOutlined,
    CheckSquareOutlined,
    CameraOutlined,
    SaveOutlined, // <-- Добавлено
    EditOutlined, // <-- Добавлено
    MessageOutlined, // <-- Добавлено
    LinkOutlined,
} from '@ant-design/icons';

const { Content } = Layout;
const { Title } = Typography;
const { Option } = Select;

const PHOTO_STATUS_OPTIONS = [
    { id: 1, name: 'Готово' },
    { id: 2, name: 'НТВ' },
    { id: 10, name: 'На съемке' },
    { id: 25, name: 'Брак' },
];

const SPHOTO_STATUS_OPTIONS = [
    { id: 1, name: 'Проверено' },
    { id: 2, name: 'Правки' },
    { id: 3, name: 'Без статуса' },
];


// Компонент для модального окна комментария (без изменений)
const CommentModal = ({ visible, onOk, onCancel, initialComment, productBarcode, darkMode }) => {
    const [internalCommentText, setInternalCommentText] = useState('');

    useEffect(() => {
        if (visible) {
            setInternalCommentText(initialComment || '');
        }
    }, [visible, initialComment]);

    const handleOk = () => {
        onOk(internalCommentText);
    };

    const handleCancel = () => {
        setInternalCommentText('');
        onCancel();
    };

    return (
        <Modal
            title={`Комментарий для правок (Товар: ${productBarcode || ''})`}
            open={visible}
            onOk={handleOk}
            onCancel={handleCancel}
            okText="Сохранить"
            cancelText="Отмена"
        >
            <Input.TextArea
                rows={4}
                value={internalCommentText}
                onChange={(e) => setInternalCommentText(e.target.value)}
                placeholder="Введите комментарий для правок"
            />
        </Modal>
    );
};

// Строка с CSS стилями для акцентирования
const inlineTableStyles = `
  .ant-table-tbody > tr.highlight-row-green-underline > td {
    border-bottom: 2px solid green !important;
  }

  .ant-table-tbody > tr.dark-mode-table-row.highlight-row-green-underline > td {
    border-bottom-color: lightgreen !important;
  }
`;

// ===================================================================
//  Новый компонент для ячейки с комментарием для ретушера
// ===================================================================
const RetoucherCommentCell = ({ record, onSave }) => {
    const [comment, setComment] = useState(record.ph_to_rt_comment || '');
    const [saving, setSaving] = useState(false);
    const [visible, setVisible] = useState(false);

    // Синхронизация внутреннего состояния с данными из таблицы
    useEffect(() => {
        setComment(record.ph_to_rt_comment || '');
    }, [record.ph_to_rt_comment]);

    const handleSave = async () => {
        setSaving(true);
        const success = await onSave(record.product.barcode, comment);
        setSaving(false);
        if (success) {
            setVisible(false); // Закрываем поповер при успехе
        }
    };

    const popoverContent = (
        <div style={{ width: 250, height: 90 }}>
            <Input.TextArea
                rows={2}
                value={comment}
                onChange={e => setComment(e.target.value)}
                placeholder="Комментарий для ретушера"
            />
            <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={saving}
                style={{ marginTop: 10, float: 'right' }}
                size="small"
            >
                Сохранить
            </Button>
        </div>
    );

    const hasComment = record.ph_to_rt_comment && record.ph_to_rt_comment.trim() !== '';

    return (
        <Popover
            content={popoverContent}
            title="Комментарий для ретушера"
            trigger="click"
            open={visible}
            onOpenChange={setVisible}
        >
            <Tooltip title={hasComment ? "Посмотреть/изменить комментарий" : "Добавить комментарий"}>
                <Button
                    icon={hasComment ? <MessageOutlined style={{ color: '#faad14' }} /> : <EditOutlined />}
                    type="text"
                />
            </Tooltip>
        </Popover>
    );
};


const PhotographerSTRequestDetailPage = ({ darkMode, setDarkMode }) => {
    const navigate = useNavigate();
    const { requestNumber } = useParams();
    const [token, setToken] = useState(localStorage.getItem('accessToken'));

    const [detailData, setDetailData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [photographers, setPhotographers] = useState([]);
    const [assistants, setAssistants] = useState([]);

    const [isCommentModalVisible, setIsCommentModalVisible] = useState(false);
    const [currentEditingProduct, setCurrentEditingProduct] = useState(null);
    const [isBulkChecking, setIsBulkChecking] = useState(false);
    const [isCountingPhotos, setIsCountingPhotos] = useState(false);
    const [photoCounts, setPhotoCounts] = useState({});


    useEffect(() => {
        document.title = `Детали заявки ${requestNumber}`;
        if (!token) {
            Modal.error({
                title: 'Ошибка доступа',
                content: 'Токен авторизации не найден.',
                okText: 'Войти',
                onOk: () => navigate('/login'),
            });
        }
    }, [navigate, token, requestNumber]);

    const fetchRequestDetails = useCallback(async () => {
        if (!token || !requestNumber) return;
        setLoading(true);
        try {
            const response = await axios.get(`${API_BASE_URL}/ph/st-requests/${requestNumber}/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            setDetailData(response.data);
        } catch (error) {
            message.error('Ошибка загрузки деталей заявки');
            console.error("Fetch detail error:", error);
        } finally {
            setLoading(false);
        }
    }, [token, requestNumber]);

    // Обновление типа заявки
    const handleTypeChange = useCallback(async (newTypeId) => {
        if (!token || !detailData) return;
        try {
            await axios.post(
                `${API_BASE_URL}/st/change-request-type/${detailData.RequestNumber}/${newTypeId}/`,
                {},
                { headers: { Authorization: `Bearer ${token}` } }
            );
            message.success('Тип заявки успешно изменён');
            fetchRequestDetails();
        } catch (error) {
            message.error('Ошибка при изменении типа заявки');
            console.error(error);
        }
    }, [token, detailData, fetchRequestDetails]);

    const fetchPhotographers = useCallback(async () => {
        if (!token) return;
        try {
            const response = await axios.get(`${API_BASE_URL}/ph/photographers/working/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            setPhotographers(response.data || []);
        } catch (error) {
            console.error('Ошибка загрузки фотографов:', error);
        }
    }, [token]);

    const fetchAssistants = useCallback(async () => {
        if (!token) return;
        try {
            const response = await axios.get(`${API_BASE_URL}/ph/assistants/all/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            setAssistants(response.data || []);
        } catch (error) {
            console.error('Ошибка загрузки ассистентов:', error);
        }
    }, [token]);

    useEffect(() => {
        if (token && requestNumber) {
            fetchRequestDetails();
            fetchPhotographers();
            fetchAssistants();
        }
    }, [token, requestNumber, fetchRequestDetails, fetchPhotographers, fetchAssistants]);
    
    // Helper function to update a single product in the local state
    const updateLocalProductState = useCallback((updatedProduct) => {
        if (!updatedProduct || !updatedProduct.product || !updatedProduct.product.barcode) {
            console.error("Invalid data received for local update", updatedProduct);
            return;
        };
        const barcode = updatedProduct.product.barcode;
        
        setDetailData(prevData => {
            if (!prevData) return null;
            const updatedProducts = prevData.products.map(p =>
                p.product.barcode === barcode ? updatedProduct : p
            );
            return { ...prevData, products: updatedProducts };
        });
    }, []);

    // ==============================================================
    //  Новая функция для обновления комментария ретушеру
    // ==============================================================
    const handleUpdatePhToRtComment = useCallback(async (barcode, comment) => {
        if (!token || !detailData) return false;
        const messageKey = `ph_comment_${barcode}`;
        message.loading({ content: 'Сохранение комментария...', key: messageKey, duration: 0 });
        try {
            const response = await axios.post(`${API_BASE_URL}/ph/update-ph-to-rt-comment/`, {
                request_number: detailData.RequestNumber,
                barcode: barcode,
                ph_to_rt_comment: comment,
            }, {
                headers: { Authorization: `Bearer ${token}` },
            });
            updateLocalProductState(response.data);
            message.success({ content: 'Комментарий для ретушера сохранен', key: messageKey });
            return true; // Возвращаем true в случае успеха
        } catch (error) {
            const errorMsg = error.response?.data?.error || 'Ошибка сохранения комментария';
            message.error({ content: errorMsg, key: messageKey });
            console.error("Error updating ph_to_rt_comment:", error.response?.data || error);
            return false; // Возвращаем false в случае ошибки
        }
    }, [token, detailData, updateLocalProductState]);


    const handlePhotographerChange = useCallback(async (photographerId) => {
        if (!token || !detailData) return;
        try {
            await axios.post(`${API_BASE_URL}/ph/st-requests/assign-photographer/`,
                { request_number: detailData.RequestNumber, user_id: photographerId },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            message.success('Фотограф обновлен');
            fetchRequestDetails();
        } catch (error) {
            message.error('Ошибка обновления фотографа');
        }
    }, [token, detailData, fetchRequestDetails]);

    const handleRemovePhotographer = useCallback(async () => {
        if (!token || !detailData) return;
        try {
            await axios.post(`${API_BASE_URL}/ph/st-requests/remove-photographer/`,
                { request_number: detailData.RequestNumber },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            message.success('Фотограф снят');
            fetchRequestDetails();
        } catch (error) {
            message.error('Ошибка снятия фотографа');
        }
    }, [token, detailData, fetchRequestDetails]);

    const handleAssistantChange = useCallback(async (assistantId) => {
        if (!token || !detailData) return;
        try {
            await axios.post(`${API_BASE_URL}/ph/st-requests/assign-assistant/`,
                { request_number: detailData.RequestNumber, user_id: assistantId },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            message.success('Ассистент обновлен');
            fetchRequestDetails();
        } catch (error) {
            message.error('Ошибка обновления ассистента');
        }
    }, [token, detailData, fetchRequestDetails]);
    
    const handleRemoveAssistant = useCallback(async () => {
        if (!token || !detailData) return;
        try {
            await axios.post(`${API_BASE_URL}/ph/st-requests/remove-assistant/`,
                { request_number: detailData.RequestNumber },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            message.success('Ассистент снят');
            fetchRequestDetails();
        } catch (error) {
            message.error('Ошибка снятия ассистента');
        }
    }, [token, detailData, fetchRequestDetails]);

    const handleReturnToShooting = useCallback(async () => {
        if (!token || !detailData || detailData.status.id !== 5) return;
        Modal.confirm({
            title: 'Вернуть на съемку?',
            content: `Вы уверены, что хотите вернуть заявку ${detailData.RequestNumber} на съемку?`,
            okText: 'Да, вернуть',
            cancelText: 'Отмена',
            onOk: async () => {
                try {
                    await axios.post(`${API_BASE_URL}/ph/st-requests/return-to-shooting/`,
                        { request_number: detailData.RequestNumber },
                        { headers: { Authorization: `Bearer ${token}` } }
                    );
                    message.success(`Заявка ${detailData.RequestNumber} возвращена на съемку`);
                    fetchRequestDetails();
                } catch (error) {
                    const errorMsg = error.response?.data?.error || 'Ошибка возврата заявки на съемку';
                    message.error(errorMsg);
                    console.error("Return to shooting error:", error.response?.data || error);
                }
            }
        });
    }, [token, detailData, fetchRequestDetails]);

    const handlePhotoStatusChange = useCallback(async (barcode, photoStatusId) => {
        if (!token || !detailData) return;
        const messageKey = `photo_status_${barcode}`;
        message.loading({ content: 'Обновление...', key: messageKey });
        try {
            const response = await axios.post(`${API_BASE_URL}/ph/st-requests/product/update-photo-status/`,
                { request_number: detailData.RequestNumber, barcode: barcode, photo_status_id: photoStatusId },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            updateLocalProductState(response.data); // Update state with response data
            message.success({ content: `Статус фото для ${barcode} обновлен`, key: messageKey });
        } catch (error) {
            message.error({ content: `Ошибка обновления статуса фото для ${barcode}`, key: messageKey });
            console.error(`Error updating photo status for ${barcode}:`, error);
        }
    }, [token, detailData, updateLocalProductState]);

    const submitSPhotoStatusChange = useCallback(async (barcode, sphotoStatusId, commentToSend) => {
        if (!token || !detailData) {
            throw new Error("Отсутствует токен или данные заявки");
        }
        const payload = {
            request_number: detailData.RequestNumber,
            barcode: barcode,
            sphoto_status_id: sphotoStatusId,
        };
        if (commentToSend !== undefined && commentToSend !== null) {
            payload.comment = commentToSend;
        }
        const response = await axios.post(`${API_BASE_URL}/ph/st-requests/product/update-sphoto-status/`,
            payload,
            { headers: { Authorization: `Bearer ${token}` } }
        );
        return response.data; // Return updated product from backend
    }, [token, detailData]);

    const handleSPhotoStatusChange = useCallback((barcode, sphotoStatusId) => {
        if (sphotoStatusId === 2) { // "Правки"
            const product = detailData?.products.find(p => p.product.barcode === barcode);
            setCurrentEditingProduct({ barcode, sphoto_status_id: sphotoStatusId, currentComment: product?.comment || '' });
            setIsCommentModalVisible(true);
        } else {
            const messageKey = `sphoto_status_${barcode}`;
            message.loading({ content: 'Обновление...', key: messageKey });
            submitSPhotoStatusChange(barcode, sphotoStatusId, null)
                .then((updatedProduct) => {
                    updateLocalProductState(updatedProduct);
                    message.success({ content: `Статус проверки для ${barcode} обновлен`, key: messageKey });
                })
                .catch(error => {
                    message.error({ content: `Ошибка обновления для ${barcode}`, key: messageKey });
                    console.error(`Ошибка обновления статуса проверки для ${barcode}:`, error)
                });
        }
    }, [detailData, submitSPhotoStatusChange, updateLocalProductState]);

    const handleCommentModalOk = useCallback((newCommentText) => {
        if (currentEditingProduct) {
            const { barcode, sphoto_status_id } = currentEditingProduct;
            const messageKey = `sphoto_status_${barcode}`;
            message.loading({ content: 'Сохранение комментария...', key: messageKey });

            submitSPhotoStatusChange(barcode, sphoto_status_id, newCommentText)
                .then((updatedProduct) => {
                    updateLocalProductState(updatedProduct);
                    message.success({ content: `Статус и комментарий для ${barcode} обновлены`, key: messageKey });
                })
                .catch(error => {
                    message.error({ content: `Ошибка обновления для ${barcode}`, key: messageKey });
                    console.error(`Ошибка обновления статуса проверки для ${barcode}:`, error);
                })
                .finally(() => {
                    setIsCommentModalVisible(false);
                    setCurrentEditingProduct(null);
                });
        } else {
            setIsCommentModalVisible(false);
            setCurrentEditingProduct(null);
        }
    }, [currentEditingProduct, submitSPhotoStatusChange, updateLocalProductState]);

    const handleCommentModalCancel = useCallback(() => {
        setIsCommentModalVisible(false);
        setCurrentEditingProduct(null);
    }, []);

    const handleBulkCheckShotItems = useCallback(async () => {
        if (!detailData || !detailData.products || !detailData.products.length) {
            message.info('Нет товаров для проверки.');
            return;
        }
        const productsToUpdate = detailData.products.filter(p => {
            const photoStatusId = p.photo_status?.id;
            const sphotoStatusId = p.sphoto_status?.id;
            return [1, 2, 25].includes(photoStatusId) && sphotoStatusId !== 1;
        });
        if (productsToUpdate.length === 0) {
            message.info('Все подходящие отснятые товары уже проверены или не требуют массовой проверки.');
            return;
        }
        Modal.confirm({
            title: 'Массовая проверка',
            content: `Будет обновлен статус проверки на "Проверено" для ${productsToUpdate.length} товаров. Продолжить?`,
            okText: 'Да, проверить',
            cancelText: 'Отмена',
            onOk: async () => {
                setIsBulkChecking(true);
                message.loading({ content: `Обновление статусов для ${productsToUpdate.length} товаров...`, key: 'bulkUpdate', duration: 0 });
                
                const updatePromises = productsToUpdate.map(p =>
                    submitSPhotoStatusChange(p.product.barcode, 1, null).catch(err => ({ error: err, barcode: p.product.barcode }))
                );

                const results = await Promise.allSettled(updatePromises);
                
                const failureCount = results.filter(r => r.status === 'rejected' || r.value.error).length;

                message.destroy('bulkUpdate');
                if (failureCount > 0) {
                    message.error(`${failureCount} из ${productsToUpdate.length} статусов не удалось обновить. Обновляем список...`);
                } else {
                    message.success(`Все ${productsToUpdate.length} статусов успешно отправлены на обновление. Обновляем список...`);
                }
                
                fetchRequestDetails(); 
                setIsBulkChecking(false);
            },
            onCancel: () => {
                setIsBulkChecking(false);
            }
        });
    }, [detailData, submitSPhotoStatusChange, fetchRequestDetails]);

    const getFolderIdFromUrl = (url) => {
        if (!url) return null;
        const match = url.match(/folders\/([a-zA-Z0-9_-]+)/);
        return match ? match[1] : null;
    };

    const handleCountPhotos = useCallback(async () => {
        if (!detailData || !detailData.products) return;

        const productsToCount = detailData.products.filter(p => {
            const photoStatusId = p.photo_status?.id;
            const sphotoStatusId = p.sphoto_status?.id;
            return [1, 2, 25].includes(photoStatusId) && sphotoStatusId !== 1 && p.photos_link;
        });

        if (productsToCount.length === 0) {
            message.info('Нет подходящих товаров для подсчета фотографий.');
            return;
        }

        setIsCountingPhotos(true);
        message.loading({ content: 'Получение ключа API...', key: 'photoCount', duration: 0 });

        let apiKey;
        try {
            const response = await axios.get(`${API_BASE_URL}/api/get-next-google-key/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            apiKey = response.data.api_key;
            if (!apiKey) throw new Error("API ключ не получен");
            message.loading({ content: `Подсчет фото для ${productsToCount.length} товаров...`, key: 'photoCount', duration: 0 });
        } catch (error) {
            message.error('Не удалось получить ключ Google API. Подсчет отменен.');
            console.error('Google Key fetch error:', error);
            setIsCountingPhotos(false);
            message.destroy('photoCount');
            return;
        }

        const countPromises = productsToCount.map(async (product) => {
            const folderId = getFolderIdFromUrl(product.photos_link);
            if (!folderId) {
                return { barcode: product.product.barcode, count: 'N/A' };
            }
            try {
                const url = `https://www.googleapis.com/drive/v3/files?q='${folderId}' in parents and mimeType='image/jpeg' and trashed=false&key=${apiKey}&supportsAllDrives=true&includeItemsFromAllDrives=true&fields=files(id)`;
                const response = await axios.get(url);
                return { barcode: product.product.barcode, count: response.data.files ? response.data.files.length : 0 };
            } catch (error) {
                console.error(`Error counting photos for ${product.product.barcode} (folderId: ${folderId}):`, error.response?.data || error);
                return { barcode: product.product.barcode, count: 'Ошибка' };
            }
        });

        const results = await Promise.all(countPromises);
        const newCounts = results.reduce((acc, result) => {
            acc[result.barcode] = result.count;
            return acc;
        }, {});
        
        setPhotoCounts(prev => ({...prev, ...newCounts}));
        message.destroy('photoCount');
        message.success('Подсчет завершен.');
        setIsCountingPhotos(false);

    }, [detailData, token]);


    const { canEditPhotographer, canEditAssistant, canEditProductStatuses, canReturnToShooting } = useMemo(() => {
        const currentStatusId = detailData?.status?.id;
        return {
            canEditPhotographer: currentStatusId === 2 || currentStatusId === 3,
            canEditAssistant: currentStatusId === 2 || currentStatusId === 3 || currentStatusId === 5,
            canEditProductStatuses: currentStatusId === 3,
            canReturnToShooting: currentStatusId === 5,
        };
    }, [detailData]);

    const renderBooleanIcon = useCallback((value, trueTip = "Да", falseTip = "Нет") => (
        <Tooltip title={value ? trueTip : falseTip}>
            {value
                ? <CheckCircleOutlined style={{ color: 'green', fontSize: 16 }} />
                : <CloseCircleOutlined style={{ color: 'red', fontSize: 16 }} />
            }
        </Tooltip>
    ), []);

    

    const productColumns = useMemo(() => [
        { title: '#', key: 'index', render: (text, record, index) => index + 1, width: 25 },
        {
            title: 'Штрихкод',
            dataIndex: ['product', 'barcode'],
            key: 'barcode',
            width: 150, // Увеличена ширина
            render: (text, record) => {
                const sellerId = record.product.seller;
                const productId = record.product.ProductID;
    
                if (sellerId && productId) {
                    const adminUrl = `https://admin.teez.kz/ru/product-verification/shop/${sellerId}/product/${productId}`;
                    return (
                        <Space>
                            <span>{text}</span>
                            <Tooltip title="Открыть в админке">
                                <a href={adminUrl} target="_blank" rel="noopener noreferrer">
                                    <LinkOutlined />
                                </a>
                            </Tooltip>
                        </Space>
                    );
                }
                // Если нет данных, отображаем только штрихкод
                return text;
            },
        },
        { title: 'Наименование', dataIndex: ['product', 'name'], key: 'name', ellipsis: false, width: 300 },
        // Новый столбец Дата приемки
        {
            title: 'Дата приема',
            dataIndex: ['product', 'income_date'],
            key: 'income_date',
            width: 80,
            render: date => date
                ? new Date(date).toLocaleDateString('ru-RU')
                : '-',
        },
        { title: 'Можно удалить', dataIndex: ['IsDeleteAccess'], key: 'IsDeleteAccess', align: 'center', render: priority => renderBooleanIcon(priority), width: 40 },
        {
            title: 'Категория',
            key: 'category',
            render: (_, record) => record.product.category ? `${record.product.category.id} - ${record.product.category.name}` : '-',
            width: 200,
        },
        {
            title: 'Реф',
            key: 'reference',
            align: 'center',
            width: 50,
            render: (_, record) => {
                // Проверяем, что флаг IsReference === true и ссылка существует
                const hasReference = record.product.category?.IsReference === true;
                const referenceLink = record.product.category?.reference_link;

                return hasReference && referenceLink ? (
                    <Tooltip title="Открыть референс">
                        <Button 
                            icon={<EyeOutlined />} 
                            href={referenceLink} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            size="small" 
                            type="link"
                        />
                    </Tooltip>
                ) : '';
            },
        },
        { title: 'Пр-т', dataIndex: ['product', 'priority'], key: 'priority', align: 'center', render: priority => renderBooleanIcon(priority), width: 55 },
        { title: 'Инфо', dataIndex: ['product', 'info'], key: 'info', ellipsis: false, width: 250 },
        // Иконка ссылки вместо текста
        {
            title: 'Ссылка фото', dataIndex: 'photos_link', key: 'photos_link', align: 'center', width: 80,
            render: link => link
                ? <Tooltip title="Открыть фото">
                    <Button type="link" icon={<LinkOutlined />} href={link} target="_blank" rel="noopener noreferrer" />
                  </Tooltip>
                : '-'
        },
        {
            title: 'Кол-во',
            dataIndex: ['product', 'barcode'],
            key: 'photo_count',
            align: 'center',
            width: 70,
            render: (barcode) => photoCounts[barcode] ?? '-',
        },
        {
            title: 'Статус фото',
            dataIndex: 'photo_status',
            key: 'photo_status_id',
            width: 150,
            render: (status, record) => (
                <Select
                    style={{ width: '100%' }}
                    value={status ? status.id : undefined}
                    onChange={(value) => handlePhotoStatusChange(record.product.barcode, value)}
                    disabled={!canEditProductStatuses}
                    placeholder="Статус фото"
                >
                    {PHOTO_STATUS_OPTIONS.map(opt => <Option key={opt.id} value={opt.id}>{opt.name}</Option>)}
                </Select>
            ),
        },
        {
            title: 'Статус проверки',
            dataIndex: 'sphoto_status',
            key: 'sphoto_status_id',
            width: 70,
            render: (status, record) => (
                <Select
                    style={{ width: '100%' }}
                    value={status ? status.id : undefined}
                    onChange={(value) => handleSPhotoStatusChange(record.product.barcode, value)}
                    disabled={!canEditProductStatuses}
                    placeholder="Статус проверки"
                >
                    {SPHOTO_STATUS_OPTIONS.map(opt => <Option key={opt.id} value={opt.id}>{opt.name}</Option>)}
                </Select>
            ),
        },
        { title: 'Comment', dataIndex: 'comment', key: 'comment', width: 150, ellipsis: false },
        // ==============================================================
        //  Новый столбец "Для ретушера"
        // ==============================================================
        {
            title: 'Ретушь инфо',
            key: 'ph_to_rt_comment',
            align: 'center',
            width: 50,
            render: (text, record) => (
                <RetoucherCommentCell record={record} onSave={handleUpdatePhToRtComment} />
            )
        },
        { title: 'В ретуши', dataIndex: 'OnRetouch', key: 'OnRetouch', align: 'center', render: onRetouch => renderBooleanIcon(onRetouch, "В ретуши", "Не в ретуши"), width: 60 },
    ], [renderBooleanIcon, handlePhotoStatusChange, handleSPhotoStatusChange, canEditProductStatuses, photoCounts, handleUpdatePhToRtComment]);

    const getRowClassName = useCallback((record) => {
        let classNames = [];
        if (darkMode) {
            classNames.push('dark-mode-table-row');
        }
        const photoStatusId = record.photo_status?.id;
        const sphotoStatusId = record.sphoto_status?.id;
        const shouldHighlight = 
            [1, 2, 25].includes(photoStatusId) && sphotoStatusId !== 1;
        if (shouldHighlight) {
            classNames.push('highlight-row-green-underline');
        }
        return classNames.join(' ');
    }, [darkMode]);


    if (loading || !detailData) {
        return (
            <Layout style={{ minHeight: '100vh' }}>
                <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
                <Layout><Content style={{ padding: '50px', textAlign: 'center' }}><Spin size="large" /></Content></Layout>
            </Layout>
        );
    }

    return (
        <>
            <style>
                {inlineTableStyles}
            </style>
            <Layout style={{ minHeight: '100vh' }}>
                <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
                <Layout>
                    <Content style={{ padding: '24px', background: darkMode ? '#001529' : '#fff' }}>
                        <Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>Детали заявки: {detailData.RequestNumber}</Title>
                        <Descriptions bordered column={2} size="small" style={{ marginBottom: 24 }}>
                            <Descriptions.Item label="Номер">{detailData.RequestNumber}</Descriptions.Item>
                            <Descriptions.Item label="Статус">{detailData.status?.name || '-'}</Descriptions.Item>
                            <Descriptions.Item label="Тип заявки">
                                <Select
                                    value={detailData.STRequestType?.id}
                                    style={{ width: 180 }}
                                    onChange={handleTypeChange}
                                >
                                    {requestTypeOptions.map(opt => (
                                        <Option key={opt.id} value={opt.id}>{opt.name}</Option>
                                    ))}
                                </Select>
                            </Descriptions.Item>
                            <Descriptions.Item label="Дата создания">{detailData.creation_date}</Descriptions.Item>
                            <Descriptions.Item label="Товаровед">{detailData.stockman?.full_name || '-'}</Descriptions.Item>
                            <Descriptions.Item label="Дата назначения съемки">{detailData.photo_date}</Descriptions.Item>
                            <Descriptions.Item label="Фотограф">
                                <Space>
                                    <Select
                                        style={{ width: 200 }}
                                        value={detailData.photographer?.id}
                                        onChange={handlePhotographerChange}
                                        disabled={!canEditPhotographer}
                                        placeholder="Фотограф"
                                        allowClear showSearch optionFilterProp="children"
                                        filterOption={(input, option) => (option?.children ?? '').toLowerCase().includes(input.toLowerCase())}
                                    >
                                        {photographers.map(p => <Option key={p.id} value={p.id}>{p.full_name}</Option>)}
                                    </Select>
                                    {detailData.photographer && canEditPhotographer && <Tooltip title="Снять фотографа"><Button icon={<DeleteOutlined />} onClick={handleRemovePhotographer} danger size="small" /></Tooltip>}
                                </Space>
                            </Descriptions.Item>
                            <Descriptions.Item label="Ассистент">
                                <Space>
                                    <Select
                                        style={{ width: 200 }}
                                        value={detailData.assistant?.id}
                                        onChange={handleAssistantChange}
                                        disabled={!canEditAssistant}
                                        placeholder="Ассистент"
                                        allowClear showSearch optionFilterProp="children"
                                        filterOption={(input, option) => (option?.children ?? '').toLowerCase().includes(input.toLowerCase())}
                                    >
                                        {assistants.map(a => <Option key={a.id} value={a.id}>{a.full_name}</Option>)}
                                    </Select>
                                    {detailData.assistant && canEditAssistant && <Tooltip title="Снять ассистента"><Button icon={<DeleteOutlined />} onClick={handleRemoveAssistant} danger size="small" /></Tooltip>}
                                </Space>
                            </Descriptions.Item>
                            <Descriptions.Item label="Дата назначения ассистента">{detailData.assistant_date}</Descriptions.Item>
                        </Descriptions>

                        <Space style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
                            <div>
                               {canReturnToShooting && (
                                    <Button type="primary" icon={<RollbackOutlined />} onClick={handleReturnToShooting}>
                                        Вернуть на съемку
                                    </Button>
                                )}
                            </div>
                            <Space>
                            {canEditProductStatuses && (
                                    <Button
                                        type="default"
                                        icon={<CameraOutlined />}
                                        onClick={handleCountPhotos}
                                        loading={isCountingPhotos}
                                        disabled={isCountingPhotos}
                                    >
                                        Количество фото
                                    </Button>
                                )}
                            {canEditProductStatuses && (
                                    <Button
                                        type="primary"
                                        icon={<CheckSquareOutlined />}
                                        onClick={handleBulkCheckShotItems}
                                        loading={isBulkChecking}
                                        disabled={isBulkChecking || !detailData.products.some(p => [1,2,25].includes(p.photo_status?.id) && p.sphoto_status?.id !== 1) }
                                    >
                                        Проверить все отснятое
                                    </Button>
                                )}
                            </Space>
                        </Space>

                        <Title level={4} style={{ marginTop: 8, color: darkMode ? 'white' : 'black' }}>Товары в заявке</Title>
                        <Table
                            columns={productColumns}
                            dataSource={detailData.products.map(p => ({ ...p, key: p.product.barcode }))}
                            pagination={false}
                            scroll={{ x: 1400 }} // Увеличил ширину скролла для новой колонки
                            bordered
                            size="small"
                            rowClassName={getRowClassName}
                        />

                        <CommentModal
                            visible={isCommentModalVisible}
                            onOk={handleCommentModalOk}
                            onCancel={handleCommentModalCancel}
                            initialComment={currentEditingProduct?.currentComment}
                            productBarcode={currentEditingProduct?.barcode}
                            darkMode={darkMode}
                        />
                    </Content>
                </Layout>
            </Layout>
        </>
    );
};

export default React.memo(PhotographerSTRequestDetailPage);