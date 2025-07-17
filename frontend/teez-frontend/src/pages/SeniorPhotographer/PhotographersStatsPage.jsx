import React, { useState, useEffect } from 'react';
import {
  Layout,
  Table,
  DatePicker,
  Button,
  message,
  Typography,
  Row,
  Col,
  Spin,
  // Modal // Не используется в этом компоненте, но оставлю, если понадобится для других целей
} from 'antd';

// Локализация
import 'dayjs/locale/ru'; // импорт локали для dayjs
import dayjs from 'dayjs';
import ruLocale from 'antd/lib/date-picker/locale/ru_RU'; // импорт локали для DatePicker

import Sidebar from '../../components/Layout/Sidebar'; // Предполагается, что сайдбар находится здесь
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config'; // Предполагается, что базовый URL API здесь

const { Content } = Layout;
const { Title, Text } = Typography;

// Компонент для страницы статистики
const DailyStatsPage = ({ darkMode, setDarkMode }) => {
  const [selectedDate, setSelectedDate] = useState(dayjs()); // По умолчанию текущая дата
  const [loading, setLoading] = useState(false);
  const [statsData, setStatsData] = useState({ photographers: [], assistants: [] });

  // Токен авторизации (пример)
  const token = localStorage.getItem('accessToken'); // Убедитесь, что токен сохраняется в localStorage

  // Установка заголовка страницы при монтировании компонента
  useEffect(() => {
    document.title = 'Дневная статистика ФТ/СП';
  }, []);

  // Загрузка статистики при изменении selectedDate или при первом рендере, если токен есть
  useEffect(() => {
    if (selectedDate && token) {
      fetchStats(selectedDate);
    } else if (!token) {
      message.error('Нет токена авторизации. Повторите вход.');
    }
  }, [selectedDate, token]); // Добавляем token в зависимости, чтобы реагировать на его появление

  // Обработка выбора даты
  const handleDateChange = (date) => {
    if (date) {
      setSelectedDate(date);
    } else {
      // Если дата очищена, можно сбросить данные или ничего не делать
      setStatsData({ photographers: [], assistants: [] });
    }
  };

  // Загрузка статистики с сервера
  const fetchStats = async (dateToFetch) => {
    if (!dateToFetch) {
      message.error('Выберите дату');
      return;
    }

    const dateStr = dateToFetch.format('DD.MM.YYYY');
    setLoading(true);
    try {
      if (!token) {
        message.error('Нет токена авторизации. Повторите вход.');
        setLoading(false);
        return;
      }

      const response = await axios.get(
        `${API_BASE_URL}/ft/sp/daily_stats/`, // Ваш эндпоинт
        {
          headers: { Authorization: `Bearer ${token}` },
          params: { date: dateStr }, // Передаем дату как параметр запроса
        }
      );

      // Ожидаемый формат ответа:
      // {
      //   "photographers": ["Имя Фамилия - число", ...],
      //   "assistants": ["Имя Фамилия - число", ...]
      // }
      setStatsData(response.data);

    } catch (error) {
      console.error("Ошибка при загрузке статистики:", error);
      message.error(
        error.response?.data?.detail || 'Ошибка при загрузке статистики'
      );
      setStatsData({ photographers: [], assistants: [] }); // Сброс данных при ошибке
    } finally {
      setLoading(false);
    }
  };

  // Функция для преобразования строк "Имя Фамилия - число" в объекты для таблицы
  const parseStatsData = (dataArray) => {
    if (!Array.isArray(dataArray)) return [];
    return dataArray.map((item, index) => {
      const parts = item.split(' - ');
      return {
        key: index,
        name: parts[0] || 'N/A',
        count: parts[1] || '0',
      };
    });
  };

  const photographersTableData = parseStatsData(statsData.photographers);
  const assistantsTableData = parseStatsData(statsData.assistants);

  // Колонки для таблиц
  const columns = [
    {
      title: 'Имя Фамилия',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Результат',
      dataIndex: 'count',
      key: 'count',
      align: 'right',
    },
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '20px', minHeight: '100vh', width: '100%' }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>
          Дневная статистика по фотографам и ассистентам
        </Title>

        {/* Форма для выбора даты */}
        <Row justify="center" style={{ marginBottom: '24px' }}>
          <Col>
            <DatePicker
              locale={ruLocale}
              format="DD.MM.YYYY"
              value={selectedDate}
              onChange={handleDateChange}
              allowClear={false} // Если нужно запретить очистку даты
            />
          </Col>
          {/* Кнопка "Загрузить" может быть не нужна, если загрузка идет по изменению даты */}
          {/* <Col style={{ marginLeft: 8 }}>
            <Button type="primary" onClick={() => fetchStats(selectedDate)} loading={loading}>
              Загрузить
            </Button>
          </Col> */}
        </Row>

        {loading ? (
          <div style={{ textAlign: 'center', marginTop: '50px' }}>
            <Spin size="large" />
          </div>
        ) : (
          <Row gutter={[16, 32]} justify="center">
            {/* Секция Фотографов */}
            <Col xs={24} md={18} lg={12} xl={10} style={{maxWidth: '20vw'}}> {/* Ограничение ширины */}
              <Title level={4}>Фотографы:</Title>
              {photographersTableData.length > 0 ? (
                <Table
                  columns={columns}
                  dataSource={photographersTableData}
                  pagination={false} // Отключаем пагинацию, если список обычно небольшой
                  bordered
                  size="small"
                />
              ) : (
                <Text>Нет данных по фотографам за выбранную дату.</Text>
              )}
            </Col>

            {/* Секция Ассистентов */}
            <Col xs={24} md={18} lg={12} xl={10} style={{maxWidth: '20vw'}}> {/* Ограничение ширины */}
              <Title level={4} style={{ marginTop: '24px' }}>Ассистенты:</Title>
              {assistantsTableData.length > 0 ? (
                <Table
                  columns={columns}
                  dataSource={assistantsTableData}
                  pagination={false}
                  bordered
                  size="small"
                />
              ) : (
                <Text>Нет данных по ассистентам за выбранную дату.</Text>
              )}
            </Col>
          </Row>
        )}
      </Content>
    </Layout>
  );
};

export default DailyStatsPage;