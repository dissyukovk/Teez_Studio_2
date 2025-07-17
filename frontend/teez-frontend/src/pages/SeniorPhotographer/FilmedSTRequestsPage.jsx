import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Table,
  Input,
  Button,
  Space,
  Pagination,
  message,
  Modal,
  Select,
  Tooltip,
  Typography
} from 'antd';
import { FilterOutlined, CheckCircleOutlined, CloseCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../../components/Layout/Sidebar'; // Adjust path
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config'; // Adjust path
import dayjs from 'dayjs';

const { Content } = Layout;
const { Option } = Select;

const FilmedSTRequestsPage = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const [token, setToken] = useState(localStorage.getItem('accessToken'));

  // Filters
  const [requestNumbers, setRequestNumbers] = useState('');
  const [barcodes, setBarcodes] = useState('');
  const [tempRequestNumbers, setTempRequestNumbers] = useState('');
  const [tempBarcodes, setTempBarcodes] = useState('');

  // Data
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [assistants, setAssistants] = useState([]);

  // Pagination & Sorting
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  const [ordering, setOrdering] = useState(null);

  useEffect(() => {
    document.title = 'Отснятые заявки';
    if (!token) {
      Modal.error({
        title: 'Ошибка доступа',
        content: 'Токен авторизации не найден.',
        okText: 'Войти',
        onOk: () => navigate('/login'),
      });
    }
  }, [navigate, token]);

  const fetchAssistants = useCallback(async () => {
     if (!token) return;
    try {
      const response = await axios.get(`${API_BASE_URL}/ph/assistants/all/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setAssistants(response.data || []);
    } catch (error) {
      console.error('Ошибка загрузки ассистентов:', error);
    }
  }, [token]);

  const fetchData = useCallback(async (page = currentPage, size = pageSize, currentOrder = ordering, currentReqNums = requestNumbers, currentBarcodes = barcodes) => {
    if (!token) return;
    setLoading(true);
    try {
      const params = { page, page_size: size };
      if (currentOrder) params.ordering = currentOrder;
      if (currentReqNums.trim()) params.request_numbers = currentReqNums.trim().split('\n').join(',');
      if (currentBarcodes.trim()) params.barcodes = currentBarcodes.trim().split('\n').join(',');

      const response = await axios.get(`${API_BASE_URL}/ph/strequests5/`, { // Fetches from status 5 endpoint
        params,
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(response.data.results.map(item => ({ ...item, key: item.id })));
      setTotalCount(response.data.count);
    } catch (error) {
      message.error('Ошибка загрузки отснятых заявок');
    } finally {
      setLoading(false);
    }
  }, [token, currentPage, pageSize, ordering, requestNumbers, barcodes]);

  useEffect(() => {
    if (token) {
      fetchData();
      fetchAssistants();
    }
  }, [token, fetchData, fetchAssistants]);

  const handleSearch = () => {
    setRequestNumbers(tempRequestNumbers);
    setBarcodes(tempBarcodes);
    setCurrentPage(1);
    fetchData(1, pageSize, ordering, tempRequestNumbers, tempBarcodes);
  };

  const handleResetFilters = () => {
    setTempRequestNumbers('');
    setTempBarcodes('');
    setRequestNumbers('');
    setBarcodes('');
    setCurrentPage(1);
    fetchData(1, pageSize, ordering, '', '');
  };
  
  // Assistant handlers are same as other pages
   const handleAssistantChange = async (requestNumber, assistantId) => {
    if (!token) return;
    try {
      await axios.post(`${API_BASE_URL}/ph/st-requests/assign-assistant/`,
        { request_number: requestNumber, user_id: assistantId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Ассистент назначен`);
      fetchData(currentPage, pageSize, ordering, requestNumbers, barcodes);
    } catch (error) {
      message.error('Ошибка назначения ассистента');
    }
  };

  const handleRemoveAssistant = async (requestNumber) => {
    if (!token) return;
    try {
      await axios.post(`${API_BASE_URL}/ph/st-requests/remove-assistant/`,
        { request_number: requestNumber },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Ассистент снят`);
      fetchData(currentPage, pageSize, ordering, requestNumbers, barcodes);
    } catch (error) {
      message.error('Ошибка снятия ассистента');
    }
  };
  
  const renderBooleanIcon = (value, trueTooltip = "Да", falseTooltip = "Нет") => (
    <Tooltip title={value ? trueTooltip : falseTooltip}>
      {value ? <CheckCircleOutlined style={{ color: 'green', fontSize: '16px' }} /> : <CloseCircleOutlined style={{ color: 'red', fontSize: '16px' }} />}
    </Tooltip>
  );

  const columns = [
    {
      title: 'Номер заявки',
      dataIndex: 'RequestNumber',
      key: 'RequestNumber',
      sorter: (a,b) => a.RequestNumber.localeCompare(b.RequestNumber),
      render: (text, record) => <a href={`/sph/st-request-detail/${record.RequestNumber}`} target="_blank" rel="noopener noreferrer">{text}</a>,
    },
    {
      title: 'Товаров',
      dataIndex: 'total_products',
      key: 'total_products',
      sorter: (a,b) => a.total_products - b.total_products,
    },
    {
      title: 'Приоритет',
      dataIndex: 'priority',
      key: 'priority',
      align: 'center',
      render: (priority) => renderBooleanIcon(priority),
    },
    {
      title: 'Есть инфо',
      dataIndex: 'info',
      key: 'info',
      align: 'center',
      render: (info) => renderBooleanIcon(info),
    },
    {
      title: 'Фотограф',
      dataIndex: 'photographer',
      key: 'photographer',
      render: (photographer) => photographer ? photographer.full_name : '-', // Text only
    },
    {
      title: 'Ассистент',
      dataIndex: 'assistant',
      key: 'assistant',
      width: 250,
      render: (assistant, record) => (
         <Space>
          <Select
            style={{ width: 200 }}
            placeholder="Ассистент"
            value={assistant ? assistant.id : undefined}
            onChange={(value) => handleAssistantChange(record.RequestNumber, value)}
            allowClear showSearch optionFilterProp="children"
            filterOption={(input, option) => option.children.toLowerCase().includes(input.toLowerCase())}
          >
            {assistants.map(a => <Option key={a.id} value={a.id}>{a.full_name}</Option>)}
          </Select>
          {assistant && <Tooltip title="Сбросить"><Button icon={<DeleteOutlined />} onClick={() => handleRemoveAssistant(record.RequestNumber)} danger size="small" /></Tooltip>}
        </Space>
      ),
    },
    {
      title: 'Дата назначения',
      dataIndex: 'photo_date',
      key: 'photo_date',
      sorter: (a,b) => dayjs(a.photo_date).unix() - dayjs(b.photo_date).unix(),
    },
  ];
  
  const handleTableChange = (pagination, filters, sorter) => {
    if (sorter && sorter.field) {
      const order = sorter.order === 'ascend' ? String(sorter.field) : `-${String(sorter.field)}`;
      setOrdering(order);
      fetchData(1, pageSize, order, requestNumbers, barcodes);
    } else if (sorter && !sorter.field && ordering) {
        setOrdering(null);
        fetchData(1, pageSize, null, requestNumbers, barcodes);
    }
  };

  const onPageChange = (page, newPageSize) => {
    setCurrentPage(page);
    setPageSize(newPageSize);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content style={{ padding: '24px', background: darkMode ? '#001529' : '#fff' }}>
          <Typography.Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>Отснятые заявки (Статус 5)</Typography.Title>
          <Space style={{ marginBottom: 16 }} wrap>
            <Input.TextArea placeholder="Номера заявок" value={tempRequestNumbers} onChange={e => setTempRequestNumbers(e.target.value)} rows={2} style={{width: 200}}/>
            <Input.TextArea placeholder="Штрихкоды" value={tempBarcodes} onChange={e => setTempBarcodes(e.target.value)} rows={2} style={{width: 200}}/>
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
              pageSize: pageSize,
              total: totalCount,
              onChange: onPageChange,
              showSizeChanger: true,
              pageSizeOptions: ['10', '20', '50', '100'],
              showTotal: total => `Всего: ${total}`,
            }}
            scroll={{ x: 1300 }}
            bordered
          />
        </Content>
      </Layout>
    </Layout>
  );
};

export default FilmedSTRequestsPage;