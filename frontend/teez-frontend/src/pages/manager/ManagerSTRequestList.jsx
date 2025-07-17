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
const { RangePicker } = DatePicker;
const { TextArea } = Input;

// Жёстко заданные статусы
const statusOptionsHardcoded = [
  { text: 'Другое', value: 9 },
  { text: 'Готово', value: 8 },
  { text: 'Проверка ретуши', value: 7 },
  { text: 'В ретуши', value: 6 },
  { text: 'Отснято', value: 5 },
  { text: 'Проверка фото', value: 4 },
  { text: 'На съемке', value: 3 },
  { text: 'Создана', value: 2 },
  { text: 'Черновик', value: 1 },
];

const ManagerSTRequestList = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const [token, setToken] = useState(null);

  // Проверка токена авторизации
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

  // Temp-стейты для ввода фильтров (значения, вводимые пользователем)
  const [tempRequestNumbers, setTempRequestNumbers] = useState('');
  const [tempBarcodes, setTempBarcodes] = useState('');
  const [tempName, setTempName] = useState('');
  const [tempCategoryIds, setTempCategoryIds] = useState('');
  const [tempCreationDateRange, setTempCreationDateRange] = useState([]);
  const [tempPhotoDateRange, setTempPhotoDateRange] = useState([]);
  const [tempStatusFilter, setTempStatusFilter] = useState([]);

  // Применённые фильтры – обновляются при нажатии на "Поиск"
  const [requestNumbers, setRequestNumbers] = useState('');
  const [barcodes, setBarcodes] = useState('');
  const [name, setName] = useState('');
  const [categoryIds, setCategoryIds] = useState('');
  const [creationDateRange, setCreationDateRange] = useState([]);
  const [photoDateRange, setPhotoDateRange] = useState([]);
  const [statusFilter, setStatusFilter] = useState([]);

  // Стейты для данных таблицы, пагинации, сортировки
  const [data, setData] = useState([]);
  // Дефолтное значение ordering соответствует бэкенду: сортировка по -RequestNumber
  const [ordering, setOrdering] = useState('-RequestNumber');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = 'Список заявок на съемку';
  }, []);

  // Функция для загрузки данных с сервера
  const fetchData = useCallback(
    async (
      page = 1,
      size = 50,
      order = ordering,
      reqNumbersArg = requestNumbers,
      barcodesArg = barcodes,
      nameArg = name,
      categoryIdsArg = categoryIds,
      creationRangeArg = creationDateRange,
      photoRangeArg = photoDateRange,
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

        // Функция обработки многострочного ввода: разделяем строки, убираем пробелы и пустые строки, затем объединяем через запятую
        const processMultiLine = (input) =>
          input.split('\n').map((item) => item.trim()).filter(Boolean).join(',');

        if (reqNumbersArg.trim()) {
          // ключ в запросе должен совпадать с тем, что ожидает бэкенд
          params['request_number'] = processMultiLine(reqNumbersArg);
        }
        if (barcodesArg.trim()) {
          params['barcode'] = processMultiLine(barcodesArg);
        }
        if (nameArg.trim()) {
          params['name'] = nameArg.trim();
        }
        if (categoryIdsArg.trim()) {
          params['category_ids'] = processMultiLine(categoryIdsArg);
        }
        if (creationRangeArg.length === 2) {
          params['creation_date_from'] = creationRangeArg[0].format('DD.MM.YYYY');
          params['creation_date_to'] = creationRangeArg[1].format('DD.MM.YYYY');
        }
        if (photoRangeArg.length === 2) {
          params['photo_date_from'] = photoRangeArg[0].format('DD.MM.YYYY');
          params['photo_date_to'] = photoRangeArg[1].format('DD.MM.YYYY');
        }
        if (statusesArg.length > 0) {
          params['status_ids'] = statusesArg.join(',');
        }

        const response = await axios.get(`${API_BASE_URL}/mn/strequest-list/`, {
          params,
          headers: { Authorization: `Bearer ${token}` },
        });

        const results = response.data.results || [];
        // Ключ для строки берем из request_number
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
    [token, ordering, requestNumbers, barcodes, name, categoryIds, creationDateRange, photoDateRange, statusFilter]
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
    setName(tempName);
    setCategoryIds(tempCategoryIds);
    setCreationDateRange(tempCreationDateRange);
    setPhotoDateRange(tempPhotoDateRange);
    setStatusFilter(tempStatusFilter);
    setCurrentPage(1);
    fetchData(
      1,
      pageSize,
      ordering,
      tempRequestNumbers,
      tempBarcodes,
      tempName,
      tempCategoryIds,
      tempCreationDateRange,
      tempPhotoDateRange,
      tempStatusFilter
    );
  };

  // Отображение сортировки: маппинг столбцов на реальные поля сортировки
  const orderingMapping = {
    request_number: 'RequestNumber',
    creation_date: 'creation_date',
    stockman: 'stockman_full_name',
    photographer: 'photographer_full_name',
    photo_date: 'photo_date',
    status: 'status__name',
    total_products: 'total_products',
    count_priority: 'count_priority',
    count_info: 'count_info',
  };

  // Обработка сортировки и обновление запроса
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

  // Обработчики для пагинации
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
      title: 'Номер заявки',
      dataIndex: 'request_number',
      key: 'request_number',
      sorter: true,
      render: (text) => (
        <a href={`/ManagerSTRequestDetail/${text}/`} target="_blank" rel="noopener noreferrer">
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
      title: 'Товаровед',
      dataIndex: 'stockman',
      key: 'stockman',
      sorter: true,
      render: (text) => text || '-',
    },
    {
      title: 'Фотограф',
      dataIndex: 'photographer',
      key: 'photographer',
      sorter: true,
      render: (text) => text || '-',
    },
    {
      title: 'Дата съемки',
      dataIndex: 'photo_date',
      key: 'photo_date',
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
            options={statusOptionsHardcoded.map((opt) => ({
                label: opt.text,
                value: opt.value,
            }))}
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
      dataIndex: 'total_products',
      key: 'total_products',
      sorter: true,
    },
    {
      title: 'приоритетных',
      dataIndex: 'count_priority',
      key: 'count_priority',
      sorter: true,
    },
    {
      title: 'отснято',
      dataIndex: 'count_photo',
      key: 'count_photo',
      sorter: true,
    },
    {
      title: 'проверено',
      dataIndex: 'count_checked',
      key: 'count_checked',
      sorter: true,
    },
    {
      title: 'ИНФО',
      dataIndex: 'count_info',
      key: 'count_info',
      sorter: true,
    },
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список заявок</h2>
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
            <div>Поиск по наименованию</div>
            <Input
              placeholder="Наименование"
              value={tempName}
              onChange={(e) => setTempName(e.target.value)}
              style={{ width: 200 }}
            />
          </Space>
          <Space direction="vertical">
            <div>Поиск по ID категорий</div>
            <TextArea
              placeholder="Каждый ID на новой строке"
              value={tempCategoryIds}
              onChange={(e) => setTempCategoryIds(e.target.value)}
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
            <div>Поиск по дате съемки</div>
            <RangePicker
              format="DD.MM.YYYY"
              value={tempPhotoDateRange}
              onChange={(values) => setTempPhotoDateRange(values || [])}
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

export default ManagerSTRequestList;
