import React, { useState, useEffect } from 'react';
import {
  Layout,
  DatePicker,
  Button,
  Spin,
  message,
  Typography,
  Row,
  Col,
  Statistic,
  Card,
  Space,
  Empty,
  Collapse,
  Divider,
  List
} from 'antd';
import { UserOutlined, AppstoreOutlined, CheckCircleOutlined, ClockCircleOutlined, PercentageOutlined, RiseOutlined } from '@ant-design/icons';
import axios from 'axios';
import dayjs from 'dayjs';

// Импорт русской локали для DatePicker
import 'dayjs/locale/ru';
import locale from 'antd/es/date-picker/locale/ru_RU';

// Chart.js imports
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  Title as ChartTitle,
  Tooltip,
  Legend,
} from 'chart.js';
import { Bar, Pie } from 'react-chartjs-2';

import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  ArcElement,
  ChartTitle,
  Tooltip,
  Legend
);

const { Content } = Layout;
const { Title, Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;
const { Panel } = Collapse;

const COLORS = [
  '#36A2EB', '#FF6384', '#4BC0C0', '#FFCE56', '#9966FF', '#FF9F40',
  '#E7E9ED', '#7CB342', '#F06292', '#BA68C8', '#4DD0E1', '#FFB74D'
];

const AcceptanceDashboardPage = ({ darkMode, setDarkMode }) => {
  const [dateRange, setDateRange] = useState([dayjs().subtract(14, 'days'), dayjs()]);
  const [loading, setLoading] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);

  // Состояния для каждого графика
  const [barChartData, setBarChartData] = useState({ labels: [], datasets: [] });
  const [categoryPieData, setCategoryPieData] = useState({ labels: [], datasets: [] });
  const [stRequestTypePieData, setStRequestTypePieData] = useState({ labels: [], datasets: [] });
  const [moderationStatusPieData, setModerationStatusPieData] = useState({ labels: [], datasets: [] }); // <-- Состояние для нового графика

  const handleSubmit = () => {
    if (dateRange && dateRange[0] && dateRange[1]) {
      const start = dateRange[0].format('YYYY-MM-DD');
      const end = dateRange[1].format('YYYY-MM-DD');
      fetchDashboardData(start, end);
    } else {
      message.warning('Пожалуйста, выберите корректный период.');
    }
  };

  const fetchDashboardData = async (startDate, endDate) => {
    setLoading(true);
    setDashboardData(null);
    try {
      const token = localStorage.getItem('accessToken'); 
      const response = await axios.get(`${API_BASE_URL}/mn/acceptance-dashboard/`, {
        params: { start_date: startDate, end_date: endDate },
        headers: { Authorization: `Bearer ${token}` }
      });
      setDashboardData(response.data);
    } catch (error) {
      console.error('Ошибка при загрузке данных дэшборда:', error);
      message.error(error.response?.data?.error || 'Не удалось загрузить данные для дэшборда.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    document.title = 'Дэшборд по приемке';
    handleSubmit();
  }, []);

  useEffect(() => {
    if (dashboardData) {
      // 1. Bar Chart (Динамика)
      if (dashboardData.daily_data) {
        const dailyData = dashboardData.daily_data;
        const labels = Object.keys(dailyData).sort();
        setBarChartData({
          labels,
          datasets: [
            { label: 'Заказано', data: labels.map(d => dailyData[d].ordered_products_count || 0), backgroundColor: 'rgba(54, 162, 235, 0.6)' },
            { label: 'Принято', data: labels.map(d => dailyData[d].accepted_products_count || 0), backgroundColor: 'rgba(75, 192, 192, 0.6)' },
          ],
        });
      }
      
      if (dashboardData.totals) {
        // 2. Pie Chart (Топ принятых категорий)
        if (dashboardData.totals.top_accepted_categories) {
          const categories = dashboardData.totals.top_accepted_categories;
          setCategoryPieData({
            labels: categories.map(cat => cat.category_name || 'Без категории'),
            datasets: [{
              data: categories.map(cat => cat.count),
              backgroundColor: COLORS,
              borderColor: darkMode ? '#141414' : '#fff', borderWidth: 2,
            }]
          });
        }
        
        // 3. Pie Chart (Заказано по типам заявок)
        if (dashboardData.totals.ordered_products_by_type_ratio) {
          const requestTypes = dashboardData.totals.ordered_products_by_type_ratio;
          const totalCount = dashboardData.totals.ordered_products_count;
          const dataCounts = Object.values(requestTypes).map(ratio => Math.round(ratio * totalCount));
          setStRequestTypePieData({
            labels: Object.keys(requestTypes),
            datasets: [{
              data: dataCounts,
              backgroundColor: COLORS.slice().reverse(),
              borderColor: darkMode ? '#141414' : '#fff', borderWidth: 2,
            }]
          });
        }

        // 4. Pie Chart (Статусы модерации фото) <-- Новая логика
        if (dashboardData.totals.photo_moderation_status_ratio) {
            const modStatuses = dashboardData.totals.photo_moderation_status_ratio;
            // Общее количество принятых товаров для расчета абсолютных значений
            const totalAccepted = dashboardData.totals.accepted_products_count;
            const dataCounts = Object.values(modStatuses).map(ratio => Math.round(ratio * totalAccepted));

            setModerationStatusPieData({
                labels: Object.keys(modStatuses),
                datasets: [{
                    data: dataCounts,
                    backgroundColor: COLORS,
                    borderColor: darkMode ? '#141414' : '#fff', borderWidth: 2,
                }]
            });
        }
      }
    }
  }, [dashboardData, darkMode]);

  const StatCard = ({ title, value, icon, precision, suffix, loading }) => (
    <Card bordered={false}>
      <Spin spinning={loading}>
        <Statistic
          title={title} value={value} precision={precision} suffix={suffix}
          valueStyle={{ color: darkMode ? '#E8E8E8' : '#3f8600' }}
          prefix={icon}
        />
      </Spin>
    </Card>
  );

  const renderTotals = () => {
    if (!dashboardData || !dashboardData.totals) return null;
    const { totals } = dashboardData;
    
    const pieOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                let label = context.label || '';
                if (label) {
                  label += ': ';
                }
                if (context.parsed !== null) {
                  label += `${context.parsed} шт.`;
                }
                return label;
              }
            }
          }
        }
      };

    return (
      <div style={{width: '100%'}}>
        <Title level={3} style={{ marginBottom: '24px' }}>Итоги за период</Title>
        <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} md={8} lg={6}><StatCard title="Всего заказано" value={totals.ordered_products_count} icon={<AppstoreOutlined />} loading={loading} /></Col>
            <Col xs={24} sm={12} md={8} lg={6}><StatCard title="Всего принято" value={totals.accepted_products_count} icon={<CheckCircleOutlined />} loading={loading} /></Col>
            <Col xs={24} sm={12} md={8} lg={6}><StatCard title="Точность сборки" value={totals.assembly_accuracy_ratio * 100} suffix="%" precision={1} icon={<PercentageOutlined />} loading={loading} /></Col>
            <Col xs={24} sm={12} md={8} lg={6}><StatCard title="Новых товаров" value={totals.total_newly_accepted_products} icon={<RiseOutlined />} loading={loading} /></Col>
            <Col xs={24} sm={12} md={8} lg={6}><StatCard title="Время сборки (среднее)" value={totals.average_assembly_time} icon={<ClockCircleOutlined />} loading={loading} /></Col>
            <Col xs={24} sm={12} md={8} lg={6}><StatCard title="Время приемки SKU (среднее)" value={totals.average_acceptance_time_per_product} icon={<ClockCircleOutlined />} loading={loading} /></Col>
        </Row>
        <Divider />
        {/* Изменена сетка на 2x2 для 4 карточек */}
        <Row gutter={[24, 24]}>
            <Col xs={24} md={12} lg={12}>
                <Card title="Топ принятых категорий" bordered={false}>
                    <div style={{ height: '350px', position: 'relative' }}>
                        <Pie data={categoryPieData} options={pieOptions} />
                    </div>
                </Card>
            </Col>
            <Col xs={24} md={12} lg={12}>
                <Card title="Заказано по типам заявок" bordered={false}>
                    <div style={{ height: '350px', position: 'relative' }}>
                        <Pie data={stRequestTypePieData} options={pieOptions} />
                    </div>
                </Card>
            </Col>
            <Col xs={24} md={12} lg={12}>
                {/* Возвращенный график по статусам модерации */}
                <Card title="Статусы модерации при приемке" bordered={false}>
                    <div style={{ height: '350px', position: 'relative' }}>
                        <Pie data={moderationStatusPieData} options={pieOptions} />
                    </div>
                </Card>
            </Col>
            <Col xs={24} md={12} lg={12}>
                <Card title="Среднее время приемки по товароведам" bordered={false}>
                     <List
                        dataSource={Object.entries(totals.average_acceptance_time_by_user)}
                        renderItem={([user, time]) => (
                            <List.Item>
                                <UserOutlined style={{marginRight: 8}}/> <Text strong>{user}</Text>
                                <Text type="secondary">{time}</Text>
                            </List.Item>
                        )}
                    />
                </Card>
            </Col>
        </Row>
      </div>
    )
  }

  const renderDailyBreakdown = () => {
    if (!dashboardData || !dashboardData.daily_data) return null;
    const { daily_data } = dashboardData;
    const dates = Object.keys(daily_data).sort((a,b) => new Date(b) - new Date(a));

    return (
        <div style={{width: '100%', marginTop: '32px'}}>
            <Title level={3} style={{ marginBottom: '24px' }}>Статистика по дням</Title>
            <Collapse accordion>
                {dates.map(date => {
                    const day = daily_data[date];
                    return (
                        <Panel header={<Text strong>{dayjs(date).format('DD MMMM YYYY')}</Text>} key={date}>
                            <Row gutter={[16, 16]}>
                                <Col xs={12} md={6}><Statistic title="Заказано" value={day.ordered_products_count} /></Col>
                                <Col xs={12} md={6}><Statistic title="Принято" value={day.accepted_products_count} /></Col>
                                <Col xs={12} md={6}><Statistic title="Точность сборки" value={day.assembly_accuracy_ratio * 100} suffix="%" /></Col>
                                <Col xs={12} md={6}><Statistic title="Новые товары" value={(day.new_products_ratio * 100).toFixed(1)} suffix="%" /></Col>
                                <Col xs={24} md={12}><Statistic title="Среднее время сборки" value={day.average_assembly_time} /></Col>
                                <Col xs={24} md={12}><Statistic title="Среднее время приемки SKU" value={day.average_acceptance_time_per_product} /></Col>
                            </Row>
                        </Panel>
                    )
                })}
            </Collapse>
        </div>
    )
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '24px', margin: 0 }}>
        <Title level={2}>Дэшборд по приемке и заказам</Title>
        <Paragraph type="secondary">
          Аналитика по заказанным и принятым товарам. Выберите период для анализа.
        </Paragraph>
        
        <Space wrap style={{ marginBottom: '24px' }}>
          <RangePicker
            locale={locale}
            value={dateRange}
            onChange={setDateRange}
            format="DD.MM.YYYY"
            allowClear={false}
          />
          <Button type="primary" onClick={handleSubmit} loading={loading}>
            Обновить данные
          </Button>
        </Space>
        
        {loading && !dashboardData && <div style={{textAlign: 'center', padding: '50px'}}><Spin size="large" /></div>}
        
        {!loading && !dashboardData && 
            <Empty description="Нет данных для отображения. Выберите период и нажмите 'Обновить данные'." />
        }

        {dashboardData && (
          <>
            <Card style={{marginBottom: '24px'}}>
              <Title level={4}>Динамика заказов и приемок</Title>
              <div style={{ height: '350px', position: 'relative' }}>
                <Bar 
                  data={barChartData} 
                  options={{
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'top' } },
                    scales: { y: { beginAtZero: true } }
                  }} 
                />
              </div>
            </Card>
            {renderTotals()}
            {renderDailyBreakdown()}
          </>
        )}
      </Content>
    </Layout>
  );
};

export default AcceptanceDashboardPage;