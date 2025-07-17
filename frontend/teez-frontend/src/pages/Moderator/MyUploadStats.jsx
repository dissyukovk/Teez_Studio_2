import React, { useState, useEffect, useCallback } from 'react';
import {
    Layout,
    DatePicker,
    Button,
    Spin,
    message,
    Typography,
    Modal,
    Table,
    Row,
    Col,
    ConfigProvider // Для глобальной локализации
} from 'antd';
import axios from 'axios';
import dayjs from 'dayjs';
import 'dayjs/locale/ru'; // Импорт локали для dayjs
import ruLocale from 'antd/lib/date-picker/locale/ru_RU';

// Импортируем компоненты и утилиты из вашего проекта
import Sidebar from '../../components/Layout/Sidebar'; // Укажите правильный путь
import { API_BASE_URL } from '../../utils/config'; // Укажите правильный путь

const { Content } = Layout;
const { Title } = Typography;
const { RangePicker } = DatePicker;

// Устанавливаем локаль для dayjs глобально
dayjs.locale('ru');

const MAX_DATE_RANGE = 31; // Максимальное количество дней в диапазоне
const DATE_FORMAT = 'DD.MM.YYYY'; // Формат даты для бэкенда и отображения

const MyUploadStats = ({ darkMode, setDarkMode }) => {
    // --- Состояния ---
    const [dateRange, setDateRange] = useState([null, null]); // Выбранный диапазон дат [dayjs | null, dayjs | null]
    const [loading, setLoading] = useState(false); // Флаг загрузки данных
    const [statsData, setStatsData] = useState([]); // Данные для таблицы
    const [errorModalVisible, setErrorModalVisible] = useState(false); // Видимость модального окна ошибки диапазона дат

    // Установка заголовка страницы при монтировании
    useEffect(() => {
        document.title = 'Моя статистика по загрузкам';
    }, []);

    // --- Обработчики событий ---

    // Обработка изменения дат с проверкой максимального интервала
    const handleDateChange = (dates) => {
        if (dates && dates[0] && dates[1]) {
            // Проверяем разницу в днях + 1, так как диапазон включительный
            const diff = dates[1].diff(dates[0], 'day') + 1;
            if (diff > MAX_DATE_RANGE) {
                // Если диапазон превышен, показываем модальное окно
                setErrorModalVisible(true);
                // Не обновляем состояние dateRange, чтобы пользователь видел предыдущий валидный выбор или пустоту
                return;
            }
        }
        // Если диапазон валидный или неполный, обновляем состояние
        setDateRange(dates);
    };

    // Функция для получения данных с бэкенда
    const fetchStats = useCallback(async () => {
        // Проверка наличия выбранных дат
        if (!dateRange || !dateRange[0] || !dateRange[1]) {
            message.error("Пожалуйста, выберите период дат.");
            return;
        }

        // Форматирование дат для URL
        const startDate = dateRange[0].format(DATE_FORMAT);
        const endDate = dateRange[1].format(DATE_FORMAT);

        setLoading(true); // Включаем индикатор загрузки
        setStatsData([]); // Очищаем предыдущие данные

        // Получение токена авторизации
        const token = localStorage.getItem('accessToken');
        if (!token) {
            message.error("Ошибка авторизации: токен не найден. Пожалуйста, войдите снова.");
            setLoading(false);
            // Здесь можно добавить редирект на страницу логина
            return;
        }

        try {
            // Формирование URL запроса
            const url = `${API_BASE_URL}/rd/MyUploadStat/${startDate}/${endDate}/`;

            // Выполнение GET запроса с токеном в заголовке
            const response = await axios.get(url, {
                headers: { Authorization: `Bearer ${token}` }
            });

            // Обработка успешного ответа
            const rawData = response.data; // Ожидаемый формат: {"dd.mm.yyyy": {"Загружено": N, "Отклонено": M}, ...}

            // Преобразование данных для таблицы Ant Design
            const formattedData = Object.entries(rawData)
                .map(([dateStr, counts]) => ({
                    key: dateStr, // Ключ для строки таблицы
                    date: dateStr, // Дата для отображения в столбце
                    uploaded: counts['Загружено'] || 0, // Количество загруженных
                    rejected: counts['Отклонено'] || 0, // Количество отклоненных
                }))
                .sort((a, b) => dayjs(a.date, DATE_FORMAT).unix() - dayjs(b.date, DATE_FORMAT).unix()); // Сортировка по дате

            setStatsData(formattedData); // Обновляем состояние с данными для таблицы

        } catch (error) {
            console.error("Ошибка при загрузке статистики:", error);
            if (error.response) {
                // Обработка ошибок от сервера (например, 401, 403, 404)
                if (error.response.status === 403) {
                     message.error("Ошибка доступа: Вы не модератор.");
                } else if (error.response.status === 401) {
                    message.error("Ошибка авторизации. Пожалуйста, войдите снова.");
                     // Возможно, редирект на логин
                } else {
                    message.error(`Ошибка сервера: ${error.response.status}. ${error.response.data?.detail || error.response.data?.error || ''}`);
                }
            } else if (error.request) {
                // Ошибка сети или сервер недоступен
                message.error("Ошибка сети. Не удалось подключиться к серверу.");
            } else {
                // Другие ошибки (например, при обработке данных)
                message.error("Произошла ошибка при обработке запроса.");
            }
        } finally {
            setLoading(false); // Выключаем индикатор загрузки в любом случае
        }
    }, [dateRange]); // Зависимость от dateRange

    // --- Конфигурация таблицы ---
    const columns = [
        {
            title: 'Дата',
            dataIndex: 'date',
            key: 'date',
            width: 150,
            sorter: (a, b) => dayjs(a.date, DATE_FORMAT).unix() - dayjs(b.date, DATE_FORMAT).unix(),
            defaultSortOrder: 'ascend',
        },
        {
            title: 'Загружено',
            dataIndex: 'uploaded',
            key: 'uploaded',
            width: 150,
            align: 'center',
             sorter: (a, b) => a.uploaded - b.uploaded,
        },
        {
            title: 'Отклонено',
            dataIndex: 'rejected',
            key: 'rejected',
            width: 150,
            align: 'center',
            sorter: (a, b) => a.rejected - b.rejected,
        },
    ];

    // --- Рендер компонента ---
    return (
        // Обертка для глобальной установки локали antd
        <ConfigProvider locale={ruLocale}>
            <Layout>
                {/* Сайдбар из вашего примера */}
                <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
                <Content style={{ padding: '24px', minHeight: '100vh', background: darkMode ? '#141414' : '#fff' }}>
                    {/* Заголовок страницы */}
                    <Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>
                         Моя статистика по загрузкам
                    </Title>

                    {/* Блок выбора дат и кнопки */}
                    <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
                        <Col>
                            <RangePicker
                                // locale={ruLocale.DatePicker} // Локаль можно и здесь, но ConfigProvider лучше
                                format={DATE_FORMAT} // Формат отображения
                                value={dateRange} // Привязка к состоянию
                                onChange={handleDateChange} // Обработчик изменения
                                allowClear={true} // Разрешить очистку
                            />
                        </Col>
                        <Col>
                            <Button
                                type="primary"
                                onClick={fetchStats} // Обработчик клика
                                loading={loading} // Состояние загрузки для кнопки
                                disabled={!dateRange || !dateRange[0] || !dateRange[1]} // Блокировка, если даты не выбраны
                            >
                                Показать данные
                            </Button>
                        </Col>
                    </Row>

                    {/* Индикатор загрузки или таблица с данными */}
                    {loading ? (
                        <div style={{ textAlign: 'center', marginTop: '50px' }}>
                            <Spin size="large" />
                        </div>
                    ) : (
                         // Отображаем таблицу только если есть данные
                        statsData.length > 0 && (
                            <Table
                                columns={columns}
                                dataSource={statsData}
                                pagination={false} // Отключаем пагинацию, если данных немного
                                bordered // Границы ячеек
                                size="middle" // Размер таблицы
                                scroll={{ x: 'max-content' }} // Горизонтальный скролл при необходимости
                            />
                        )
                    )}

                    {/* Модальное окно для ошибки диапазона дат */}
                    <Modal
                        title="Ошибка выбора дат"
                        visible={errorModalVisible}
                        onOk={() => setErrorModalVisible(false)}
                        onCancel={() => setErrorModalVisible(false)}
                        cancelButtonProps={{ style: { display: 'none' } }} // Скрываем кнопку "Отмена"
                        okText="Понятно"
                        zIndex={1050} // Убедимся, что модальное окно поверх всего
                    >
                        <p>Максимально допустимый период для выбора составляет {MAX_DATE_RANGE} дней.</p>
                        <p>Пожалуйста, выберите другой диапазон дат.</p>
                    </Modal>
                </Content>
            </Layout>
        </ConfigProvider>
    );
};

export default MyUploadStats;