import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Layout, Table, Descriptions, Typography, message, Spin, Button, Modal, Input, Tooltip, Select, Space, Progress } from 'antd';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import dayjs from 'dayjs';

import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';
import { RETOUCHER_STATUS_OPTIONS } from '../../utils/rtConstants';
import { EyeOutlined, DownloadOutlined, LinkOutlined, SendOutlined } from '@ant-design/icons';

const { Content } = Layout;
const { Title, Text, Link } = Typography;
const { Option } = Select;

const CONCURRENT_LINK_CHECKS_LIMIT = 5;
const BATCH_DELAY_MS = 200;

const RetoucherRequestDetailPage = ({ darkMode, setDarkMode }) => {
    const navigate = useNavigate();
    const { requestNumber } = useParams();
    const [token] = useState(localStorage.getItem('accessToken'));
    const userId = useMemo(() => {
        try {
            const decoded = token ? JSON.parse(atob(token.split('.')[1])) : null;
            return decoded ? decoded.user_id : null;
        } catch (e) {
            console.error("Failed to decode token:", e);
            return null;
        }
    }, [token]);

    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState({ download: false, link: false, send: false });
    const [requestHeader, setRequestHeader] = useState(null);
    const [products, setProducts] = useState([]);
    const [isLinkModalVisible, setIsLinkModalVisible] = useState(false);
    const [parentFolderUrl, setParentFolderUrl] = useState('');

    const [downloadProgress, setDownloadProgress] = useState(0);
    const [downloadStatusMessage, setDownloadStatusMessage] = useState('');
    const [isDownloadModalVisible, setIsDownloadModalVisible] = useState(false);
    const [downloadFinalUrl, setDownloadFinalUrl] = useState(null);

    const ws = useRef(null);

    const fetchData = useCallback(async () => {
        if (!token || !requestNumber) return;
        setLoading(true);
        try {
            const response = await axios.get(`${API_BASE_URL}/rt/request/details/${requestNumber}/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const results = response.data.results || [];
            if (results.length > 0) {
                setRequestHeader(results[0].retouch_request);
                setProducts(results.map(p => ({ ...p, key: p.id })));
            }
        } catch (error) {
            message.error('Ошибка загрузки деталей заявки.');
        } finally {
            setLoading(false);
        }
    }, [token, requestNumber]);

    useEffect(() => {
        document.title = `Заявка на ретушь ${requestNumber}`;
        if (token) fetchData();
        else Modal.error({ title: 'Ошибка доступа', content: 'Токен не найден.', onOk: () => navigate('/login') });
    }, [token, requestNumber, fetchData, navigate]);

    useEffect(() => {
        if (!userId) return;

        const apiUrl = new URL(API_BASE_URL);
        const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHostPort = apiUrl.host;

        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.close();
        }

        ws.current = new WebSocket(`${wsProtocol}//${wsHostPort}/ws/task_progress/${userId}/`);

        ws.current.onopen = () => {
            console.log('WebSocket connected');
            if (isDownloadModalVisible) {
                setDownloadStatusMessage('Соединение восстановлено. Ожидание прогресса...');
            }
        };

        ws.current.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);

            if (data.type === 'status_update') {
                setDownloadStatusMessage(data.payload.message);
                setDownloadProgress(0);
            } else if (data.type === 'progress') {
                setDownloadProgress(data.payload.percent);
                setDownloadStatusMessage(data.payload.description);
            } else if (data.type === 'complete') {
                setDownloadProgress(100);
                setDownloadStatusMessage(data.payload.message);
                setDownloadFinalUrl(data.payload.download_url);
                message.success('Архив успешно создан! Ссылка доступна в модальном окне и в Telegram.');
                setActionLoading(prev => ({ ...prev, download: false }));
                // Automatically trigger download
                if (data.payload.download_url) {
                    const link = document.createElement('a');
                    link.href = data.payload.download_url;
                    link.setAttribute('download', ''); // This attribute suggests the browser to download the file
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }
            } else if (data.type === 'error') {
                setDownloadProgress(0);
                setDownloadStatusMessage(`Ошибка: ${data.payload.message}`);
                message.error(`Ошибка скачивания: ${data.payload.message}. Проверьте Telegram для деталей.`);
                setDownloadFinalUrl(null);
                setActionLoading(prev => ({ ...prev, download: false }));
            }
        };

        ws.current.onclose = () => {
            console.log('WebSocket disconnected');
            if (isDownloadModalVisible && actionLoading.download) {
                 setDownloadStatusMessage('Соединение потеряно. Пожалуйста, подождите или перезагрузите страницу.');
            }
        };

        ws.current.onerror = (error) => {
            console.error('WebSocket error:', error);
            setDownloadStatusMessage('Ошибка WebSocket. Проверьте консоль.');
            message.error('Ошибка WebSocket. Перезагрузите страницу, если процесс завис.');
        };

        return () => {
            if (ws.current && ws.current.readyState === WebSocket.OPEN) {
                ws.current.close();
            }
        };
    }, [userId, isDownloadModalVisible, actionLoading.download]); //

    const handleProductChange = (productId, field, value) => {
        setProducts(prev => prev.map(p => p.id === productId ? { ...p, [field]: value } : p));
    };

    const handleStatusChange = async (productId, statusId) => {
        const product = products.find(p => p.id === productId);
        if (!product) return;

        try {
            const response = await axios.patch(
                `${API_BASE_URL}/rt/result/update/`,
                { retouch_request_product_id: productId, retouch_status_id: statusId, retouch_link: product.retouch_link },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            setProducts(prev => prev.map(p => p.id === productId ? { ...response.data, key: p.id } : p));
            message.success('Статус обновлен!');
        } catch (error) {
            const errorMsg = error.response?.data?.error || 'Не удалось обновить статус.';
            message.error(errorMsg);
        }
    };

    const getGoogleApiKey = async () => {
        try {
            const response = await axios.get(`${API_BASE_URL}/api/get-next-google-key/`, { headers: { Authorization: `Bearer ${token}` } });
            return response.data.api_key;
        } catch (error) {
            message.error('Не удалось получить ключ Google API.');
            return null;
        }
    };

    const getFolderIdFromUrl = (url) => {
        if (!url) return null;
        const match = url.match(/folders\/([a-zA-Z0-9_-]+)/);
        return match ? match[1] : null;
    };

    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

    const handleDownloadAll = async () => {
        if (!userId) {
            message.error('ID пользователя не найден. Пожалуйста, перезагрузите страницу или войдите заново.');
            return;
        }

        setActionLoading(prev => ({ ...prev, download: true }));

        try {
            const response = await axios.post(
            `${API_BASE_URL}/rt/request/download-files/${requestNumber}/`,
            {},
            { headers: { Authorization: `Bearer ${token}` } }
            );

            // Если архив уже готов — сразу качаем
            if (response.status === 200 && response.data.download_url) {
            const url = response.data.download_url;
            message.success('Архив уже готов! Начинаю загрузку...');
            // Закрываем модалку, если она была открыта
            setIsDownloadModalVisible(false);
            setActionLoading(prev => ({ ...prev, download: false }));
            // Создаём временную ссылку и эмулируем клик
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', '');
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            return;
            }

            // Иначе задача запущена на сервере — показываем модалку с прогрессом
            setIsDownloadModalVisible(true);
            setDownloadProgress(0);
            setDownloadStatusMessage('Запрос на архивацию принят. Ожидайте прогресса...');
            setDownloadFinalUrl(null);
            message.success('Запрос на архивацию принят. Ожидайте прогресса в модальном окне и уведомления в Telegram!');

        } catch (error) {
            const errorMsg = error.response?.data?.error || 'Ошибка при запросе на скачивание файлов.';
            message.error(errorMsg);
            setDownloadStatusMessage(`Ошибка: ${errorMsg}`);
            setDownloadProgress(0);
            setActionLoading(prev => ({ ...prev, download: false }));
        }
    };

    const handleApplyLinks = async () => {
        setActionLoading(prev => ({...prev, link: true}));
        const parentFolderId = getFolderIdFromUrl(parentFolderUrl);
        if (!parentFolderId) {
            message.error('Неверный формат ссылки на папку.');
            setActionLoading(prev => ({...prev, link: false}));
            return;
        }

        message.loading({ content: 'Получение ключа API...', key: 'link', duration: 0 });
        const apiKey = await getGoogleApiKey();
        if (!apiKey) {
            setActionLoading(prev => ({...prev, link: false}));
            message.destroy('link');
            return;
        }

        try {
            message.loading({ content: 'Запрос списка папок...', key: 'link', duration: 0 });
            const foldersResponse = await axios.get(`https://www.googleapis.com/drive/v3/files`, {
                params: {
                    q: `'${parentFolderId}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false`,
                    key: apiKey,
                    supportsAllDrives: 'true',
                    includeItemsFromAllDrives: 'true',
                    fields: 'files(id,name,webViewLink)',
                }
            });

            const subfolders = foldersResponse.data.files || [];

            if (subfolders.length === 0) {
                message.warning('В указанной директории не найдено ни одной папки. Проверьте ссылку и права доступа.');
                setActionLoading(prev => ({...prev, link: false}));
                message.destroy('link');
                return;
            }

            message.info(`Найдено ${subfolders.length} папок. Проверяем содержимое и обновляем статусы...`);

            const folderMap = new Map(subfolders.map(f => [f.name, {link: f.webViewLink, id: f.id}]));
            let updatedCount = 0;
            const emptyFolders = [];
            const successfulUpdates = new Map();

            const linkCheckQueue = [...products];
            const activeLinkChecks = new Set();

            const checkProductLinkAndSave = async (p) => {
                const barcode = p.st_request_product.product.barcode;
                if (folderMap.has(barcode)) {
                    const folderInfo = folderMap.get(barcode);

                    try {
                        const contentResponse = await axios.get(`https://www.googleapis.com/drive/v3/files`, {
                            params: {
                               q: `'${folderInfo.id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed=false`,
                               key: apiKey,
                               supportsAllDrives: 'true',
                               includeItemsFromAllDrives: 'true',
                               pageSize: 1,
                               fields: 'files(id)',
                            }
                        });

                        if (contentResponse.data.files && contentResponse.data.files.length > 0) {
                            const newLink = folderInfo.link;
                            const newStatusId = 2; // "Готов"
                            await axios.patch(
                                `${API_BASE_URL}/rt/result/update/`,
                                {
                                    retouch_request_product_id: p.id,
                                    retouch_status_id: newStatusId,
                                    retouch_link: newLink,
                                },
                                { headers: { Authorization: `Bearer ${token}` } }
                            );
                            successfulUpdates.set(p.id, { newLink, newStatusId });
                            updatedCount++;
                        } else {
                           emptyFolders.push(barcode);
                        }
                    } catch (error) {
                        console.error(`Ошибка при проверке/обновлении для ШК ${barcode}:`, error);
                        message.error(`Не удалось сохранить статус для ШК ${barcode}.`);
                    }
                }
            };

            while (linkCheckQueue.length > 0 || activeLinkChecks.size > 0) {
                while (linkCheckQueue.length > 0 && activeLinkChecks.size < CONCURRENT_LINK_CHECKS_LIMIT) {
                    const product = linkCheckQueue.shift();
                    if (!product) continue;

                    const checkPromise = checkProductLinkAndSave(product)
                        .finally(() => {
                            activeLinkChecks.delete(checkPromise);
                        });
                    activeLinkChecks.add(checkPromise);
                    await sleep(BATCH_DELAY_MS);
                }

                if (activeLinkChecks.size > 0) {
                    await Promise.race(Array.from(activeLinkChecks));
                } else if (linkCheckQueue.length > 0) {
                    await sleep(500);
                }
            }

            if (successfulUpdates.size > 0) {
                setProducts(prevProducts =>
                    prevProducts.map(p => {
                        if (successfulUpdates.has(p.id)) {
                            const update = successfulUpdates.get(p.id);
                            return {
                                ...p,
                                retouch_link: update.newLink,
                                retouch_status: RETOUCHER_STATUS_OPTIONS.find(s => s.id === update.newStatusId)
                            };
                        }
                        return p;
                    })
                );
            }

            if (updatedCount > 0) {
                 message.success(`Статус и ссылки для ${updatedCount} товаров успешно обновлены.`);
            } else {
                 message.warning('Не найдено совпадений по штрихкодам или все найденные папки пусты.');
            }

            if (emptyFolders.length > 0) {
                Modal.warning({
                    title: 'Следующие папки были пропущены (пустые):',
                    content: (
                        <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                            {emptyFolders.map(barcode => (
                                <Typography.Text key={barcode} style={{ display: 'block' }}>
                                    {barcode}
                                </Typography.Text>
                            ))}
                        </div>
                    ),
                    okText: 'Понятно',
                });
            }

        } catch (error) {
            console.error('Ошибка при поиске или проверке папок в Google Drive:', error);
            message.error('Произошла ошибка при работе с Google Drive API.');
        } finally {
            setActionLoading(prev => ({...prev, link: false}));
            setIsLinkModalVisible(false);
            setParentFolderUrl('');
            message.destroy('link');
        }
    };

    const handleSendForReview = async () => {
        setActionLoading(prev => ({ ...prev, send: true }));
        try {
            await axios.post(`${API_BASE_URL}/rt/request/send-for-review/${requestHeader.id}/`, {}, {
                headers: { Authorization: `Bearer ${token}` }
            });
            message.success('Заявка успешно отправлена на проверку!');
            navigate('/rt/RetoucherRequestsListPage/2/');
        } catch (error) {
            const errorMsg = error.response?.data?.detail || 'Ошибка отправки на проверку.';
            message.error(errorMsg);
        } finally {
            setActionLoading(prev => ({ ...prev, send: false }));
        }
    };

    const isSendButtonActive = useMemo(() => {
        // Если списка продуктов нет или он пуст, кнопка должна быть неактивна.
        if (!products || products.length === 0) return false;

        // Проверяем, что КАЖДЫЙ продукт в заявке соответствует новым правилам.
        // Метод .every() вернет true, только если все элементы массива пройдут проверку.
        return products.every(p => {
            // Получаем ID статуса текущего продукта.
            const statusId = p.retouch_status?.id;

            // Проверяем первое условие: статус "Готов" (ID=2) и ссылка на ретушь не пустая.
            // `!!p.retouch_link` преобразует строку в boolean (true если не пустая, false если пустая или null/undefined).
            if (statusId === 2) {
                return !!p.retouch_link;
            }

            // Проверяем второе условие: статус равен 3, 4, 5 или 7.
            // В этом случае проверка на ссылку не требуется.
            if ([3, 4, 5, 7].includes(statusId)) {
                return true;
            }

            // Если ни одно из условий не выполнено, продукт не проходит проверку,
            // и .every() вернет false, делая кнопку неактивной.
            return false;
        });
    }, [products]);

    const columns = [
        { title: 'Штрихкод', dataIndex: ['st_request_product', 'product', 'barcode'], key: 'barcode', width: 120 },
        { title: 'Наименование', dataIndex: ['st_request_product', 'product', 'name'], key: 'name', width: 230 },
        { title: 'Категория', key: 'category', render: (_, r) => r.st_request_product.product.category ? `${r.st_request_product.product.category.id} - ${r.st_request_product.product.category.name}` : '-', width: 180 },
        { title: 'Реф', key: 'ref', align: 'center', // r.st_request_product.product.category?.reference_link
            render: (_, r) => {
          // Проверяем, что флаг IsReference === true и ссылка существует record.st_request_product.product.category?.reference_link
                const hasReference = r.st_request_product.product.category?.IsReference === true;
                const referenceLink = r.st_request_product.product.category?.reference_link;

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
        { title: 'Инфо', dataIndex: ['st_request_product', 'product', 'info'], key: 'info', width: 150 },
        { title: 'Исходники', dataIndex: ['st_request_product', 'photos_link'], key: 'source', render: (link) => link ? <Link href={link} target="_blank">Ссылка</Link> : '-', width: 100 },
        { title: 'Комментарий фотографа', dataIndex: ['st_request_product', 'ph_to_rt_comment'], key: 'ph_comment', render: (text) => <Text strong>{text || '-'}</Text>, width: 200 },
        {
            title: 'Ссылка',
            dataIndex: 'retouch_link',
            key: 'link',
            render: (text, record) => <Input value={text || ''} onChange={(e) => handleProductChange(record.id, 'retouch_link', e.target.value)} placeholder="Вставьте ссылку на ретушь" />,
            width: 200,
        },
        {
            title: 'Статус',
            dataIndex: ['retouch_status', 'id'],
            key: 'status',
            render: (statusId, record) => (
                <Select
                    style={{ width: '100%' }}
                    value={statusId}
                    onChange={(value) => handleStatusChange(record.id, value)}
                    placeholder="Выберите статус"
                >
                    {RETOUCHER_STATUS_OPTIONS.map(opt => <Option key={opt.id} value={opt.id}>{opt.name}</Option>)}
                </Select>
            ),
            width: 150,
        },
        {
            title: 'Проверка',
            dataIndex: ['sretouch_status', 'name'],
            key: 's_status',
            render: (text, record) => (
                <Text style={{ color: record.sretouch_status?.id === 2 ? 'red' : undefined }}>
                {text || '-'}
                </Text>
            ),
            width: 120,
        },
        { title: 'Комментарий', dataIndex: 'comment', key: 'comment', render: (text) => text || '-', width: 200 },
    ];

    if (loading) return <Layout><Content style={{padding: 50, textAlign: 'center'}}><Spin size="large" /></Content></Layout>;

    return (
        <Layout style={{ minHeight: '100vh' }}>
            <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
            <Layout>
                <Content style={{ padding: '24px', background: darkMode ? '#001529' : '#fff' }}>
                    <Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>Детали заявки: {requestNumber}</Title>
                    {requestHeader && (
                        <Descriptions bordered size="small" style={{ marginBottom: 24 }}>
                            <Descriptions.Item label="Номер">{requestHeader.RequestNumber}</Descriptions.Item>
                            <Descriptions.Item label="Дата создания">{dayjs(requestHeader.creation_date).format('DD.MM.YYYY HH:mm')}</Descriptions.Item>
                        </Descriptions>
                    )}

                    <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
                        <Button icon={<DownloadOutlined />} onClick={handleDownloadAll} loading={actionLoading.download}>Скачать все</Button>
                        <Button icon={<LinkOutlined />} onClick={() => setIsLinkModalVisible(true)}>Проставить ссылки</Button>
                        <Button type="primary" icon={<SendOutlined />} onClick={handleSendForReview} loading={actionLoading.send} disabled={!isSendButtonActive}>Отправить на проверку</Button>
                    </Space>

                    <Table
                        columns={columns}
                        dataSource={products}
                        loading={loading}
                        pagination={false}
                        scroll={{ x: 1400 }}
                        bordered
                        size="small"
                    />

                    <Modal
                        title="Подготовка архива"
                        open={isDownloadModalVisible}
                        onCancel={() => setIsDownloadModalVisible(false)}
                        closable={true} // Allow closing with the 'x' button
                        maskClosable={false} // Prevent closing by clicking outside
                        footer={
                            downloadFinalUrl ?
                            [
                                <Button key="download" href={downloadFinalUrl} target="_blank" type="primary" icon={<DownloadOutlined />}>
                                    Скачать архив
                                </Button>,
                                <Button key="close" onClick={() => setIsDownloadModalVisible(false)}>
                                    Закрыть
                                </Button>
                            ] :
                            [
                                <Button key="close" onClick={() => setIsDownloadModalVisible(false)} disabled={actionLoading.download}>
                                    Закрыть
                                </Button>
                            ]
                        }
                    >
                        <div style={{ textAlign: 'center', padding: '20px 0' }}>
                            <Text>{downloadStatusMessage}</Text>
                            <Progress percent={downloadProgress} status={downloadProgress === 100 ? 'success' : 'active'} style={{ marginTop: 20 }} />
                            {downloadFinalUrl && (
                                <Text type="success" style={{ display: 'block', marginTop: 10 }}>
                                    Архив готов! Вы можете скачать его по ссылке выше или из Telegram.
                                </Text>
                            )}
                            {downloadProgress === 0 && downloadStatusMessage.includes('Ошибка') && (
                                <Text type="danger" style={{ display: 'block', marginTop: 10 }}>
                                    Произошла ошибка. Проверьте Telegram для более подробной информации.
                                </Text>
                            )}
                        </div>
                    </Modal>

                    <Modal
                        title="Проставить ссылки из папки Google Drive"
                        open={isLinkModalVisible}
                        onOk={handleApplyLinks}
                        onCancel={() => setIsLinkModalVisible(false)}
                        confirmLoading={actionLoading.link}
                        okText="Проставить"
                        cancelText="Отмена"
                    >
                        <Input
                           placeholder="https://drive.google.com/drive/folders/..."
                           value={parentFolderUrl}
                           onChange={(e) => setParentFolderUrl(e.target.value)}
                        />
                         <Text type="secondary" style={{marginTop: 8, display: 'block'}}>
                           Система найдет в указанной папке дочерние папки, названные по штрихкоду, проверит, что они не пустые, и проставит ссылки в таблицу.
                         </Text>
                    </Modal>
                </Content>
            </Layout>
        </Layout>
    );
};

export default RetoucherRequestDetailPage;