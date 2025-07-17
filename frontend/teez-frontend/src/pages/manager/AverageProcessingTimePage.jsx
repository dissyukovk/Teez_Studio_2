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
  Divider,
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

const AverageProcessingTimePage = ({ darkMode, setDarkMode }) => {
  const [dateRange, setDateRange] = useState([null, null]);
  const [loading, setLoading] = useState(false);
  const [statsData, setStatsData] = useState(null);

  useEffect(() => {
    document.title = 'Среднее время обработки';
  }, []);

  const fetchStats = async (startDate, endDate) => {
    setLoading(true);
    setStatsData(null);
    try {
      const resp = await axios.get(`${API_BASE_URL}/mn/average-processing-time/`, {
        params: {
          start_date: startDate,
          end_date: endDate,
        },
      });
      setStatsData(resp.data);
    } catch (error) {
      console.error('Ошибка при загрузке статистики:', error);
      message.error('Произошла ошибка при загрузке статистики.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => {
    if (dateRange && dateRange[0] && dateRange[1]) {
      const start = dateRange[0].format('YYYY-MM-DD');
      const end = dateRange[1].format('YYYY-MM-DD');
      fetchStats(start, end);
    } else {
      message.warning('Пожалуйста, выберите период.');
    }
  };

  // ✅ Функция рендера полностью переработана для новой структуры ответа
  const renderStats = () => {
    if (loading) {
      return <Spin size="large" style={{ marginTop: 50 }} />;
    }

    if (!statsData) {
      return <Text style={{ marginTop: 24 }}>Выберите период и нажмите "Получить данные".</Text>;
    }
    
    const { period, product_storage_time, order_to_acceptance_time } = statsData;

    // Проверяем, есть ли хоть какие-то данные для отображения
    const noDataAvailable = 
      product_storage_time.average_duration_seconds === 0 &&
      order_to_acceptance_time.average_duration_seconds === 0;

    if (noDataAvailable) {
      return (
         <Card title="Результат" style={{ width: '100%', maxWidth: 600, marginTop: 24 }}>
            <Text>Нет данных для расчета за выбранный период.</Text>
         </Card>
      );
    }

    // Рендерим карточки только для тех метрик, по которым есть данные
    return (
      <div style={{ width: '100%', maxWidth: 700, marginTop: 24 }}>
        <Title level={4} style={{ textAlign: 'center', marginBottom: 16 }}>
          Статистика за период с {period.start_date} по {period.end_date}
        </Title>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>

          {/* === Блок 1: Время нахождения товара на ФС === */}
          {product_storage_time.average_duration_seconds > 0 && (
            <Card title="Время нахождения товара на ФС">
              <Row gutter={[16, 16]}>
                <Col xs={24} sm={12}>
                  <Statistic
                    title="Средняя длительность"
                    value={product_storage_time.average_duration_human_readable}
                  />
                </Col>
                <Col xs={24} sm={12}>
                  <Statistic
                    title="В секундах"
                    value={product_storage_time.average_duration_seconds}
                    suffix=" сек."
                  />
                </Col>
              </Row>
            </Card>
          )}

          {/* === Блок 2: Время от заказа до приемки === */}
          {order_to_acceptance_time.average_duration_seconds > 0 && (
             <Card title="Время от создания заказа до приемки">
               <Row gutter={[16, 16]}>
                <Col xs={24} sm={12}>
                  <Statistic
                    title="Средняя длительность"
                    value={order_to_acceptance_time.average_duration_human_readable}
                  />
                </Col>
                <Col xs={24} sm={12}>
                  <Statistic
                    title="В секундах"
                    value={order_to_acceptance_time.average_duration_seconds}
                    suffix=" сек."
                  />
                </Col>
              </Row>
            </Card>
          )}

        </Space>
      </div>
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
          }}
        >
          <Title level={2}>Среднее время обработки</Title>
          <Text type="secondary" style={{ marginBottom: 24, textAlign: 'center' }}>
            Аналитика среднего времени нахождения товаров на ФС и времени обработки заказов.
          </Text>

          <Space direction="vertical" size="middle">
            <RangePicker
              locale={locale}
              format="DD.MM.YYYY"
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

export default AverageProcessingTimePage;