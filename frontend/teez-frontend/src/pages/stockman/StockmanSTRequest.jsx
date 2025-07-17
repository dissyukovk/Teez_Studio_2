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
  Checkbox
} from 'antd';
import { FilterOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

const StockmanSTRequest = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();

  // 1. Токен авторизации
  const [token, setToken] = useState(null);
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

  // 2. Основные стейты для фильтров (отправляются в запрос)
  const [requestNumbers, setRequestNumbers] = useState('');
  const [barcodesMulti, setBarcodesMulti] = useState('');
  const [creationDateRange, setCreationDateRange] = useState([]);
  const [photoDateRange, setPhotoDateRange] = useState([]);
  const [statusFilter, setStatusFilter] = useState([]); // выбранные статусы

  // 3. Temp-стейты для ввода пользователем
  const [tempRequestNumbers, setTempRequestNumbers] = useState('');
  const [tempBarcodesMulti, setTempBarcodesMulti] = useState('');
  const [tempCreationDateRange, setTempCreationDateRange] = useState([]);
  const [tempPhotoDateRange, setTempPhotoDateRange] = useState([]);
  const [tempStatusFilter, setTempStatusFilter] = useState([]);

  // 4. Другие стейты (данные, пагинация, сортировка)
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [statusOptions, setStatusOptions] = useState([]);
  const [ordering, setOrdering] = useState('-RequestNumber');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    document.title = 'Список заявок';
  }, []);

  // 5. Загрузка списка статусов
  useEffect(() => {
    if (token) {
      axios
        .get(`${API_BASE_URL}/st/strequest-statuses/`, {
          headers: { Authorization: `Bearer ${token}` },
        })
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
    }
  }, [token]);

  // 6. Функция загрузки данных (принимает опциональные параметры)
  const fetchData = useCallback(
    async (
      page = 1,
      size = 50,
      order = ordering,
      statusesArg = undefined,
      barcodesArg = undefined,
      reqNumbersArg = undefined,
      creationRangeArg = undefined,
      photoRangeArg = undefined
    ) => {
      if (!token) return;
      setLoading(true);
      try {
        const effectiveRequestNumbers = reqNumbersArg !== undefined ? reqNumbersArg : requestNumbers;
        const effectiveBarcodes = barcodesArg !== undefined ? barcodesArg : barcodesMulti;
        const effectiveCreationDateRange = creationRangeArg !== undefined ? creationRangeArg : creationDateRange;
        const effectivePhotoDateRange = photoRangeArg !== undefined ? photoRangeArg : photoDateRange;
        const effectiveStatuses = statusesArg !== undefined ? statusesArg : statusFilter;

        const params = {
          page,
          page_size: size,
          ordering: order,
        };

        if (effectiveRequestNumbers.trim()) {
          const lines = effectiveRequestNumbers.split('\n').map((l) => l.trim()).filter(Boolean);
          if (lines.length > 0) {
            params.request_numbers = lines.join(',');
          }
        }

        if (effectiveBarcodes.trim()) {
          const lines = effectiveBarcodes.split('\n').map((l) => l.trim()).filter(Boolean);
          if (lines.length > 0) {
            params.barcodes = lines.join(',');
          }
        }

        if (effectiveCreationDateRange.length === 2) {
          params.creation_date_from = effectiveCreationDateRange[0].format('DD.MM.YYYY');
          params.creation_date_to = effectiveCreationDateRange[1].format('DD.MM.YYYY');
        }

        if (effectivePhotoDateRange.length === 2) {
          params.photo_date_from = effectivePhotoDateRange[0].format('DD.MM.YYYY');
          params.photo_date_to = effectivePhotoDateRange[1].format('DD.MM.YYYY');
        }

        if (effectiveStatuses && effectiveStatuses.length > 0) {
          params.statuses = effectiveStatuses.join(',');
        }

        const response = await axios.get(`${API_BASE_URL}/st/strequest-search/`, {
          params,
          headers: { Authorization: `Bearer ${token}` },
        });
        const results = response.data.results || [];
        setData(results.map((item, index) => ({ key: index, ...item })));
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
    [token, ordering, requestNumbers, barcodesMulti, creationDateRange, photoDateRange, statusFilter]
  );

  // 7. Первичная загрузка (один раз при наличии токена)
  const [isInitialLoadDone, setIsInitialLoadDone] = useState(false);
  useEffect(() => {
    if (token && !isInitialLoadDone) {
      fetchData(currentPage, pageSize, ordering, statusFilter);
      setIsInitialLoadDone(true);
    }
  }, [token, isInitialLoadDone, currentPage, pageSize, ordering, statusFilter, fetchData]);

  // 8. Обновление стейтов сортировки/пагинации (без вызова fetchData)
  const orderingMap = {
    RequestNumber: 'RequestNumber',
    creation_date: 'creation_date',
    photo_date: 'photo_date',
    products_count: 'products_count',
    stockman: 'stockman__first_name',
    photographer: 'photographer__first_name',
  };

  const handleTableChange = (pagination, filters, sorter) => {
    let newOrdering = ordering;
    if (sorter.field) {
      const drfField = orderingMap[sorter.field] || sorter.field;
      newOrdering = sorter.order === 'descend' ? `-${drfField}` : drfField;
    }
    setOrdering(newOrdering);
    setCurrentPage(1);
    fetchData(1, pageSize, newOrdering);
  };

  const handlePageChange = (page, size) => {
    setCurrentPage(page);
    setPageSize(size);
  };

  const handleShowSizeChange = (current, size) => {
    setCurrentPage(current);
    setPageSize(size);
  };

  // 9. Кнопка "Поиск" – копирование temp-значений и запуск запроса
  const handleSearch = () => {
    setRequestNumbers(tempRequestNumbers);
    setBarcodesMulti(tempBarcodesMulti);
    setCreationDateRange(tempCreationDateRange);
    setPhotoDateRange(tempPhotoDateRange);
    setStatusFilter(tempStatusFilter);
    setCurrentPage(1);
    fetchData(
      1,
      pageSize,
      ordering,
      tempStatusFilter,
      tempBarcodesMulti,
      tempRequestNumbers,
      tempCreationDateRange,
      tempPhotoDateRange
    );
  };

  // 10. Обработчик создания заявки
  const handleCreateRequest = async () => {
    if (!token) return;
    try {
      const response = await axios.post(
        `${API_BASE_URL}/st/strequest-create/`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const { RequestNumber } = response.data;
      if (RequestNumber) {
        message.success(`Заявка №${RequestNumber} создана`);
        window.open(`/stockman-strequest-detail/${RequestNumber}`, '_blank');
      }
    } catch (error) {
      const errMsg =
        error.response && error.response.data && error.response.data.error
          ? error.response.data.error
          : 'Ошибка создания заявки';
      message.error(errMsg);
    }
  };

  // 11. Сканирование штрихкодов (срабатывает сразу)
  useEffect(() => {
    let inputBuffer = '';
    let lastKeyTime = 0;
    const handleKeyDown = (e) => {
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      if (activeTag === 'input' || activeTag === 'textarea') return;
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

  // 12. Кастомный фильтр статусов (через dropdown)
  const columns = [
    {
      title: 'Номер заявки',
      dataIndex: 'RequestNumber',
      key: 'RequestNumber',
      sorter: true,
      render: (RequestNumber) => (
        <a
          href={`/stockman-strequest-detail/${RequestNumber}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {RequestNumber}
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
      render: (stockman) => stockman || '-',
    },
    {
      title: 'Фотограф',
      dataIndex: 'photographer',
      key: 'photographer',
      sorter: true,
      render: (photographer) => photographer || '-',
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
            options={statusOptions.map((opt) => ({
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
              Reset
            </Button>
          </div>
        </div>
      ),
      filterDropdownProps: {
        onOpenChange: (open) => {
          if (open) {
            setTempStatusFilter(statusFilter);
          }
        },
      },
      filterIcon: (filtered) => (
        <FilterOutlined style={{ color: filtered ? '#1890ff' : undefined }} />
      ),
      render: (status) => (status ? status.name : '-'),
    },
    {
      title: 'Количество товаров',
      dataIndex: 'products_count',
      key: 'products_count',
      sorter: true,
    },
  ];

  // 13. РЕНДЕР
  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список заявок</h2>
        <Space style={{ marginBottom: 16, width: '100%' }} align="start">
          {/* Поля ввода фильтров (temp) */}
          <Space direction="vertical">
            <div>Поиск по номерам заявок</div>
            <TextArea
              placeholder="Номера заявок (каждый в новой строке)"
              value={tempRequestNumbers}
              onChange={(e) => setTempRequestNumbers(e.target.value)}
              style={{ width: 200 }}
              rows={6}
            />
          </Space>
          <Space direction="vertical">
            <div>Поиск по штрихкодам</div>
            <TextArea
              placeholder="Штрихкоды (каждый в новой строке)"
              value={tempBarcodesMulti}
              onChange={(e) => setTempBarcodesMulti(e.target.value)}
              style={{ width: 200 }}
              rows={6}
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
        {/* Кнопка "Создать заявку" */}
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={handleCreateRequest}>
            Создать заявку
          </Button>
        </Space>
        <Pagination
          current={currentPage}
          pageSize={pageSize}
          total={totalCount}
          onChange={handlePageChange}
          showSizeChanger
          pageSizeOptions={['10', '20', '50', '100']}
          onShowSizeChange={handleShowSizeChange}
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

export default StockmanSTRequest;
