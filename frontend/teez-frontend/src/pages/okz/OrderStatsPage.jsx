import React, { useState, useEffect } from 'react';
import {
  Layout,
  DatePicker,
  Button,
  Spin,
  message,
  Typography,
  Card,
  Row,
  Col,
  Statistic,
  Space,
} from 'antd';
import axios from 'axios';
import dayjs from 'dayjs';

// Импорт русской локали для DatePicker
import 'dayjs/locale/ru';
import locale from 'antd/es/date-picker/locale/ru_RU';

import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const OrderStatsPage = ({ darkMode, setDarkMode }) => {
  const [dateRange, setDateRange] = useState([null, null]);
  const [loading, setLoading] = useState(false);
  const [statsData, setStatsData] = useState(null);

  useEffect(() => {
    document.title = 'Статистика по заказам';
  }, []);

  const fetchStats = async (startDate, endDate) => {
    setLoading(true);
    setStatsData(null); // Сбрасываем старые данные перед новым запросом
    try {
      const resp = await axios.get(`${API_BASE_URL}/okz/order-stats/`, {
        params: {
          // Отправляем даты в формате, который ожидает бэкенд
          date_from: startDate,
          date_to: endDate,
        },
      });
      setStatsData(resp.data);
      if (resp.data.order_count === 0) {
        message.info('Заказы за выбранный период не найдены.');
      }
    } catch (error) {
      console.error('Ошибка при загрузке статистики по заказам:', error);
      const errorMsg = error.response?.data?.error || 'Произошла ошибка при загрузке статистики.';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    if (dateRange && dateRange[0] && dateRange[1]) {
      // Форматируем даты в нужный для API формат
      const start = dateRange[0].format('DD.MM.YYYY');
      const end = dateRange[1].format('DD.MM.YYYY');
      fetchStats(start, end);
    } else {
      message.warning('Пожалуйста, выберите период.');
    }
  };

  const renderStats = () => {
    if (loading) {
      return <Spin size="large" style={{ marginTop: 50 }} />;
    }

    if (!statsData) {
      return <Text style={{ marginTop: 24, color: darkMode ? 'rgba(255, 255, 255, 0.65)' : 'rgba(0, 0, 0, 0.45)' }}>Выберите период и нажмите "Получить данные".</Text>;
    }

    // Если данных нет, показываем сообщение
    if (statsData.order_count === 0) {
        return (
            <Card title="Результат" style={{ width: '100%', maxWidth: 600, marginTop: 24 }}>
               <Text>Нет данных для отображения за выбранный период.</Text>
            </Card>
         );
    }

    return (
      <Card
        title={`Статистика за период`}
        style={{ width: '100%', maxWidth: 600, marginTop: 24 }}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12}>
            <Statistic
              title="Количество заказов"
              value={statsData.order_count}
              valueStyle={{ color: '#3f8600' }}
              formatter={(value) => value}
            />
          </Col>
          <Col xs={24} sm={12}>
            <Statistic
              title="Количество SKU"
              value={statsData.sku_count}
              valueStyle={{ color: '#1890ff' }}
              formatter={(value) => value}
            />
          </Col>
        </Row>
      </Card>
    );
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content
          style={{
            padding: 24,
            margin: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            background: darkMode ? '#141414' : '#fff',
          }}
        >
          <Title level={2} style={{ color: darkMode ? '#fff' : 'inherit' }}>Статистика по заказам</Title>
          <Text type="secondary" style={{ marginBottom: 24, textAlign: 'center' }}>
            Выберите период для получения данных о количестве заказов и SKU.
          </Text>

          <Space direction="vertical" size="middle">
            <RangePicker
              locale={locale}
              format="DD.MM.YYYY" // Формат отображения в поле
              value={dateRange}
              onChange={setDateRange}
            />
            <Button
              type="primary"
              onClick={handleSubmit}
              loading={loading}
              style={{ width: '100%' }}
            >
              Получить данные
            </Button>
          </Space>

          {renderStats()}

        </Content>
      </Layout>
    </Layout>
  );
};

export default OrderStatsPage;