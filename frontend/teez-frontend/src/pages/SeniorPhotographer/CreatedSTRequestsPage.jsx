import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Table,
  Input,
  Button,
  Space,
  message,
  Modal,
  Select,
  Tooltip,
  Typography,
  Tabs
} from 'antd';
import {
  FilterOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';
import { requestTypeOptions } from '../../utils/requestTypeOptions';

const { Content } = Layout;
const { Option } = Select;
const { TabPane } = Tabs;

const CreatedSTRequestsPage = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const [token] = useState(localStorage.getItem('accessToken'));

  // --- Filters state ---
  const [requestNumbers, setRequestNumbers] = useState('');
  const [barcodes, setBarcodes] = useState('');
  const [tempRequestNumbers, setTempRequestNumbers] = useState('');
  const [tempBarcodes, setTempBarcodes] = useState('');

  // --- Data and controls ---
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [photographers, setPhotographers] = useState([]);
  const [assistants, setAssistants] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  const [ordering, setOrdering] = useState(null);
  const [activeType, setActiveType] = useState('1');

  // Проверка токена и заголовок
  useEffect(() => {
    document.title = 'Созданные заявки на съемку';
    if (!token) {
      Modal.error({
        title: 'Ошибка доступа',
        content: 'Токен авторизации не найден. Пожалуйста, выполните вход.',
        okText: 'Войти',
        onOk: () => navigate('/login'),
      });
    }
  }, [navigate, token]);

  // Загрузка справочников
  const fetchPhotographers = useCallback(async () => {
    if (!token) return;
    try {
      const res = await axios.get(`${API_BASE_URL}/ph/photographers/working/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPhotographers(res.data || []);
    } catch {
      message.error('Не удалось загрузить список фотографов');
    }
  }, [token]);

  const fetchAssistants = useCallback(async () => {
    if (!token) return;
    try {
      const res = await axios.get(`${API_BASE_URL}/ph/assistants/all/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAssistants(res.data || []);
    } catch {
      message.error('Не удалось загрузить список ассистентов');
    }
  }, [token]);

  // Универсальная загрузка таблицы
  const fetchData = useCallback(
    async (
      page = currentPage,
      size = pageSize,
      order = ordering,
      reqNums = requestNumbers,
      barcodesList = barcodes,
      type = activeType
    ) => {
      if (!token) return;
      setLoading(true);
      try {
        const params = { page, page_size: size };
        if (order) params.ordering = order;
        if (reqNums) params.request_numbers = reqNums.split('\n').join(',');
        if (barcodesList) params.barcodes = barcodesList.split('\n').join(',');
        if (type) params.strequest_type = type;

        const res = await axios.get(`${API_BASE_URL}/ph/strequests2/`, {
          params,
          headers: { Authorization: `Bearer ${token}` }
        });
        setData(res.data.results.map(item => ({ ...item, key: item.id })));
        setTotalCount(res.data.count);
      } catch {
        message.error('Ошибка загрузки созданных заявок');
      } finally {
        setLoading(false);
      }
    },
    [token, currentPage, pageSize, ordering, requestNumbers, barcodes, activeType]
  );

  // Эффект для fetchData при изменении параметров
  useEffect(() => {
    if (token) fetchData();
  }, [token, fetchData]);

  // Эффект для загрузки справочников один раз
  useEffect(() => {
    fetchPhotographers();
    fetchAssistants();
  }, [fetchPhotographers, fetchAssistants]);

  // Обработчики
  const handleTabChange = key => {
    setActiveType(key);
    setCurrentPage(1);
  };

  const handleSearch = () => {
    setRequestNumbers(tempRequestNumbers);
    setBarcodes(tempBarcodes);
    setCurrentPage(1);
  };

  const handleResetFilters = () => {
    setTempRequestNumbers('');
    setTempBarcodes('');
    setRequestNumbers('');
    setBarcodes('');
    setCurrentPage(1);
  };

  const handleTableChange = (pagination, filters, sorter) => {
    if (sorter.field) {
      const ord = sorter.order === 'ascend' ? sorter.field : `-${sorter.field}`;
      setOrdering(ord);
    } else {
      setOrdering(null);
    }
    setCurrentPage(1);
  };

  const onPageChange = (page, newSize) => {
    setCurrentPage(page);
    setPageSize(newSize);
  };

  // Операции назначения/снятия фотографа и ассистента
  const refreshTable = () => fetchData();

  const handlePhotographerChange = async (num, id) => {
    if (!token) return;
    try {
      await axios.post(
        `${API_BASE_URL}/ph/st-requests/assign-photographer/`,
        { request_number: num, user_id: id },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Фотограф назначен на заявку ${num}`);
      refreshTable();
    } catch {
      message.error('Ошибка назначения фотографа');
    }
  };

  const handleRemovePhotographer = async num => {
    if (!token) return;
    try {
      await axios.post(
        `${API_BASE_URL}/ph/st-requests/remove-photographer/`,
        { request_number: num },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Фотограф снят с заявки ${num}`);
      refreshTable();
    } catch {
      message.error('Ошибка снятия фотографа');
    }
  };

  const handleAssistantChange = async (num, id) => {
    if (!token) return;
    try {
      await axios.post(
        `${API_BASE_URL}/ph/st-requests/assign-assistant/`,
        { request_number: num, user_id: id },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Ассистент назначен на заявку ${num}`);
      refreshTable();
    } catch {
      message.error('Ошибка назначения ассистента');
    }
  };

  const handleRemoveAssistant = async num => {
    if (!token) return;
    try {
      await axios.post(
        `${API_BASE_URL}/ph/st-requests/remove-assistant/`,
        { request_number: num },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Ассистент снят с заявки ${num}`);
      refreshTable();
    } catch {
      message.error('Ошибка снятия ассистента');
    }
  };

  const renderBoolean = value => (
    <Tooltip title={value ? 'Да' : 'Нет'}>
      {value ? <CheckCircleOutlined style={{ color: 'green' }} /> : <CloseCircleOutlined style={{ color: 'red' }} />}
    </Tooltip>
  );

  const columns = [
    {
      title: 'Номер заявки',
      dataIndex: 'RequestNumber',
      key: 'RequestNumber',
      sorter: (a, b) => a.RequestNumber.localeCompare(b.RequestNumber),
      render: (text, rec) => (
        <a href={`/sph/st-request-detail/${rec.RequestNumber}`} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      )
    },
    {
      title: 'Товаров',
      dataIndex: 'total_products',
      key: 'total_products',
      sorter: (a, b) => a.total_products - b.total_products
    },
    {
      title: 'Приоритет',
      dataIndex: 'priority',
      key: 'priority',
      align: 'center',
      render: renderBoolean
    },
    {
      title: 'Есть инфо',
      dataIndex: 'info',
      key: 'info',
      align: 'center',
      render: renderBoolean
    },
    {
      title: 'Фотограф',
      dataIndex: 'photographer',
      key: 'photographer',
      width: 250,
      render: (photographer, rec) => (
        <Space>
          <Select
            style={{ width: 200 }}
            placeholder="Выберите фотографа"
            value={photographer?.id}
            onChange={id => handlePhotographerChange(rec.RequestNumber, id)}
            allowClear showSearch optionFilterProp="children"
          >
            {photographers.map(p => <Option key={p.id} value={p.id}>{p.full_name}</Option>)}
          </Select>
          {photographer && (
            <Tooltip title="Сбросить фотографа">
              <Button icon={<DeleteOutlined />} onClick={() => handleRemovePhotographer(rec.RequestNumber)} danger size="small" />
            </Tooltip>
          )}
        </Space>
      )
    },
    {
      title: 'Ассистент',
      dataIndex: 'assistant',
      key: 'assistant',
      width: 250,
      render: (assistant, rec) => (
        <Space>
          <Select
            style={{ width: 200 }}
            placeholder="Выберите ассистента"
            value={assistant?.id}
            onChange={id => handleAssistantChange(rec.RequestNumber, id)}
            allowClear showSearch optionFilterProp="children"
          >
            {assistants.map(a => <Option key={a.id} value={a.id}>{a.full_name}</Option>)}
          </Select>
          {assistant && (
            <Tooltip title="Сбросить ассистента">
              <Button icon={<DeleteOutlined />} onClick={() => handleRemoveAssistant(rec.RequestNumber)} danger size="small" />
            </Tooltip>
          )}
        </Space>
      )
    }
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content style={{ padding: 24, background: darkMode ? '#001529' : '#fff' }}>
          <Typography.Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>
            Созданные заявки (Статус 2)
          </Typography.Title>

          <Tabs activeKey={activeType} onChange={handleTabChange} style={{ marginBottom: 16 }}>
            <TabPane tab="Обычные товары" key="1" />
            <TabPane tab="Одежда" key="2" />
            <TabPane tab="КГТ" key="3" />
          </Tabs>

          <Space wrap style={{ marginBottom: 16 }}>
            <Input.TextArea
              placeholder="Номера заявок (по одному на строку)"
              value={tempRequestNumbers}
              onChange={e => setTempRequestNumbers(e.target.value)}
              rows={2} style={{ width: 200 }}
            />
            <Input.TextArea
              placeholder="Штрихкоды (по одному на строку)"
              value={tempBarcodes}
              onChange={e => setTempBarcodes(e.target.value)}
              rows={2} style={{ width: 200 }}
            />
            <Button type="primary" onClick={handleSearch} icon={<FilterOutlined />}>Поиск</Button>
            <Button onClick={handleResetFilters}>Сбросить</Button>
          </Space>

          <Table
            columns={columns}
            dataSource={data}
            loading={loading}
            onChange={handleTableChange}
            pagination={{
              current: currentPage,
              pageSize,
              total: totalCount,
              onChange: onPageChange,
              showSizeChanger: true,
              pageSizeOptions: ['10','20','50','100'],
              showTotal: total => `Всего: ${total}`
            }}
            scroll={{ x: 1200 }}
            bordered
          />
        </Content>
      </Layout>
    </Layout>
  );
};

export default CreatedSTRequestsPage;
