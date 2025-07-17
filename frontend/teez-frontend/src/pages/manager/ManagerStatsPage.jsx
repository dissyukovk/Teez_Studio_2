import React, { useState, useEffect } from 'react';
import { Layout, DatePicker, Button, Spin, message, Typography, Modal } from 'antd';
import axios from 'axios';
// Chart.js + react-chartjs-2
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title as ChartTitle,
  Tooltip as ChartTooltip,
  Legend,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

// Регистрация необходимых компонентов Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ChartTitle,
  ChartTooltip,
  Legend
);

const { Content } = Layout;
const { Title } = Typography;
const { RangePicker } = DatePicker;

// Набор цветов для разных категорий (опционально)
const COLORS = [
  '#FF6384', '#36A2EB', '#FFCE56',
  '#4BC0C0', '#9966FF', '#FF9F40',
  '#7CB342', '#F06292', '#BA68C8',
];

const ManagerStatsPage = ({ darkMode, setDarkMode }) => {
  const [dateRange, setDateRange] = useState([null, null]);
  const [loading, setLoading] = useState(false);

  // Состояние для данных, подготовленных специально для Chart.js
  const [chartData, setChartData] = useState({
    labels: [],
    datasets: [],
  });

  useEffect(() => {
      document.title = 'Общая статистика ФС';
    }, []);

  // Модальное окно для ошибок при выборе дат
  const [errorModalVisible, setErrorModalVisible] = useState(false);

  // Функция для загрузки данных с бэкенда
  const fetchStats = async (startDate, endDate) => {
    setLoading(true);
    try {
      const resp = await axios.get(`${API_BASE_URL}/mn/fsallstats/`, {
        params: { start_date: startDate, end_date: endDate },
      });
      const result = resp.data;  // объект вида { "2025-03-12": { "Заказано": 2002, ... }, ... }

      // Преобразуем объект в массив [{ date, category, count }, ...]
      const rawArray = [];
      Object.keys(result).forEach((date) => {
        const stats = result[date];
        Object.keys(stats).forEach((category) => {
          rawArray.push({
            date,
            category,
            count: stats[category],
          });
        });
      });

      // Теперь собираем данные для Chart.js:
      // 1) Уникальные даты -> labels
      const uniqueDates = [...new Set(rawArray.map(item => item.date))].sort();
      // 2) Уникальные категории -> отдельные наборы (datasets)
      const uniqueCategories = [...new Set(rawArray.map(item => item.category))];

      // Создаём объект для хранения значений: category -> [counts по индексам дат]
      const categoryMap = {};
      uniqueCategories.forEach(cat => {
        categoryMap[cat] = new Array(uniqueDates.length).fill(0);
      });

      // Заполняем categoryMap, сопоставляя (date, category) -> count
      rawArray.forEach(({ date, category, count }) => {
        const dateIndex = uniqueDates.indexOf(date);
        if (dateIndex !== -1) {
          categoryMap[category][dateIndex] = count;
        }
      });

      // Формируем datasets для Chart.js с суммой значений в label
      const datasets = uniqueCategories.map((cat, idx) => {
        const total = categoryMap[cat].reduce((sum, value) => sum + value, 0);
        return {
          label: `${cat} - ${total}`,
          data: categoryMap[cat],
          backgroundColor: COLORS[idx % COLORS.length],
        };
      });

      // Обновляем состояние chartData
      setChartData({
        labels: uniqueDates, // Массив дат
        datasets,
      });
    } catch (error) {
      message.error('Ошибка при загрузке статистики');
    } finally {
      setLoading(false);
    }
  };

  // Проверяем выбранный диапазон и устанавливаем, если <= 31 день
  const handleDateChange = (dates) => {
    if (dates && dates[0] && dates[1]) {
      const diff = dates[1].diff(dates[0], 'day'); // разница в днях
      if (diff > 31) {
        setErrorModalVisible(true); // показываем модалку
        return; // не устанавливаем dateRange
      }
    }
    // Если всё ок, сохраняем в state
    setDateRange(dates);
  };

  // Обработчик клика на «Обновить данные»
  const handleSubmit = () => {
    if (dateRange[0] && dateRange[1]) {
      const start = dateRange[0].format('YYYY-MM-DD');
      const end = dateRange[1].format('YYYY-MM-DD');
      fetchStats(start, end);
    }
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
        {/* 1. Изменённый заголовок страницы */}
        <Title level={2}>Общая статистика ФС</Title>

        {/* Выбор дат */}
        <RangePicker
          format="DD.MM.YYYY"
          value={dateRange}
          onChange={handleDateChange}
          style={{ marginBottom: 16 }}
        />

        <Button
          type="primary"
          onClick={handleSubmit}
          style={{ marginBottom: 16 }}
        >
          Получить данные
        </Button>

        {loading ? (
          <Spin />
        ) : (
          <div style={{ width: '100%', maxWidth: '75vw' }}>
            {/* Сам график */}
            <Bar
              data={chartData}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    position: 'top',
                  },
                  title: {
                    display: true,
                  },
                  tooltip: {
                    // Здесь можно настроить формат подсказки (при желании)
                    callbacks: {
                      label: (tooltipItem) => {
                        // tooltipItem.dataset.label = категория
                        // tooltipItem.parsed.y = значение
                        return `${tooltipItem.dataset.label}: ${tooltipItem.parsed.y}`;
                      },
                    },
                  },
                },
                // Настройки осей, если нужно
                scales: {
                  x: {
                    title: {
                      display: true,
                      text: 'Дата',
                    },
                  },
                  y: {
                    title: {
                      display: true,
                      text: 'Количество',
                    },
                  },
                },
              }}
            />
          </div>
        )}

        {/* 2. Модальное окно, если диапазон > 31 дня */}
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

export default ManagerStatsPage;
