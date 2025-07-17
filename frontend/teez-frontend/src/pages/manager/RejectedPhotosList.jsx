import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Layout, Input, Button, message, Typography, Space, Divider, Slider } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;

const RejectedPhotosList = ({ darkMode, setDarkMode }) => {
    const [count, setCount] = useState('100');
    const [barcodesResult, setBarcodesResult] = useState('');
    const [loadingBarcodes, setLoadingBarcodes] = useState(false);
    const [sliderRange, setSliderRange] = useState([10, 80]);

    const [isTaskTriggering, setIsTaskTriggering] = useState(false);
    const [currentTaskId, setCurrentTaskId] = useState(null);
    const websocketRef = useRef(null);
    const messageKeyRef = React.useRef('taskStatusMessage');

    const token = localStorage.getItem('accessToken');
    const userId = useMemo(() => {
        try {
            const decoded = token ? JSON.parse(atob(token.split('.')[1])) : null;
            return decoded ? decoded.user_id : null;
        } catch (e) {
            console.error("Failed to decode token:", e);
            return null;
        }
    }, [token]);

    useEffect(() => {
        if (!userId) return;
        const apiUrl = new URL(API_BASE_URL);
        const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${apiUrl.host}/ws/task_progress/${userId}/`;
        const ws = new WebSocket(wsUrl);
        websocketRef.current = ws;
        ws.onopen = () => console.log(`WebSocket connected for user ${userId}`);
        ws.onerror = (error) => {
            console.error('WebSocket Error:', error);
            message.error('Ошибка WebSocket соединения. Попробуйте обновить страницу.');
        };
        ws.onclose = () => console.log('WebSocket disconnected.');
        return () => ws.close();
    }, [userId]);

    useEffect(() => {
        const ws = websocketRef.current;
        if (!ws) return;
        const messageHandler = (event) => {
            const data = JSON.parse(event.data);
            if (currentTaskId && data.payload.task_id === currentTaskId) {
                const { status, message: msg } = data.payload;
                if (status === 'completed') {
                    message.success({ content: msg, key: messageKeyRef.current, duration: 5 });
                } else if (status === 'error') {
                    message.error({ content: msg, key: messageKeyRef.current, duration: 5 });
                }
                setIsTaskTriggering(false);
                setCurrentTaskId(null);
            }
        };
        ws.onmessage = messageHandler;
        return () => {
            if (ws) ws.onmessage = null;
        };
    }, [currentTaskId]);

    const handleTriggerUpdateStatusTask = async () => {
        if (isTaskTriggering) {
            message.warn('Задача уже выполняется. Пожалуйста, подождите.');
            return;
        }
        if (!websocketRef.current || websocketRef.current.readyState !== WebSocket.OPEN) {
            message.error('WebSocket не подключен. Попробуйте обновить страницу.');
            return;
        }
        setIsTaskTriggering(true);
        const key = messageKeyRef.current;
        message.loading({ content: 'Запуск задачи обновления статусов...', key, duration: 0 });
        try {
            const response = await axios.post(
                `${API_BASE_URL}/auto/trigger-update-order-status/`,
                {},
                { headers: { Authorization: token ? `Bearer ${token}` : '' } }
            );
            if (response.data && response.data.task_id) {
                setCurrentTaskId(response.data.task_id);
            } else {
                const errorMsg = response.data.message || 'Не удалось получить ID задачи для отслеживания.';
                message.error({ content: errorMsg, key, duration: 5 });
                setIsTaskTriggering(false);
            }
        } catch (error) {
            const errorMsg = error.response?.data?.message || 'Не удалось запустить задачу обновления статусов.';
            message.error({ content: errorMsg, key, duration: 5 });
            setIsTaskTriggering(false);
        }
    };
    
    useEffect(() => {
        document.title = 'Список отклоненных фото | Управление задачами';
    }, []);

    const handleCountChange = (e) => {
        const value = e.target.value.replace(/[^0-9]/g, '');
        setCount(value);
    };

    const handleFetchBarcodes = async () => {
        const numCount = parseInt(count, 10);
        if (isNaN(numCount) || numCount <= 0) {
            message.error('Введите корректное положительное число для получения списка');
            return;
        }
        setLoadingBarcodes(true);
        setBarcodesResult('');

        const limit_type_3 = sliderRange[0] / 100;
        const limit_type_2 = (100 - sliderRange[1]) / 100;

        const params = new URLSearchParams();
        if (limit_type_2 > 0) {
            params.append('limit_type_2', limit_type_2.toFixed(2));
        }
        if (limit_type_3 > 0) {
            params.append('limit_type_3', limit_type_3.toFixed(2));
        }
        const queryString = params.toString();
        const requestUrl = `${API_BASE_URL}/rd/RejectToShooting/${numCount}/${queryString ? `?${queryString}` : ''}`;
        
        try {
            const response = await axios.get(requestUrl, { headers: { Authorization: token ? `Bearer ${token}` : '' } });
            if (response.data && Array.isArray(response.data)) {
                if (response.data.length === 0) {
                    message.info('Не найдено баркодов по заданным критериям.');
                    setBarcodesResult('');
                } else {
                    setBarcodesResult(response.data.join('\n'));
                    message.success(`Загружено ${response.data.length} баркодов.`);
                }
            } else {
                message.warning('Получен некорректный ответ от сервера при получении списка.');
                setBarcodesResult('');
            }
        } catch (error) {
            console.error("Ошибка при получении списка баркодов:", error);
            const errorMsg = error.response?.data?.detail || error.response?.data?.error || 'Не удалось получить список баркодов.';
            message.error(errorMsg);
            setBarcodesResult('');
        } finally {
            setLoadingBarcodes(false);
        }
    };

    return (
        <Layout style={{ minHeight: '100vh' }}>
            <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
            <Layout>
                <Content
                    style={{
                        padding: 24, margin: 0, display: 'flex',
                        flexDirection: 'column', alignItems: 'center',
                        background: darkMode ? '#141414' : '#fff',
                    }}
                >
                    <div style={{ width: '100%', maxWidth: 600, marginBottom: 24, textAlign: 'center' }}>
                        <Title level={3} style={{ color: darkMode ? '#fff' : 'inherit', marginBottom: 16 }}>
                            Управление фоновыми задачами
                        </Title>
                        <Button
                            type="primary"
                            danger
                            onClick={handleTriggerUpdateStatusTask}
                            loading={isTaskTriggering}
                            disabled={isTaskTriggering}
                            style={{ minWidth: 250 }}
                        >
                            {isTaskTriggering ? 'Задача выполняется...' : 'Запустить обновление статусов IsOnOrder'}
                        </Button>
                    </div>
                    <Divider style={{ borderColor: darkMode ? '#444' : '#e8e8e8' }} />
                    <div style={{ width: '100%', maxWidth: 600, marginTop: 24, textAlign: 'center' }}>
                        <Title level={3} style={{ color: darkMode ? '#fff' : 'inherit', marginBottom: 16 }}>
                            Получить список отклоненных фото
                        </Title>
                        <Space direction="vertical" size="middle" style={{ width: '100%', alignItems: 'center' }}>
                            <Input
                                placeholder="Введите количество"
                                value={count}
                                onChange={handleCountChange}
                                style={{ width: 300 }}
                            />
                            
                            <div style={{ width: '100%', maxWidth: '500px', margin: '20px auto' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 100px', marginBottom: '4px' }}>
                                    <Text style={{ color: darkMode ? '#ccc' : '#555' , marginRight: '25px'}}>КГТ{'\u00A0'}</Text>
                                    <Text style={{ color: darkMode ? '#ccc' : '#555' , marginRight: '25px'}}>{'\u00A0'}Обычные{'\u00A0'}</Text>
                                    <Text style={{ color: darkMode ? '#ccc' : '#555' }}>{'\u00A0'}Одежда</Text>
                                </div>
                                
                                <Slider
                                    range
                                    value={sliderRange}
                                    onChange={setSliderRange}
                                    disabled={loadingBarcodes || isTaskTriggering}
                                    tooltip={{
                                        // --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
                                        formatter: (value) => {
                                            // Сравниваем значение с текущими значениями в состоянии
                                            if (value === sliderRange[0]) {
                                                return `КГТ: ${value}%`;
                                            }
                                            if (value === sliderRange[1]) {
                                                return `Одежда: ${100 - value}%`;
                                            }
                                            return value;
                                        }
                                    }}
                                />

                                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 10px', marginTop: '4px' }}>
                                    <Text strong style={{ color: darkMode ? '#fff' : '#000' }}>{sliderRange[0]}%</Text>
                                    <Text strong style={{ color: darkMode ? '#fff' : '#000' }}>{sliderRange[1] - sliderRange[0]}%</Text>
                                    <Text strong style={{ color: darkMode ? '#fff' : '#000' }}>{100 - sliderRange[1]}%</Text>
                                </div>
                            </div>


                            <Button
                                type="primary"
                                onClick={handleFetchBarcodes}
                                loading={loadingBarcodes}
                                disabled={loadingBarcodes || isTaskTriggering}
                                style={{ minWidth: 200 }}
                            >
                                {loadingBarcodes ? 'Получение...' : 'Получить список'}
                            </Button>
                            <TextArea
                                rows={10}
                                value={barcodesResult}
                                readOnly
                                placeholder="Здесь появятся баркоды..."
                                style={{
                                    width: 400, fontFamily: 'monospace',
                                    backgroundColor: darkMode ? '#222' : '#f5f5f5',
                                    color: darkMode ? '#eee' : '#333',
                                }}
                            />
                        </Space>
                    </div>
                </Content>
            </Layout>
        </Layout>
    );
};

export default RejectedPhotosList;