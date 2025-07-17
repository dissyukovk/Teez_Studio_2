import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Table,
  Button,
  Space,
  message,
  Modal,
  Select,
  Typography,
  Input,
  Tooltip
} from 'antd';
import { useNavigate } from 'react-router-dom';
import { FilterOutlined, EyeOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import Sidebar from '../../components/Layout/Sidebar'; // Adjust path
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config'; // Adjust path

const { Content } = Layout;
const { Title } = Typography;
const { Option } = Select;

const CreateRetouchRequestsPage = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const [token] = useState(localStorage.getItem('accessToken'));

  // Data
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [retouchers, setRetouchers] = useState([]);

  // Filters and Selection
  const [filters, setFilters] = useState({ barcodes: '' });
  const [tempFilters, setTempFilters] = useState({ barcodes: '' });
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [selectedRetoucherId, setSelectedRetoucherId] = useState(undefined);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    document.title = 'Создание заявок на ретушь';
    if (!token) {
      Modal.error({
        title: 'Ошибка доступа',
        content: 'Токен авторизации не найден. Пожалуйста, выполните вход.',
        okText: 'Войти',
        onOk: () => navigate('/login'),
      });
    }
  }, [navigate, token]);

  const fetchReadyForRetouch = useCallback(async (page = currentPage, size = pageSize, currentFilters = filters) => {
    if (!token) return;
    setLoading(true);
    try {
      const params = {
        page,
        page_size: size,
        barcodes: currentFilters.barcodes.trim().split('\n').join(','),
      };

      const response = await axios.get(`${API_BASE_URL}/srt/ready-for-retouch/`, {
        params,
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(response.data.results.map(item => ({ ...item, key: item.id })));
      setTotalCount(response.data.count);
    } catch (error) {
      message.error('Ошибка загрузки товаров для ретуши');
    } finally {
      setLoading(false);
    }
  }, [token, currentPage, pageSize, filters]);

  // MODIFIED FUNCTION
  const fetchRetouchers = useCallback(async () => {
    if (!token) return;
    try {
      const response = await axios.get(`${API_BASE_URL}/srt/retouchers/on-work/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      // ПРОВЕРКА: Убеждаемся, что в ответе есть поле "results" и оно является массивом
      if (response.data && Array.isArray(response.data.results)) {
        setRetouchers(response.data.results);
      } else {
        console.error("Data received for retouchers is not in paginated format:", response.data);
        message.error('Получен неверный формат данных для ретушеров.');
        setRetouchers([]); // Устанавливаем пустой массив, чтобы избежать сбоя
      }
    } catch (error) {
      message.error('Не удалось загрузить список ретушеров');
      setRetouchers([]); // Также устанавливаем пустой массив при ошибке
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchReadyForRetouch();
      fetchRetouchers();
    }
  }, [token, fetchReadyForRetouch, fetchRetouchers]);

  const handleSearch = () => {
    setFilters(tempFilters);
    setCurrentPage(1);
    fetchReadyForRetouch(1, pageSize, tempFilters);
  };

  const handleResetFilters = () => {
    setTempFilters({ barcodes: '' });
    setFilters({ barcodes: '' });
    setCurrentPage(1);
    fetchReadyForRetouch(1, pageSize, { barcodes: '' });
  };

  const onSelectChange = (keys) => {
    setSelectedRowKeys(keys);
  };
  
  const handleBulkSelect = (value) => {
    // Добавляем проверку на undefined или null
    if (!value) {
      setSelectedRowKeys([]); // Очищаем выделение при сбросе
      return;
    }

    const [count, stepStr] = value.split(':');
    const numCount = parseInt(count, 10);
    const step = stepStr ? parseInt(stepStr, 10) : 1;

    let selectedKeys = [];
    if (step === 1) { // Simple selection from top
      selectedKeys = data.slice(0, numCount).map(item => item.key);
    } else { // Stepped selection
      for (let i = 0; i < data.length && selectedKeys.length < numCount; i += step) {
        selectedKeys.push(data[i].key);
      }
    }
    setSelectedRowKeys(selectedKeys);
  };
  
  const handleAssign = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('Выделите хотя бы один товар для назначения.');
      return;
    }
    if (!selectedRetoucherId) {
      message.warning('Выберите ретушера.');
      return;
    }

    setLoading(true);
    try {
      await axios.post(
        `${API_BASE_URL}/srt/retouch-requests/create/`,
        {
          st_request_product_ids: selectedRowKeys,
          retoucher_id: selectedRetoucherId,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Заявка успешно создана и назначена ретушеру.`);
      setSelectedRowKeys([]);
      setSelectedRetoucherId(undefined);
      fetchReadyForRetouch(); // Refresh the list
    } catch (error) {
      const errorMsg = error.response?.data?.error || 'Ошибка при создании заявки.';
      message.error(errorMsg);
      setLoading(false);
    }
  };

  const renderBooleanIcon = (value, trueTooltip = "Да", falseTooltip = "Нет") => (
    <Tooltip title={value ? trueTooltip : falseTooltip}>
      {value ? <CheckCircleOutlined style={{ color: 'green' }} /> : <CloseCircleOutlined style={{ color: 'red' }} />}
    </Tooltip>
  );
  
  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 80, sorter: (a,b) => a.id - b.id },
    { title: 'Штрихкод', dataIndex: ['product', 'barcode'], key: 'barcode' },
    { title: 'Наименование', dataIndex: ['product', 'name'], key: 'name' },
    {
      title: 'Категория',
      key: 'category',
      render: (_, record) => record.product.category ? `${record.product.category.id} - ${record.product.category.name}` : '-',
    },
    {
      title: 'Реф',
      key: 'reference',
      align: 'center',
      render: (_, record) => {
          // Проверяем, что флаг IsReference === true и ссылка существует
          const hasReference = record.product.category?.IsReference === true;
          const referenceLink = record.product.category?.reference_link;

          return hasReference && referenceLink ? (
              <Tooltip title="Открыть референс">
                  <Button 
                      icon={<EyeOutlined />} 
                      href={referenceLink} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      size="small" 
                      type="link"
                  />
              </Tooltip>
          ) : '';
      },
    },
    { title: 'Приоритет', dataIndex: ['product', 'priority'], key: 'priority', align: 'center', render: (priority) => renderBooleanIcon(priority) },
    { title: 'Инфо', dataIndex: ['product', 'info'], key: 'info' },
    {
      title: 'Исходники',
      dataIndex: 'photos_link',
      key: 'photos_link',
      render: link => link ? <a href={link} target="_blank" rel="noopener noreferrer">Ссылка</a> : '-',
    },
    { title: 'Комментарий фотографа', dataIndex: 'ph_to_rt_comment', key: 'ph_to_rt_comment' },
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content style={{ padding: '24px', background: darkMode ? '#001529' : '#fff' }}>
          <Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>Создание заявок на ретушь</Title>
          <Space style={{ marginBottom: 16 }} wrap>
            <Input.TextArea
              placeholder="Штрихкоды (по одному на строку)"
              value={tempFilters.barcodes}
              onChange={e => setTempFilters({ ...tempFilters, barcodes: e.target.value })}
              rows={2} style={{ width: 250 }}
            />
            <Button type="primary" onClick={handleSearch} icon={<FilterOutlined />}>Поиск</Button>
            <Button onClick={handleResetFilters}>Сбросить</Button>
          </Space>

          <Space style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }} wrap>
              <Select placeholder="Массовое выделение" style={{width: 200}} onChange={handleBulkSelect} allowClear>
                <Option value="10:1">Выделить 10 верхних</Option>
                <Option value="15:1">Выделить 15 верхних</Option>
                <Option value="20:1">Выделить 20 верхних</Option>
                <Option value="10:3">10 через 3</Option>
                <Option value="15:3">15 через 3</Option>
                <Option value="10:5">10 через 5</Option>
                <Option value="15:5">15 через 5</Option>
              </Select>
            <Space>
              <Select
                placeholder="Выберите ретушера"
                style={{ width: 250 }}
                value={selectedRetoucherId}
                onChange={value => setSelectedRetoucherId(value)}
                showSearch
                optionFilterProp="children"
                filterOption={(input, option) => option.children.toLowerCase().includes(input.toLowerCase())}
              >
                {retouchers.map(r => <Option key={r.id} value={r.id}>{r.full_name}</Option>)}
              </Select>
              <Button type="primary" onClick={handleAssign} loading={loading} disabled={selectedRowKeys.length === 0 || !selectedRetoucherId}>
                Назначить ({selectedRowKeys.length})
              </Button>
            </Space>
          </Space>

          <Table
            rowSelection={rowSelection}
            columns={columns}
            dataSource={data}
            loading={loading}
            pagination={{
              current: currentPage,
              pageSize: pageSize,
              total: totalCount,
              onChange: (page, size) => { setCurrentPage(page); setPageSize(size); fetchReadyForRetouch(page, size); },
              showSizeChanger: true,
              pageSizeOptions: ['50', '100', '200', '500'],
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

export default CreateRetouchRequestsPage;