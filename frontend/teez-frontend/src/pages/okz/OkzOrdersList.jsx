import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Table,
  Input,
  Button,
  Space,
  DatePicker,
  Pagination,
  message,
  Grid
} from 'antd';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { RangePicker } = DatePicker;
const { TextArea } = Input;
const { useBreakpoint } = Grid;

const OkzOrders = ({ darkMode, setDarkMode }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [orderNumbers, setOrderNumbers] = useState('');
  const [barcodesMulti, setBarcodesMulti] = useState('');
  const [creationDateRange, setCreationDateRange] = useState([]);
  const [assemblyDateRange, setAssemblyDateRange] = useState([]);
  const [statusOptions, setStatusOptions] = useState([]);
  const [statusFilter, setStatusFilter] = useState([2, 3]);
  const [ordering, setOrdering] = useState('-priority_products,date');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  const [notFoundBarcodes, setNotFoundBarcodes] = useState([]);
  // Состояние для переключения фильтра "Показать только созданные"
  const [isShowOnlyCreated, setIsShowOnlyCreated] = useState(false);

  useEffect(() => {
    document.title = 'Список заказов ФС';
  }, []);

  useEffect(() => {
    axios
      .get(`${API_BASE_URL}/okz/order-statuses/`)
      .then((response) => {
        const options = response.data.map((item) => ({
          text: item.name,
          value: item.id,
        }));
        setStatusOptions(options);
      })
      .catch((error) => {
        console.error('Ошибка загрузки статусов', error);
      });
  }, []);

  const fetchData = useCallback(
    async (
      page = 1,
      size = 50,
      order = ordering,
      statusesArg = null,
      barcodesArg = null
    ) => {
      setLoading(true);
      try {
        const params = {
          page,
          page_size: size,
          ordering: order,
        };

        if (orderNumbers.trim()) {
          const lines = orderNumbers
            .split('\n')
            .map((l) => l.trim())
            .filter(Boolean);
          if (lines.length > 0) {
            params.order_numbers = lines.join(',');
          }
        }

        if (barcodesArg) {
          params.barcode = barcodesArg;
        } else if (barcodesMulti.trim()) {
          const lines = barcodesMulti
            .split('\n')
            .map((l) => l.trim())
            .filter(Boolean);
          if (lines.length > 0) {
            params.barcode = lines.join(',');
          }
        }

        if (creationDateRange.length === 2) {
          const start = creationDateRange[0].format('DD.MM.YYYY') + ' 00:00:00';
          const end = creationDateRange[1].format('DD.MM.YYYY') + ' 23:59:59';
          params.date_from = start;
          params.date_to = end;
        }

        if (assemblyDateRange.length === 2) {
          const start = assemblyDateRange[0].format('DD.MM.YYYY') + ' 00:00:00';
          const end = assemblyDateRange[1].format('DD.MM.YYYY') + ' 23:59:59';
          params.assembly_date_from = start;
          params.assembly_date_to = end;
        }

        const actualStatuses = statusesArg !== null ? statusesArg : statusFilter;
        if (actualStatuses && actualStatuses.length > 0) {
          params.statuses = actualStatuses.join(',');
        }

        const response = await axios.get(`${API_BASE_URL}/okz/orders`, {
          params,
        });
        const results = response.data.results || [];
        setData(results.map((item, index) => ({ key: index, ...item })));
        setTotalCount(response.data.count || 0);
        setCurrentPage(page);
        setPageSize(size);

        if (response.data.not_found_barcodes) {
          setNotFoundBarcodes(response.data.not_found_barcodes);
        } else {
          setNotFoundBarcodes([]);
        }
      } catch (error) {
        console.error('Ошибка загрузки данных', error);
        message.error('Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    },
    [
      ordering,
      orderNumbers,
      barcodesMulti,
      creationDateRange,
      assemblyDateRange,
      statusFilter
    ]
  );

  // Первоначальная загрузка данных
  useEffect(() => {
    fetchData(currentPage, pageSize, ordering);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Интервал для автоматического обновления данных каждые 10 секунд
  useEffect(() => {
    const intervalId = setInterval(() => {
      fetchData(currentPage, pageSize, ordering, statusFilter);
    }, 10000);
    return () => clearInterval(intervalId);
  }, [fetchData, currentPage, pageSize, ordering, statusFilter]);

  const orderingMap = {
    order_number: 'OrderNumber',
    status_name: 'status__name',
    creation_date: 'date',
    creator: 'creator__first_name',
    assembly_date: 'assembly_date',
    priority_products: 'priority_products',
  };

  const handleTableChange = (pagination, filters, sorter) => {
    let newOrdering = ordering;
    if (sorter.field) {
      const drfField = orderingMap[sorter.field] || sorter.field;
      newOrdering = sorter.order === 'descend' ? `-${drfField}` : drfField;
      setOrdering(newOrdering);
    }
    const newStatusFilter = filters.status_name || [];
    setStatusFilter(newStatusFilter);
    const newPage = 1;
    setCurrentPage(newPage);
    fetchData(newPage, pageSize, newOrdering, newStatusFilter);
  };

  const handlePageChange = (page, size) => {
    setCurrentPage(page);
    setPageSize(size);
    fetchData(page, size, ordering, statusFilter);
  };

  const handleSearch = () => {
    setCurrentPage(1);
    fetchData(1, pageSize, ordering, statusFilter);
  };

  // Переключаемая кнопка "Показать только созданные" / "Показать все"
  const handleToggleShowOnlyCreated = () => {
    let newStatusFilter;
    if (isShowOnlyCreated) {
      // Если сейчас активен фильтр "только созданные", возвращаем фильтр по умолчанию
      newStatusFilter = [2, 3];
    } else {
      // Иначе устанавливаем фильтр только по статусу 2
      newStatusFilter = [2];
    }
    setIsShowOnlyCreated(!isShowOnlyCreated);
    setStatusFilter(newStatusFilter);
    setCurrentPage(1);
    fetchData(1, pageSize, ordering, newStatusFilter);
  };

  // Логика "сканирования" штрихкодов. Теперь используется текущий statusFilter
  useEffect(() => {
    let inputBuffer = '';
    let lastKeyTime = 0;

    const handleKeyDown = (e) => {
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      if (activeTag === 'input' || activeTag === 'textarea') {
        return;
      }

      const now = Date.now();
      if (now - lastKeyTime > 1000) {
        inputBuffer = '';
      }
      lastKeyTime = now;

      if (/^[0-9]$/.test(e.key)) {
        inputBuffer += e.key;
      } else if (e.key === 'Enter') {
        if (inputBuffer.length === 13) {
          setBarcodesMulti(inputBuffer);
          // Используем текущий statusFilter вместо явного задания [2, 3]
          fetchData(1, pageSize, ordering, statusFilter, inputBuffer);
        }
        inputBuffer = '';
      } else {
        inputBuffer = '';
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [fetchData, ordering, pageSize, statusFilter]);

  const columns = [
    {
      title: 'Номер заказа',
      dataIndex: 'order_number',
      key: 'order_number',
      sorter: true,
      render: (order_number) => (
        <a
          href={`/okz_orders/${order_number}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {order_number}
        </a>
      ),
      responsive: ['xs', 'sm', 'md', 'lg', 'xl'],
    },
    {
      title: 'Статус',
      dataIndex: 'status_name',
      key: 'status_name',
      sorter: true,
      filters: statusOptions,
      filterMultiple: true,
      responsive: ['xs', 'sm', 'md', 'lg', 'xl'],
    },
    {
      title: 'Дата создания',
      dataIndex: 'creation_date',
      key: 'creation_date',
      sorter: true,
      responsive: ['md'],
    },
    {
      title: 'Заказчик',
      dataIndex: 'creator',
      key: 'creator',
      sorter: true,
      responsive: ['md'],
    },
    {
      title: 'Дата сборки',
      dataIndex: 'assembly_date',
      key: 'assembly_date',
      sorter: true,
      responsive: ['xs', 'sm', 'md', 'lg', 'xl'],
    },
    {
      title: 'Приоритетные товары',
      dataIndex: 'priority_products',
      key: 'priority_products',
      sorter: true,
      render: (text, record) => record.priority_products || 0,
      responsive: ['xs', 'sm', 'md', 'lg', 'xl'],
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh', background: darkMode ? '#1f1f1f' : '#fff' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список заказов ФС</h2>
        <div>
          <p><h3>Инструкция:</h3></p>
          <p><h3>⚠️Пожалуйста, не меняйте порядок сортировки. По стандарту заказы сортируются так, чтобы наиболее приоритетные были сверху</h3></p>
          <p><h3>Статус "Сбор" значит, что заказ был распечатан или скачан в Excel</h3></p>
          <p><h3>Вы можете нажать на кнопку, чтобы отобразить только заказы в статусе "Создан"</h3></p>
        </div>
        {/* Кнопка для переключения фильтра */}
        <div style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={handleToggleShowOnlyCreated}>
            {isShowOnlyCreated ? 'Показать все' : 'Показать только созданные'}
          </Button>
          <br />
        </div>
        <br />
        {/* Блоки фильтров делаем "обёрнутыми", чтобы на мобильном они переносились. */}
        <Space
          style={{ marginBottom: 16, width: '100%' }}
          align="start"
          wrap
          size={[16, 16]}
        >
          <Space direction="vertical">
            <div>Поиск по номерам заказа</div>
            <TextArea
              placeholder="Номера заказа (каждый в новой строке)"
              value={orderNumbers}
              onChange={(e) => setOrderNumbers(e.target.value)}
              style={{ width: 200 }}
              rows={6}
            />
          </Space>
          <Space direction="vertical">
            <div>Поиск по штрихкодам</div>
            <TextArea
              placeholder="Штрихкоды (каждый в новой строке)"
              value={barcodesMulti}
              onChange={(e) => setBarcodesMulti(e.target.value)}
              style={{ width: 200 }}
              rows={6}
            />
          </Space>
          <Space direction="vertical">
            <div>
              <div>Поиск по дате создания</div>
              <RangePicker
                format="DD.MM.YYYY"
                value={creationDateRange}
                onChange={(values) => setCreationDateRange(values || [])}
              />
            </div>
            <div>
              <div>Поиск по дате сборки</div>
              <RangePicker
                format="DD.MM.YYYY"
                value={assemblyDateRange}
                onChange={(values) => setAssemblyDateRange(values || [])}
              />
            </div>
          </Space>
          <Space direction="vertical" style={{ marginTop: 'auto' }}>
            <Button type="primary" onClick={handleSearch}>
              Поиск
            </Button>
          </Space>
          <Space direction="vertical" style={{ marginLeft: 'auto' }}>
            <div>Не найдены штрихкоды</div>
            <TextArea
              placeholder="Не найдены штрихкоды"
              value={notFoundBarcodes.join('\n')}
              style={{ width: 200 }}
              rows={6}
              readOnly
            />
          </Space>
        </Space>
        <Pagination
          current={currentPage}
          pageSize={pageSize}
          total={totalCount}
          onChange={handlePageChange}
          showSizeChanger
          onShowSizeChange={handlePageChange}
          showTotal={(total) => `Всего ${total} записей`}
          style={{ marginBottom: 16 }}
        />
        <Table
          columns={columns}
          dataSource={data}
          loading={loading}
          onChange={handleTableChange}
          pagination={false}
          scroll={{ x: 'max-content' }}
        />
      </Content>
    </Layout>
  );
};

export default OkzOrders;
