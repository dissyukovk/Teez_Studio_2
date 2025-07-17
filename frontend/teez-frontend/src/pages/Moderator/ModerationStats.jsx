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
  Checkbox,
  Spin,
  Modal
} from 'antd';

// Локализация
import 'dayjs/locale/ru';
import dayjs from 'dayjs';
import ruLocale from 'antd/lib/date-picker/locale/ru_RU';

// Chart.js и react-chartjs-2
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
import axios from 'axios';
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

// Максимальное количество дней в интервале
const MAX_DATE_RANGE = 31;

// Набор цветов для диаграммы
const COLORS = [
  '#FF6384', '#36A2EB', '#FFCE56',
  '#4BC0C0', '#9966FF', '#FF9F40',
  '#7CB342', '#F06292', '#BA68C8',
  '#E57373', '#F44336', '#FFB300',
];

const ModerationStats = ({ darkMode, setDarkMode }) => {
  const [dateRange, setDateRange] = useState([]);
  const [loading, setLoading] = useState(false);

  // Для pivot-таблицы
  const [pivotTableData, setPivotTableData] = useState([]);
  const [dateKeys, setDateKeys] = useState([]);

  // Для диаграммы
  const [chartData, setChartData] = useState(null);

  // Чекбоксы (диаграмма)
  const [showUploaded, setShowUploaded] = useState(true);
  const [showRejected, setShowRejected] = useState(true);

  // Модальное окно при большом периоде
  const [errorModalVisible, setErrorModalVisible] = useState(false);

  // Токен авторизации (пример)
  const token = localStorage.getItem('accessToken');

  useEffect(() => {
    document.title = 'Статистика по загрузкам';
  }, []);

  // Обработка выбора дат с проверкой интервала
  const handleDateChange = (dates) => {
    if (dates && dates[0] && dates[1]) {
      const diff = dates[1].diff(dates[0], 'day');
      if (diff > MAX_DATE_RANGE) {
        message.error('Слишком большой промежуток дат');
        setErrorModalVisible(true);
        return;
      }
    }
    setDateRange(dates);
  };

  // Загрузка статистики
  const fetchStats = async () => {
    if (!dateRange || dateRange.length !== 2) {
      message.error('Выберите диапазон дат');
      return;
    }

    const dateFrom = dateRange[0].format('DD.MM.YYYY');
    const dateTo = dateRange[1].format('DD.MM.YYYY');

    setLoading(true);
    try {
      if (!token) {
        message.error('Нет токена авторизации. Повторите вход.');
        setLoading(false);
        return;
      }

      const response = await axios.get(
        `${API_BASE_URL}/rd/senior_moderation_stats/${dateFrom}/${dateTo}/`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      // Ожидаемая структура ответа:
      // {
      //   "15.03.2025": {
      //       "Модератор A": { total: 5, Uploaded: 3, Rejected: 2 },
      //       "Модератор B": { total: 10, Uploaded: 7, Rejected: 3 }
      //   },
      //   "16.03.2025": { ... },
      //   ...
      // }

      const data = response.data;

      // Собираем и сортируем список дат
      const keys = Object.keys(data).sort(
        (a, b) => dayjs(a, 'DD.MM.YYYY').toDate() - dayjs(b, 'DD.MM.YYYY').toDate()
      );
      setDateKeys(keys);

      // Собираем список модераторов
      const moderatorsSet = new Set();
      keys.forEach((dateKey) => {
        const dayData = data[dateKey];
        Object.keys(dayData).forEach((moderatorName) => {
          moderatorsSet.add(moderatorName);
        });
      });
      const moderators = Array.from(moderatorsSet);

      // Формируем pivot-таблицу в формате:
      //   4 строки (rowType= uploaded, rejected, total, percent) на каждого модератора
      //   Первый столбец объединён (rowSpan=4)
      //   Второй столбец — «Тип»
      //   Остальные столбцы — даты
      const pivotRows = [];
      moderators.forEach((modName) => {
        const groupId = `mod_${modName}`; // для rowSpan

        // 4 строки = разные rowType
        const rowUploaded = { key: `${modName}-uploaded`, groupId, modName, rowType: 'uploaded' };
        const rowRejected = { key: `${modName}-rejected`, groupId, modName, rowType: 'rejected' };
        const rowTotal = { key: `${modName}-total`, groupId, modName, rowType: 'total' };
        const rowPercent = { key: `${modName}-percent`, groupId, modName, rowType: 'percent' };

        keys.forEach((dateKey) => {
          const dayData = data[dateKey];
          const stats = dayData[modName] || { total: 0, Uploaded: 0, Rejected: 0 };

          const uploadedVal = stats.Uploaded || 0;
          const rejectedVal = stats.Rejected || 0;
          const totalVal = stats.total || 0;
          const sumUR = uploadedVal + rejectedVal;
          const percentUploaded = sumUR > 0 ? ((uploadedVal / sumUR) * 100).toFixed(2) : '0.00';

          rowUploaded[dateKey] = uploadedVal;
          rowRejected[dateKey] = rejectedVal;
          rowTotal[dateKey] = totalVal;
          rowPercent[dateKey] = `${percentUploaded}%`;
        });

        pivotRows.push(rowUploaded, rowRejected, rowTotal, rowPercent);
      });
      setPivotTableData(pivotRows);

      // Формируем данные для диаграммы (stacked bar)
      let colorIndex = 0;
      const chartDatasets = [];

      moderators.forEach((modName) => {
        // массивы по датам
        const arrUploaded = keys.map((dateKey) => {
          const dayStats = data[dateKey][modName] || { Uploaded: 0 };
          return dayStats.Uploaded || 0;
        });
        const arrRejected = keys.map((dateKey) => {
          const dayStats = data[dateKey][modName] || { Rejected: 0 };
          return dayStats.Rejected || 0;
        });

        const baseColor = COLORS[colorIndex % COLORS.length];
        const uploadedColor = baseColor + 'CC'; 
        const rejectedColor = baseColor + '66';
        colorIndex++;

        chartDatasets.push({
          label: `${modName} - Загружено`,
          data: arrUploaded,
          backgroundColor: uploadedColor,
          stack: modName,
          hidden: !showUploaded,
        });
        chartDatasets.push({
          label: `${modName} - Отклонено`,
          data: arrRejected,
          backgroundColor: rejectedColor,
          stack: modName,
          hidden: !showRejected,
        });
      });

      setChartData({
        labels: keys,
        datasets: chartDatasets,
      });
    } catch (error) {
      console.error(error);
      message.error(error.response?.data?.error || 'Ошибка при загрузке статистики');
    } finally {
      setLoading(false);
    }
  };

  // Настраиваем колонки для pivot-таблицы
  // 1) «Модератор» — объединяем 4 строки (rowSpan=4)
  // 2) «Тип» — rowType => «Загружено», «Отклонено», «Всего», «% загруженных»
  // 3) Остальные — даты
  const pivotColumns = [
    {
      title: 'Модератор',
      dataIndex: 'modName',
      key: 'modName',
      fixed: 'left',
      width: 160,
      render: (value, row, index) => {
        // Рассчитываем rowSpan
        // Ищем первую строку в группе (по groupId)
        const obj = {
          children: value,
          props: {},
        };
        // Найдём все строки с таким groupId
        const groupRows = pivotTableData.filter((r) => r.groupId === row.groupId);
        // Индекс первой строки этой группы
        const firstRowIndex = pivotTableData.findIndex(
          (r) => r.groupId === row.groupId
        );
        // Если текущая строка — первая в группе => rowSpan = 4, иначе 0
        if (index === firstRowIndex) {
          obj.props.rowSpan = 4;
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
          case 'uploaded':
            return 'Загружено';
          case 'rejected':
            return 'Отклонено';
          case 'total':
            return 'Всего';
          case 'percent':
            return '% загруженных';
          default:
            return '';
        }
      },
    },
    // Для каждой даты генерируем по столбцу
    ...dateKeys.map((dateKey) => ({
      title: dateKey,
      dataIndex: dateKey,
      key: dateKey,
      width: 120,
      align: 'center',
    })),
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16, minHeight: '100vh', width: '100%' }}>
        <Title level={2}>Статистика по загрузкам</Title>

        {/* Форма для выбора диапазона дат */}
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
            <Button type="primary" onClick={fetchStats}>
              Загрузить статистику
            </Button>
          </Col>
        </Row>

        {/* Чекбоксы (скрыть/показать на диаграмме) */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col>
            <Checkbox
              checked={showUploaded}
              onChange={(e) => setShowUploaded(e.target.checked)}
            >
              Показывать «Загружено»
            </Checkbox>
          </Col>
          <Col>
            <Checkbox
              checked={showRejected}
              onChange={(e) => setShowRejected(e.target.checked)}
            >
              Показывать «Отклонено»
            </Checkbox>
          </Col>
        </Row>

        {loading ? (
          <Spin />
        ) : (
          <>
            {/* Диаграмма (stacked bar) */}
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
                        text: 'Статистика по модераторам (стековая диаграмма)',
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

            {/* Pivot-таблица: (Модератор - rowSpan=4), (Тип), ...даты */}
            <Title level={4}>Детализированная сводка</Title>
            <Table
              columns={pivotColumns}
              dataSource={pivotTableData}
              pagination={false}
              bordered
              scroll={{ x: 'max-content' }}
            />
          </>
        )}

        <Modal
          title="Ошибка выбора дат"
          visible={errorModalVisible}
          onOk={() => setErrorModalVisible(false)}
          onCancel={() => setErrorModalVisible(false)}
        >
          <p>Можно выбрать период только до {MAX_DATE_RANGE} дней</p>
        </Modal>
      </Content>
    </Layout>
  );
};

export default ModerationStats;
