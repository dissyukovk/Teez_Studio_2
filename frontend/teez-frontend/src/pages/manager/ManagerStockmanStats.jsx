import React, { useState, useEffect } from 'react';
import { Layout, DatePicker, Button, Spin, message, Typography, Modal, Table, Checkbox, Row, Col } from 'antd';
import axios from 'axios';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';
import updateLocale from 'dayjs/plugin/updateLocale';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import ruLocale from 'antd/lib/date-picker/locale/ru_RU';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title as ChartTitle,
  Tooltip as ChartTooltip,
  Legend as ChartLegend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

// Расширяем dayjs плагином customParseFormat
dayjs.extend(customParseFormat);
dayjs.extend(updateLocale);
dayjs.updateLocale('ru', {
  weekStart: 1, // 1 – значит, что неделя начинается с понедельника
});


// Регистрация компонентов Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ChartTitle,
  ChartTooltip,
  ChartLegend
);

const { Content } = Layout;
const { Title } = Typography;
const { RangePicker } = DatePicker;

// Набор цветов для графика
const COLORS = [
  '#FF6384', '#36A2EB', '#FFCE56',
  '#4BC0C0', '#9966FF', '#FF9F40',
  '#7CB342', '#F06292', '#BA68C8',
];

const ManagerStockmanStats = ({ darkMode, setDarkMode }) => {
  const [dateRange, setDateRange] = useState([null, null]);
  const [loading, setLoading] = useState(false);
  // baseChartData хранит исходные данные (без учета переключателей легенды)
  const [baseChartData, setBaseChartData] = useState({ labels: [], datasets: [] });
  // computedChartData – данные для отображения с учетом переключателей
  const [computedChartData, setComputedChartData] = useState({ labels: [], datasets: [] });
  const [overallData, setOverallData] = useState(null);

  // Состояния для кастомных переключателей легенды
  const [activeUsers, setActiveUsers] = useState({});
  const [activeOps, setActiveOps] = useState({
    'Принято': true,
    'Отправлено': true,
    'Итого': true,
  });

  const [errorModalVisible, setErrorModalVisible] = useState(false);

  useEffect(() => {
    document.title = 'Статистика по товароведам';
  }, []);

  // При изменении базовых данных или переключателей пересчитываем computedChartData
  useEffect(() => {
    if (!baseChartData.datasets) return;
    const newDatasets = baseChartData.datasets.map(ds => ({
      ...ds,
      // Скрываем, если отключён либо пользователь, либо тип операции
      hidden: !(activeUsers[ds.user] && activeOps[ds.op]),
    }));
    setComputedChartData({
      labels: baseChartData.labels,
      datasets: newDatasets,
    });
  }, [activeUsers, activeOps, baseChartData]);

  // Преобразование строки "DD.MM.YYYY" в Date с помощью dayjs
  const parseDate = (dateStr) => dayjs(dateStr, 'DD.MM.YYYY').toDate();

  // Загрузка статистики с бэкенда
  const fetchStats = async (startDate, endDate) => {
    setLoading(true);
    try {
      // Передаём параметры в формате "DD.MM.YYYY"
      const resp = await axios.get(`${API_BASE_URL}/mn/product-operations-stats/`, {
        params: { date_from: startDate, date_to: endDate },
      });
      const result = resp.data;
      // Ожидаемая структура ответа:
      // {
      //   "12.03.2025": {
      //       "Иван Иванов": { "Принято": 30, "Отправлено": 20, "Итого": 50 },
      //       "Петр Петров": { "Принято": 30, "Отправлено": 30, "Итого": 60 }
      //    },
      //   "13.03.2025": { ... },
      //   "Итого": {
      //       "Иван Иванов": { "Принято": X, "Отправлено": Y, "Итого": Z },
      //       "Петр Петров": { ... }
      //   }
      // }
      
      // Разделяем ежедневную статистику от итоговой сводки
      const dailyData = {};
      let overall = {};
      Object.keys(result).forEach((key) => {
        if (key === 'Итого') {
          overall = result[key];
        } else {
          dailyData[key] = result[key];
        }
      });

      // Получаем список дат и сортируем их
      const sortedDates = Object.keys(dailyData).sort((a, b) => parseDate(a) - parseDate(b));

      // Собираем уникальные имена товароведов
      const usersSet = new Set();
      sortedDates.forEach(date => {
        const dayStats = dailyData[date];
        Object.keys(dayStats).forEach(user => {
          usersSet.add(user);
        });
      });
      const users = Array.from(usersSet);

      // Инициализируем переключатели для пользователей
      const usersObj = {};
      users.forEach(user => {
        usersObj[user] = true;
      });
      setActiveUsers(usersObj);

      // Для каждого товароведа создаём 3 набора данных: "Принято", "Отправлено" и "Итого"
      let datasets = [];
      users.forEach((user, userIndex) => {
        const acceptedData = sortedDates.map(date => {
          const dayStats = dailyData[date];
          return dayStats && dayStats[user] ? dayStats[user]['Принято'] || 0 : 0;
        });
        const sentData = sortedDates.map(date => {
          const dayStats = dailyData[date];
          return dayStats && dayStats[user] ? dayStats[user]['Отправлено'] || 0 : 0;
        });
        const totalData = sortedDates.map((date, idx) => acceptedData[idx] + sentData[idx]);

        const colorAccepted = COLORS[(userIndex * 3) % COLORS.length];
        const colorSent = COLORS[(userIndex * 3 + 1) % COLORS.length];
        const colorTotal = COLORS[(userIndex * 3 + 2) % COLORS.length];

        datasets.push({
          label: `${user} - Принято`,
          data: acceptedData,
          backgroundColor: colorAccepted,
          user,
          op: 'Принято',
        });
        datasets.push({
          label: `${user} - Отправлено`,
          data: sentData,
          backgroundColor: colorSent,
          user,
          op: 'Отправлено',
        });
        datasets.push({
          label: `${user} - Итого`,
          data: totalData,
          backgroundColor: colorTotal,
          user,
          op: 'Итого',
        });
      });

      setBaseChartData({
        labels: sortedDates,
        datasets,
      });
      // Сохраняем итоговую сводку для таблицы и легенды
      setOverallData(overall);
    } catch (error) {
      console.error(error);
      message.error('Ошибка при загрузке статистики');
    } finally {
      setLoading(false);
    }
  };

  // Обработка выбора дат с ограничением до 31 дня
  const handleDateChange = (dates) => {
    if (dates && dates[0] && dates[1]) {
      const diff = dates[1].diff(dates[0], 'day');
      if (diff > 31) {
        setErrorModalVisible(true);
        return;
      }
    }
    setDateRange(dates);
  };

  const handleSubmit = () => {
    if (dateRange[0] && dateRange[1]) {
      const start = dateRange[0].format('DD.MM.YYYY');
      const end = dateRange[1].format('DD.MM.YYYY');
      fetchStats(start, end);
    }
  };

  const overallColumns = [
    { title: 'Товаровед', dataIndex: 'user', key: 'user' },
    { title: 'Принято', dataIndex: 'Принято', key: 'accepted' },
    { title: 'Отправлено', dataIndex: 'Отправлено', key: 'sent' },
    { title: 'Итого', dataIndex: 'Итого', key: 'total' },
  ];

  let overallTableData = [];
  if (overallData) {
    overallTableData = Object.keys(overallData).map(user => ({
      key: user,
      user,
      ...overallData[user],
    }));
  }

  const handleUserToggle = (user, checked) => {
    setActiveUsers(prev => ({ ...prev, [user]: checked }));
  };

  const handleOpToggle = (op, checked) => {
    setActiveOps(prev => ({ ...prev, [op]: checked }));
  };

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content
        style={{
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          minHeight: '100vh',
        }}
      >
        <Title level={2}>Статистика по товароведам</Title>
        <RangePicker
          locale={ruLocale}
          format="DD.MM.YYYY"
          value={dateRange}
          onChange={handleDateChange}
          style={{ marginBottom: 16 }}
        />
        <Button type="primary" onClick={handleSubmit} style={{ marginBottom: 16 }}>
          Получить данные
        </Button>
        <div style={{ width: '100%', maxWidth: '75vw', marginBottom: 16 }}>
          <Row gutter={[16, 8]}>
            <Col span={12}>
              <Title level={4}>Товароведы</Title>
              {Object.keys(activeUsers).map(user => (
                <Checkbox
                  key={user}
                  checked={activeUsers[user]}
                  onChange={(e) => handleUserToggle(user, e.target.checked)}
                >
                  {user}
                  {overallData && overallData[user] && overallData[user]['Итого'] !== undefined
                    ? ` - Итого: ${overallData[user]['Итого']}`
                    : ''}
                </Checkbox>
              ))}
            </Col>
            <Col span={12}>
              <Title level={4}>Операции</Title>
              {['Принято', 'Отправлено', 'Итого'].map(op => (
                <Checkbox
                  key={op}
                  checked={activeOps[op]}
                  onChange={(e) => handleOpToggle(op, e.target.checked)}
                >
                  {op}
                </Checkbox>
              ))}
            </Col>
          </Row>
        </div>
        {loading ? (
          <Spin />
        ) : (
          <>
            <div style={{ width: '100%', maxWidth: '75vw', marginBottom: 32 }}>
              <Bar
                data={computedChartData}
                options={{
                  responsive: true,
                  plugins: {
                    legend: { display: false },
                    title: {
                      display: true,
                      text: 'Дневная статистика по товароведам',
                    },
                    tooltip: {
                      callbacks: {
                        label: (tooltipItem) =>
                          `${tooltipItem.dataset.label}: ${tooltipItem.parsed.y}`,
                      },
                    },
                  },
                  scales: {
                    x: {
                      title: { display: true, text: 'Дата' },
                    },
                    y: {
                      title: { display: true, text: 'Количество' },
                    },
                  },
                }}
              />
            </div>
            {overallData && (
              <div style={{ width: '100%', maxWidth: '75vw' }}>
                <Title level={4}>Итоговая статистика за период</Title>
                <Table
                  columns={overallColumns}
                  dataSource={overallTableData}
                  pagination={false}
                  bordered
                />
              </div>
            )}
          </>
        )}
        <Modal
          title="Ошибка выбора дат"
          visible={errorModalVisible}
          onOk={() => setErrorModalVisible(false)}
          onCancel={() => setErrorModalVisible(false)}
          okText="Закрыть"
        >
          <p>Можно выбрать период только до 31 дня</p>
        </Modal>
      </Content>
    </Layout>
  );
};

export default ManagerStockmanStats;
