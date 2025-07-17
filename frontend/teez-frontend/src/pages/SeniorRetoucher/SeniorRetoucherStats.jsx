import React, { useState, useEffect } from 'react';
import { Layout, DatePicker, Button, Spin, message, Typography, Modal, Table, Checkbox, Row, Col } from 'antd';
import axios from 'axios';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';
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

const { Content } = Layout;
const { Title } = Typography;
const { RangePicker } = DatePicker;

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ChartTitle,
  ChartTooltip,
  ChartLegend
);

const MAX_DATE_RANGE = 31; // Максимальное количество дней при выборе дат

const COLORS = [
  '#FF6384', '#36A2EB', '#FFCE56',
  '#4BC0C0', '#9966FF', '#FF9F40',
  '#7CB342', '#F06292', '#BA68C8',
  '#E57373', '#F44336', '#FFB300',
];

const SeniorRetoucherStats = ({ darkMode, setDarkMode }) => {
  // --- Состояния ---
  const [dateRange, setDateRange] = useState([null, null]);
  const [loading, setLoading] = useState(false);

  // Данные для сводной таблицы (pivot)
  // Теперь для каждого ретушёра формируется 4 строки: uploaded, rejected, total, percent
  const [pivotTableData, setPivotTableData] = useState([]);
  // Массив дат (сортированный)
  const [dateKeys, setDateKeys] = useState([]);
  // Набор данных для диаграммы
  const [chartData, setChartData] = useState(null);

  // Флаги для показа/скрытия данных на диаграмме
  const [showAccepted, setShowAccepted] = useState(true);
  const [showRejected, setShowRejected] = useState(true);

  const [errorModalVisible, setErrorModalVisible] = useState(false);

  // Токен авторизации (например, берём из localStorage)
  const token = localStorage.getItem('accessToken');

  useEffect(() => {
    document.title = 'Статистика по рендерам';
  }, []);

  // Обработка изменения дат с проверкой максимального интервала
  const handleDateChange = (dates) => {
    if (dates && dates[0] && dates[1]) {
      const diff = dates[1].diff(dates[0], 'day');
      if (diff > MAX_DATE_RANGE) {
        message.error("слишком большой промежуток дат");
        setErrorModalVisible(true);
        return;
      }
    }
    setDateRange(dates);
  };

  // Запрос данных с бэкенда и подготовка сводной таблицы и данных для диаграммы
  const handleSubmit = async () => {
    if (!dateRange[0] || !dateRange[1]) {
      message.error("Выберите даты");
      return;
    }
    const start = dateRange[0].format('DD.MM.YYYY');
    const end = dateRange[1].format('DD.MM.YYYY');
    setLoading(true);

    try {
      if (!token) {
        message.error("Нет токена авторизации. Повторите вход.");
        setLoading(false);
        return;
      }

      const response = await axios.get(
        `${API_BASE_URL}/rd/senior_retoucher_stats/${start}/${end}/`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = response.data;
      // Пример структуры data:
      // {
      //   "02.04.2025": {
      //       "Retoucher Test": { total: 3, Processed: 2, Rejected: 1 },
      //       "Кенесары Дисюков": { total: 26, Processed: 6, Rejected: 20 }
      //   },
      //   "03.04.2025": {
      //       "Кенесары Дисюков": { total: 6, Processed: 1, Rejected: 5 }
      //   }
      // }

      // 1) Собираем отсортированный список дат
      const keys = Object.keys(data).sort(
        (a, b) => dayjs(a, 'DD.MM.YYYY').toDate() - dayjs(b, 'DD.MM.YYYY').toDate()
      );
      setDateKeys(keys);

      // 2) Собираем множество всех ретушёров
      const retouchersSet = new Set();
      keys.forEach(date => {
        const dayData = data[date];
        Object.keys(dayData).forEach(r => {
          retouchersSet.add(r);
        });
      });
      const retouchers = Array.from(retouchersSet);

      // 3) Формируем сводную таблицу по ретушёрам.
      // Для каждого ретушёра создаём 4 строки:
      //  - rowType: 'uploaded'
      //  - rowType: 'rejected'
      //  - rowType: 'total'
      //  - rowType: 'percent'
      // Поле modName сохраняет имя ретушёра.
      const pivotResult = [];
      retouchers.forEach((retName) => {
        const rowUploaded = { key: `${retName}-uploaded`, modName: retName, rowType: 'uploaded' };
        const rowRejected = { key: `${retName}-rejected`, modName: retName, rowType: 'rejected' };
        const rowTotal = { key: `${retName}-total`, modName: retName, rowType: 'total' };
        const rowPercent = { key: `${retName}-percent`, modName: retName, rowType: 'percent' };

        keys.forEach((date) => {
          const dayData = data[date] || {};
          const userStats = dayData[retName] || { Processed: 0, Rejected: 0, total: 0 };
          const accepted = userStats.Processed || 0;
          const rejected = userStats.Rejected || 0;
          const total = userStats.total || 0;
          const sumPR = accepted + rejected;
          const percentUploaded = sumPR > 0 ? ((accepted / sumPR) * 100).toFixed(2) : '0.00';

          // Здесь для строки типа "uploaded" покажем число принятых (будет называться "Загружено")
          rowUploaded[date] = accepted;
          rowRejected[date] = rejected;
          rowTotal[date] = total;
          rowPercent[date] = `${percentUploaded}%`;
        });
        pivotResult.push(rowUploaded, rowRejected, rowTotal, rowPercent);
      });
      setPivotTableData(pivotResult);

      // 4) Формируем данные для диаграммы (stacked bar)
      // Каждая дата — метка (label); для каждого ретушёра — 2 dataset (принято/отклонено) с общим stack = имя ретушёра
      let colorIndex = 0;
      const chartDatasets = [];

      retouchers.forEach(retName => {
        const acceptedData = keys.map(d => {
          const dayData = data[d];
          return dayData && dayData[retName] ? (dayData[retName].Processed || 0) : 0;
        });
        const rejectedData = keys.map(d => {
          const dayData = data[d];
          return dayData && dayData[retName] ? (dayData[retName].Rejected || 0) : 0;
        });

        const baseColor = COLORS[colorIndex % COLORS.length];
        // Прозрачность для различия
        const acceptedColor = baseColor + 'CC';
        const rejectedColor = baseColor + '66';
        colorIndex++;

        chartDatasets.push({
          label: `${retName} - Принято`,
          data: acceptedData,
          backgroundColor: acceptedColor,
          stack: retName,
          hidden: !showAccepted,
        });
        chartDatasets.push({
          label: `${retName} - Отклонено`,
          data: rejectedData,
          backgroundColor: rejectedColor,
          stack: retName,
          hidden: !showRejected,
        });
      });

      setChartData({
        labels: keys,
        datasets: chartDatasets,
      });

    } catch (error) {
      console.error(error);
      message.error("Ошибка при загрузке статистики");
    } finally {
      setLoading(false);
    }
  };

  // --- Формируем колонки для сводной таблицы ---  
  // Первый столбец «Модератор» объединяет 4 строки (rowSpan=4), второй — «Тип»
  const pivotColumns = [
    {
      title: 'Модератор',
      dataIndex: 'modName',
      key: 'modName',
      fixed: 'left',
      width: 160,
      render: (value, row, index) => {
        const obj = {
          children: value,
          props: {},
        };
        // Находим первую строку в группе по modName
        const groupRows = pivotTableData.filter(r => r.modName === row.modName);
        const firstRowIndex = pivotTableData.findIndex(r => r.modName === row.modName);
        // Если текущая строка — первая в группе, объединяем 4 строки (rowSpan = groupRows.length, тут должно быть 4)
        if (index === firstRowIndex) {
          obj.props.rowSpan = groupRows.length;
        } else {
          obj.props.rowSpan = 0;
        }
        return obj;
      },
    },
    {
      title: 'Тип',
      dataIndex: 'rowType',
      key: 'rowType',
      fixed: 'left',
      width: 140,
      render: (rowType) => {
        switch (rowType) {
          case 'uploaded': return 'Принято';
          case 'rejected': return 'Отклонено';
          case 'total': return 'Всего';
          case 'percent': return '% принятых';
          default: return '';
        }
      },
    },
    ...dateKeys.map((date) => ({
      title: date,
      dataIndex: date,
      key: date,
      width: 120,
      align: 'center',
    })),
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16, minHeight: '100vh' }}>
        <Title level={2}>Статистика по рендерам</Title>

        {/* Выбор периода дат */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col>
            <RangePicker
              locale={ruLocale}
              format="DD.MM.YYYY"
              value={dateRange}
              onChange={handleDateChange}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={handleSubmit}>
              Получить данные
            </Button>
          </Col>
        </Row>

        {/* Чекбоксы для показа/скрытия данных на диаграмме */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col>
            <Checkbox
              checked={showAccepted}
              onChange={(e) => setShowAccepted(e.target.checked)}
            >
              Принятых
            </Checkbox>
          </Col>
          <Col>
            <Checkbox
              checked={showRejected}
              onChange={(e) => setShowRejected(e.target.checked)}
            >
              Отклонённых
            </Checkbox>
          </Col>
        </Row>

        {loading ? (
          <Spin />
        ) : (
          <>
            {/* Стековая диаграмма */}
            {chartData && chartData.labels && chartData.labels.length > 0 && (
              <div style={{ width: '100%', maxWidth: '80vw', marginBottom: 40 }}>
                <Bar
                  data={chartData}
                  options={{
                    responsive: true,
                    plugins: {
                      legend: { display: true },
                      title: {
                        display: true,
                        text: 'Дневная статистика по ретушёрам (стековая диаграмма)',
                      },
                      tooltip: {
                        callbacks: {
                          label: (tooltipItem) => {
                            const label = tooltipItem.dataset.label || '';
                            const val = tooltipItem.parsed.y || 0;
                            return `${label}: ${val}`;
                          },
                        },
                      },
                    },
                    scales: {
                      x: { stacked: true },
                      y: { stacked: true },
                    },
                  }}
                />
              </div>
            )}

            {/* Сводная таблица (первый столбец – Модератор с объединением, второй – Тип, далее даты) */}
            <Title level={4}>Сводная таблица по датам</Title>
            <Table
              columns={pivotColumns}
              dataSource={pivotTableData}
              pagination={false}
              bordered
              scroll={{ x: 'max-content' }}
            />
          </>
        )}

        {/* Модальное окно с сообщением об ошибке выбора дат */}
        <Modal
          title="Ошибка выбора дат"
          visible={errorModalVisible}
          onOk={() => setErrorModalVisible(false)}
          onCancel={() => setErrorModalVisible(false)}
          okText="Закрыть"
        >
          <p>Можно выбрать период только до {MAX_DATE_RANGE} дней</p>
        </Modal>
      </Content>
    </Layout>
  );
};

export default SeniorRetoucherStats;
