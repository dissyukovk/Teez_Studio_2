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
  Modal,
  Checkbox,
} from 'antd';
import { FilterOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { TextArea } = Input;
const { RangePicker } = DatePicker;

// Жёстко заданные статусы для фильтра в колонке "Статус"
const statusOptionsHardcoded = [
  { label: 'Готово', value: '5' },
  { label: 'Правки', value: '4' },
  { label: 'Проверка', value: '3' },
  { label: 'В ретуши', value: '2' },
  { label: 'Создан', value: '1' },
];

const ManagerRetouchRequestList = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const [token, setToken] = useState(null);

  // Проверка наличия токена авторизации
  useEffect(() => {
    const storedToken = localStorage.getItem('accessToken');
    if (!storedToken) {
      Modal.error({
        title: 'Ошибка доступа',
        content: 'Токен авторизации не найден. Пожалуйста, выполните вход.',
        okText: 'Войти',
        onOk: () => navigate('/login'),
      });
    } else {
      setToken(storedToken);
    }
  }, [navigate]);

  // Temp-стейты для ввода фильтров (значения вводятся пользователем)
  const [tempRequestNumbers, setTempRequestNumbers] = useState('');
  const [tempBarcodes, setTempBarcodes] = useState('');
  const [tempCreationDateRange, setTempCreationDateRange] = useState([]);
  const [tempRetouchDateRange, setTempRetouchDateRange] = useState([]);
  const [tempStatusFilter, setTempStatusFilter] = useState([]);

  // Применённые фильтры – обновляются при нажатии на кнопку "Поиск"
  const [requestNumbers, setRequestNumbers] = useState('');
  const [barcodes, setBarcodes] = useState('');
  const [creationDateRange, setCreationDateRange] = useState([]);
  const [retouchDateRange, setRetouchDateRange] = useState([]);
  const [statusFilter, setStatusFilter] = useState([]);

  // Стейты для данных таблицы, пагинации и сортировки
  const [data, setData] = useState([]);
  const [ordering, setOrdering] = useState('-RequestNumber');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = 'Список заявок на ретушь';
  }, []);

  // Функция для загрузки данных с сервера
  const fetchData = useCallback(
    async (
      page = 1,
      size = 50,
      order = ordering,
      reqNumbersArg = requestNumbers,
      barcodesArg = barcodes,
      creationRangeArg = creationDateRange,
      retouchRangeArg = retouchDateRange,
      statusesArg = statusFilter
    ) => {
      if (!token) return;
      setLoading(true);
      try {
        const params = {
          page,
          page_size: size,
          ordering: order,
        };

        // Разбиваем многострочный ввод по строкам и объединяем через запятую
        const processMultiLine = (input) =>
          input.split('\n').map((item) => item.trim()).filter(Boolean).join(',');

        if (reqNumbersArg.trim()) {
          params['request_numbers'] = processMultiLine(reqNumbersArg);
        }
        if (barcodesArg.trim()) {
          params['barcode'] = processMultiLine(barcodesArg);
        }
        if (creationRangeArg.length === 2) {
          params['creation_date_from'] = creationRangeArg[0].format('DD.MM.YYYY');
          params['creation_date_to'] = creationRangeArg[1].format('DD.MM.YYYY');
        }
        if (retouchRangeArg.length === 2) {
          params['retouch_date_from'] = retouchRangeArg[0].format('DD.MM.YYYY');
          params['retouch_date_to'] = retouchRangeArg[1].format('DD.MM.YYYY');
        }
        if (statusesArg.length > 0) {
          params['statuses'] = statusesArg.join(',');
        }

        const response = await axios.get(`${API_BASE_URL}/mn/retouchrequestlist/`, {
          params,
          headers: { Authorization: `Bearer ${token}` },
        });

        const results = response.data.results || [];
        setData(results.map((item) => ({ key: item.request_number, ...item })));
        setTotalCount(response.data.count || 0);
        setCurrentPage(page);
        setPageSize(size);
      } catch (error) {
        console.error('Ошибка загрузки данных', error);
        message.error('Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    },
    [token, ordering, requestNumbers, barcodes, creationDateRange, retouchDateRange, statusFilter]
  );

  // Первоначальная загрузка при наличии токена
  useEffect(() => {
    if (token) {
      fetchData(currentPage, pageSize, ordering);
    }
  }, [token, currentPage, pageSize, ordering, fetchData]);

  // При нажатии на кнопку "Поиск" копируем temp-значения в фильтры и запускаем запрос
  const handleSearch = () => {
    setRequestNumbers(tempRequestNumbers);
    setBarcodes(tempBarcodes);
    setCreationDateRange(tempCreationDateRange);
    setRetouchDateRange(tempRetouchDateRange);
    setStatusFilter(tempStatusFilter);
    setCurrentPage(1);
    fetchData(
      1,
      pageSize,
      ordering,
      tempRequestNumbers,
      tempBarcodes,
      tempCreationDateRange,
      tempRetouchDateRange,
      tempStatusFilter
    );
  };

  // Маппинг колонок для сортировки – соответствие полей таблицы и полей бэкенда
  const orderingMapping = {
    request_number: 'RequestNumber',
    creation_date: 'creation_date',
    retouch_date: 'retouch_date',
    products_count: 'products_count',
    priority_products_count: 'priority_products_count',
  };

  // Обработка сортировки в таблице
  const handleTableChange = (pagination, filters, sorter) => {
    let newOrdering = ordering;
    if (sorter.field) {
      const field = orderingMapping[sorter.field] || sorter.field;
      newOrdering = sorter.order === 'descend' ? `-${field}` : field;
    }
    setOrdering(newOrdering);
    setCurrentPage(1);
    fetchData(1, pageSize, newOrdering);
  };

  // Обработчики пагинации
  const handlePageChange = (page, size) => {
    setCurrentPage(page);
    setPageSize(size);
    fetchData(page, size, ordering);
  };

  const handleShowSizeChange = (current, size) => {
    setCurrentPage(current);
    setPageSize(size);
    fetchData(current, size, ordering);
  };

  // Определение колонок таблицы
  const columns = [
    {
      title: 'Заявка',
      dataIndex: 'request_number',
      key: 'request_number',
      sorter: true,
      render: (text) => (
        <a href={`/ManagerRetouchRequestDetail/${text}/`} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      ),
    },
    {
      title: 'Дата создания',
      dataIndex: 'creation_date',
      key: 'creation_date',
      sorter: true,
    },
    {
      title: 'Ретушер',
      dataIndex: 'retoucher',
      key: 'retoucher',
      render: (text) => text || '-',
    },
    {
      title: 'Дата ретуши',
      dataIndex: 'retouch_date',
      key: 'retouch_date',
      sorter: true,
    },
    {
      title: 'Время ретуши',
      dataIndex: 'retouch_time',
      key: 'retouch_time',
      // Если хотите добавить сортировку по этому полю, 
      // нужно реализовать соответствующую логику на бэкенде.
      sorter: true,
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      sorter: true,
      filterDropdown: ({ confirm, clearFilters }) => (
        <div style={{ padding: 8 }}>
          <Checkbox.Group
            style={{ display: 'flex', flexDirection: 'column' }}
            options={statusOptionsHardcoded}
            value={tempStatusFilter}
            onChange={(vals) => setTempStatusFilter(vals)}
          />
          <div style={{ marginTop: 8 }}>
            <Button
              type="primary"
              onClick={() => {
                setStatusFilter(tempStatusFilter);
                confirm();
                handleSearch();
              }}
              size="small"
              style={{ marginRight: 8 }}
            >
              OK
            </Button>
            <Button
              onClick={() => {
                setTempStatusFilter([]);
                setStatusFilter([]);
                if (clearFilters) clearFilters();
                confirm();
                handleSearch();
              }}
              size="small"
            >
              Сброс
            </Button>
          </div>
        </div>
      ),
      filterIcon: (filtered) => (
        <FilterOutlined style={{ color: filtered ? '#1890ff' : undefined }} />
      ),
      render: (status) => status || '-',
    },
    {
      title: 'товаров',
      dataIndex: 'products_count',
      key: 'products_count',
      sorter: true,
    },
    {
      title: 'приоритетных',
      dataIndex: 'priority_products_count',
      key: 'priority_products_count',
      sorter: true,
    },
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список заявок на ретушь</h2>
        <Space style={{ marginBottom: 16, width: '100%' }} align="start">
          <Space direction="vertical">
            <div>Поиск по номерам заявок</div>
            <TextArea
              placeholder="Каждый номер на новой строке"
              value={tempRequestNumbers}
              onChange={(e) => setTempRequestNumbers(e.target.value)}
              rows={4}
              style={{ width: 200 }}
            />
          </Space>
          <Space direction="vertical">
            <div>Поиск по штрихкодам</div>
            <TextArea
              placeholder="Каждый штрихкод на новой строке"
              value={tempBarcodes}
              onChange={(e) => setTempBarcodes(e.target.value)}
              rows={4}
              style={{ width: 200 }}
            />
          </Space>
          <Space direction="vertical">
            <div>Поиск по дате создания</div>
            <RangePicker
              format="DD.MM.YYYY"
              value={tempCreationDateRange}
              onChange={(values) => setTempCreationDateRange(values || [])}
            />
          </Space>
          <Space direction="vertical">
            <div>Поиск по дате ретуши</div>
            <RangePicker
              format="DD.MM.YYYY"
              value={tempRetouchDateRange}
              onChange={(values) => setTempRetouchDateRange(values || [])}
            />
          </Space>
          <Space direction="vertical" style={{ marginTop: 'auto' }}>
            <Button type="primary" onClick={handleSearch}>
              Поиск
            </Button>
          </Space>
        </Space>
        {/* Пагинатор над таблицей */}
        <Pagination
          current={currentPage}
          pageSize={pageSize}
          total={totalCount}
          onChange={handlePageChange}
          showSizeChanger
          onShowSizeChange={handleShowSizeChange}
          pageSizeOptions={['10', '20', '50', '100']}
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

export default ManagerRetouchRequestList;
