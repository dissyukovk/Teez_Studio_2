import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Table, Input, Button, Space, message, Modal, Typography, Select, Tooltip } from 'antd';
import { useNavigate } from 'react-router-dom';
import { FilterOutlined, DeleteOutlined } from '@ant-design/icons';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';
import dayjs from 'dayjs';

const { Content } = Layout;
const { Title } = Typography;
const { Option } = Select;

const RetouchRequestsListPage = ({ darkMode, setDarkMode, statusId, pageTitle }) => {
  const navigate = useNavigate();
  const [token] = useState(localStorage.getItem('accessToken'));

  // Data
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [availableRetouchers, setAvailableRetouchers] = useState([]); // Renamed for clarity

  // Filters
  const [filters, setFilters] = useState({ requestNumbers: '', barcodes: '' });
  const [tempFilters, setTempFilters] = useState({ requestNumbers: '', barcodes: '' });

  // Pagination & Sorting
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    document.title = pageTitle;
    if (!token) {
      Modal.error({
        title: 'Ошибка доступа',
        content: 'Токен авторизации не найден.',
        okText: 'Войти',
        onOk: () => navigate('/login'),
      });
    }
  }, [navigate, token, pageTitle]);

  // Function to fetch available retouchers
  const fetchAvailableRetouchers = useCallback(async () => {
    if (!token) return;
    try {
      const response = await axios.get(`${API_BASE_URL}/srt/retouchers/on-work/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setAvailableRetouchers(Array.isArray(response.data.results) ? response.data.results : []); // Access results property
    } catch (error) {
      console.error('Ошибка загрузки ретушеров:', error);
      message.error('Ошибка загрузки списка ретушеров.');
      setAvailableRetouchers([]);
    }
  }, [token]);

  const fetchData = useCallback(async (page = currentPage, size = pageSize, currentFilters = filters) => {
    if (!token) return;
    setLoading(true);
    try {
      const params = {
        page,
        page_size: size,
        RequestNumber: currentFilters.requestNumbers.trim().split('\n').join(','),
        barcodes: currentFilters.barcodes.trim().split('\n').join(','),
      };
      
      const response = await axios.get(`${API_BASE_URL}/srt/retouch-requests/status/${statusId}/`, {
        params,
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(response.data.results.map(item => ({ ...item, key: item.id })));
      setTotalCount(response.data.count);
    } catch (error) {
      message.error(`Ошибка загрузки заявок со статусом "${pageTitle}"`);
    } finally {
      setLoading(false);
    }
  }, [token, currentPage, pageSize, filters, statusId, pageTitle]);

  useEffect(() => {
    if (token) {
      fetchData();
      fetchAvailableRetouchers(); // Call fetchAvailableRetouchers here
    }
  }, [token, fetchData, fetchAvailableRetouchers]);

  const handleSearch = () => {
    setFilters(tempFilters);
    setCurrentPage(1);
    fetchData(1, pageSize, tempFilters);
  };

  const handleResetFilters = () => {
    setTempFilters({ requestNumbers: '', barcodes: '' });
    setFilters({ requestNumbers: '', barcodes: '' });
    setCurrentPage(1);
    fetchData(1, pageSize, { requestNumbers: '', barcodes: '' });
  };

  const handleRetoucherReassign = async (requestNumber, newRetoucherId) => {
    if (!token) return;
    try {
      await axios.patch(
        `${API_BASE_URL}/srt/reassign-retoucher/`,
        { request_number: requestNumber, retoucher_id: newRetoucherId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Ретушер для заявки ${requestNumber} переназначен.`);
      fetchData(currentPage, pageSize, filters); // Re-fetch data to reflect changes
    } catch (error) {
      const errorMsg = error.response?.data?.error || `Ошибка переназначения ретушера для заявки ${requestNumber}.`;
      message.error(errorMsg);
      console.error("Reassign retoucher error:", error.response?.data || error);
    }
  };

  const columns = [
    {
      title: 'Номер заявки',
      dataIndex: 'RequestNumber',
      key: 'RequestNumber',
      render: (text) => <a onClick={() => navigate(`/srt/RetouchRequestDetailPage/${text}/`)}>{text}</a>,
    },
    {
      title: 'Дата создания',
      dataIndex: 'creation_date',
      key: 'creation_date',
      render: (date) => dayjs(date).format('DD.MM.YYYY HH:mm'),
    },
    {
      title: 'Ретушер',
      dataIndex: 'retoucher',
      key: 'retoucher',
      render: (assignedRetoucher, record) => {
        let allRetoucherOptions = Array.isArray(availableRetouchers) ? [...availableRetouchers] : [];

        // If an retoucher is assigned but not in the currently available list, add them to options
        if (assignedRetoucher && assignedRetoucher.id &&
            !allRetoucherOptions.some(r => r.id === assignedRetoucher.id)) {
            allRetoucherOptions = [
                { id: assignedRetoucher.id, full_name: assignedRetoucher.full_name },
                ...allRetoucherOptions
            ];
        }

        // Deduplicate options based on ID
        const uniqueOptions = Array.from(new Map(allRetoucherOptions.map(r => [r.id, r])).values());

        return (
          <Space>
            <Select
              style={{ width: 180 }}
              placeholder="Выберите ретушера"
              value={assignedRetoucher ? assignedRetoucher.id : undefined}
              onChange={(value) => handleRetoucherReassign(record.RequestNumber, value)}
              allowClear
              showSearch
              optionFilterProp="children"
              filterOption={(input, option) =>
                option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
              }
            >
              {uniqueOptions.map(r => (
                <Option key={r.id} value={r.id}>
                  {r.full_name}
                </Option>
              ))}
            </Select>
          </Space>
        );
      },
    },
    {
      title: 'Количество товаров',
      dataIndex: 'total_products',
      key: 'total_products',
      align: 'center',
    },
    {
      title: 'На проверку',
      dataIndex: 'unchecked_product',
      key: 'unchecked_product',
      align: 'center',
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content style={{ padding: '24px', background: darkMode ? '#001529' : '#fff' }}>
          <Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>{pageTitle}</Title>
          <Space style={{ marginBottom: 16 }} wrap>
            <Input.TextArea
              placeholder="Номера заявок"
              value={tempFilters.requestNumbers}
              onChange={e => setTempFilters({ ...tempFilters, requestNumbers: e.target.value })}
              rows={2} style={{ width: 200 }}
            />
            <Input.TextArea
              placeholder="Штрихкоды"
              value={tempFilters.barcodes}
              onChange={e => setTempFilters({ ...tempFilters, barcodes: e.target.value })}
              rows={2} style={{ width: 200 }}
            />
            <Button type="primary" onClick={handleSearch} icon={<FilterOutlined />}>Поиск</Button>
            <Button onClick={handleResetFilters}>Сбросить</Button>
          </Space>
          <Table
            columns={columns}
            dataSource={data}
            loading={loading}
            pagination={{
              current: currentPage,
              pageSize: pageSize,
              total: totalCount,
              onChange: (page, size) => { setCurrentPage(page); setPageSize(size); fetchData(page, size); },
              showSizeChanger: true,
              pageSizeOptions: ['10', '20', '50', '100'],
              showTotal: total => `Всего: ${total}`,
            }}
            scroll={{ x: 1000 }}
            bordered
          />
        </Content>
      </Layout>
    </Layout>
  );
};

export default RetouchRequestsListPage;