import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Table, Input, Button, Space, DatePicker, Pagination, message, Modal, Spin } from 'antd';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

const StockmanOrders = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();

  // Остальные хуки (они вызываются всегда, независимо от проверки доступа)
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [orderNumbers, setOrderNumbers] = useState('');
  const [barcodesMulti, setBarcodesMulti] = useState('');
  const [creationDateRange, setCreationDateRange] = useState([]);
  const [assemblyDateRange, setAssemblyDateRange] = useState([]);
  const [acceptDateRange, setAcceptDateRange] = useState([]);
  const [statusOptions, setStatusOptions] = useState([]);
  const [statusFilter, setStatusFilter] = useState([]);
  const [ordering, setOrdering] = useState('-date');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  const [notFoundBarcodes, setNotFoundBarcodes] = useState([]);

  useEffect(() => {
    document.title = 'Список заказов';
  }, []);

  useEffect(() => {
    axios
      .get(`${API_BASE_URL}/st/order-statuses/`)
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

  /**
   * Функция загрузки данных.
   * barcodesArg — приоритетный штрихкод, если state barcodesMulti ещё не успел обновиться.
   */
  const fetchData = useCallback(
    async (page = 1, size = 50, order = ordering, statusesArg = null, barcodesArg = null) => {
      setLoading(true);
      try {
        const params = {
          page,
          page_size: size,
          ordering: order,
        };

        if (orderNumbers.trim()) {
          const lines = orderNumbers.split('\n').map((l) => l.trim()).filter(Boolean);
          if (lines.length > 0) {
            params.order_numbers = lines.join(',');
          }
        }

        if (barcodesArg) {
          params.barcodes = barcodesArg;
        } else if (barcodesMulti.trim()) {
          const lines = barcodesMulti.split('\n').map((l) => l.trim()).filter(Boolean);
          if (lines.length > 0) {
            params.barcodes = lines.join(',');
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

        if (acceptDateRange.length === 2) {
          const start = acceptDateRange[0].format('DD.MM.YYYY') + ' 00:00:00';
          const end = acceptDateRange[1].format('DD.MM.YYYY') + ' 23:59:59';
          params.accept_date_from = start;
          params.accept_date_to = end;
        }

        const actualStatuses = statusesArg !== null ? statusesArg : statusFilter;
        if (actualStatuses && actualStatuses.length > 0) {
          params.statuses = actualStatuses.join(',');
        }

        const response = await axios.get(`${API_BASE_URL}/st/orders`, { params });
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
      acceptDateRange,
      statusFilter
    ]
  );

  // Первичная загрузка
  useEffect(() => {
    fetchData(currentPage, pageSize, ordering);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const orderingMap = {
    order_number: 'OrderNumber',
    status_name: 'status__name',
    creation_date: 'date',
    creator: 'creator__first_name',
    assembly_user: 'assembly_user__first_name',
    assembly_date: 'assembly_date',
    accept_user: 'accept_user__first_name',
    accept_date: 'accept_date',
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

  // --- Логика "сканирования" (13 цифр + Enter + 1 сек) ---
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
          const newStatusFilter = [2, 1, 4, 6];
          setStatusFilter(newStatusFilter);
          fetchData(1, pageSize, ordering, newStatusFilter, inputBuffer);
        }
        inputBuffer = '';
      } else {
        inputBuffer = '';
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [fetchData, ordering, pageSize]);

  const columns = [
    {
      title: 'Номер заказа',
      dataIndex: 'order_number',
      key: 'order_number',
      sorter: true,
      render: (order_number) => (
        <a
          href={`/stockman-order-detail/${order_number}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {order_number}
        </a>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'status_name',
      key: 'status_name',
      sorter: true,
      filters: statusOptions,
      filterMultiple: true,
    },
    {
      title: 'Дата создания',
      dataIndex: 'creation_date',
      key: 'creation_date',
      sorter: true,
    },
    {
      title: 'Заказчик',
      dataIndex: 'creator',
      key: 'creator',
      sorter: true,
    },
    {
      title: 'Сотрудник сборки',
      dataIndex: 'assembly_user',
      key: 'assembly_user',
      sorter: true,
    },
    {
      title: 'Дата сборки',
      dataIndex: 'assembly_date',
      key: 'assembly_date',
      sorter: true,
    },
    {
      title: 'Сотрудник приемки',
      dataIndex: 'accept_user',
      key: 'accept_user',
      sorter: true,
    },
    {
      title: 'Дата начала приемки',
      dataIndex: 'accept_date',
      key: 'accept_date',
      sorter: true,
    },
    {
      title: 'Принято / Количество товаров',
      key: 'accepted_total',
      render: (text, record) =>
        `${record.accepted_products || 0} / ${record.total_products || 0}`,
    },
    {
      title: 'Приоритетные товары',
      dataIndex: 'priority_products',
      key: 'priority_products',
      sorter: true,
      render: (text, record) => record.priority_products || 0,
    },
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список заказов</h2>
        <Space style={{ marginBottom: 16, width: '100%' }} align="start">
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
            <div>
              <div>Поиск по дате приемки</div>
              <RangePicker
                format="DD.MM.YYYY"
                value={acceptDateRange}
                onChange={(values) => setAcceptDateRange(values || [])}
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
        />
      </Content>
    </Layout>
  );
};

export default StockmanOrders;
