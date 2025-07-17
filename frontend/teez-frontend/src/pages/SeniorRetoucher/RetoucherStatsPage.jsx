import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Table,
  DatePicker,
  message,
  Typography,
  Row,
  Col,
  Spin,
  Modal
} from 'antd';

// Локализация
import 'dayjs/locale/ru';
import dayjs from 'dayjs';
import ruLocale from 'antd/lib/date-picker/locale/ru_RU';

import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';
import { useNavigate } from 'react-router-dom';


const { Content } = Layout;
const { Title, Text } = Typography;

const RetoucherStatsPage = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const [loading, setLoading] = useState(false);
  const [statsData, setStatsData] = useState([]);
  const [token] = useState(localStorage.getItem('accessToken'));

  useEffect(() => {
    document.title = 'Дневная статистика по ретушерам';
  }, []);

  const fetchStats = useCallback(async (dateToFetch) => {
    if (!dateToFetch) {
      message.error('Выберите дату');
      return;
    }
     if (!token) {
      Modal.error({ title: 'Ошибка доступа', content: 'Токен не найден.', onOk: () => navigate('/login') });
      return;
    }

    // Бэкенд ожидает формат YYYY-MM-DD
    const dateStr = dateToFetch.format('YYYY-MM-DD');
    setLoading(true);
    try {
      const response = await axios.get(
        `${API_BASE_URL}/srt/statistics/retouchers/`,
        {
          headers: { Authorization: `Bearer ${token}` },
          params: { date: dateStr },
        }
      );
      // API возвращает массив объектов, который напрямую подходит для таблицы
      setStatsData(response.data);

    } catch (error) {
      console.error("Ошибка при загрузке статистики:", error);
      message.error(
        error.response?.data?.error || 'Ошибка при загрузке статистики'
      );
      setStatsData([]); // Сброс данных при ошибке
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

  useEffect(() => {
    if (selectedDate && token) {
      fetchStats(selectedDate);
    }
  }, [selectedDate, token, fetchStats]);

  const handleDateChange = (date) => {
    if (date) {
      setSelectedDate(date);
    } else {
      setStatsData([]);
    }
  };

  // Колонки для таблицы. dataIndex берем из ответа API.
  const columns = [
    {
      title: 'Имя Фамилия',
      dataIndex: 'full_name',
      key: 'full_name',
      width: 250
    },
    {
      title: 'Обработано',
      dataIndex: 'completed_and_checked_products',
      key: 'completed_and_checked_products',
      align: 'right',
      width: 150
    },
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '20px', minHeight: '100vh', width: '100%' }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: '24px' }}>
          Дневная статистика по ретушерам
        </Title>

        <Row justify="center" style={{ marginBottom: '24px' }}>
          <Col>
            <DatePicker
              locale={ruLocale}
              format="DD.MM.YYYY"
              value={selectedDate}
              onChange={handleDateChange}
              allowClear={false}
            />
          </Col>
        </Row>

        {loading ? (
          <div style={{ textAlign: 'center', marginTop: '50px' }}>
            <Spin size="large" />
          </div>
        ) : (
          <Row justify="center">
            <Col xs={35} md={19} lg={12} xl={6}>
              {statsData.length > 0 ? (
                <Table
                  columns={columns}
                  dataSource={statsData.map(item => ({...item, key: item.id}))} // Используем ID из ответа как ключ
                  pagination={false}
                  bordered
                  size="large"
                />
              ) : (
                <Text>Нет данных по ретушерам за выбранную дату.</Text>
              )}
            </Col>
          </Row>
        )}
      </Content>
    </Layout>
  );
};

export default RetoucherStatsPage;