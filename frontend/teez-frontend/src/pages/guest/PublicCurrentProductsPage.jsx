import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Table, Input, Button, Space, DatePicker, Pagination, Checkbox, message, ConfigProvider, Popover, Tooltip } from 'antd';
import { UserOutlined, LinkOutlined } from '@ant-design/icons';
import axios from 'axios';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';
import ruRU from 'antd/locale/ru_RU';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import Sidebar from '../../components/Layout/Sidebar';
import UserInfoCard from '../../components/UserInfoCard';
import { API_BASE_URL } from '../../utils/config';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.locale('ru');

const { Content } = Layout;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

const CurrentProductsPage = ({ darkMode, setDarkMode }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 50, total: 0 });
  const [ordering, setOrdering] = useState('income_date');
  const [filters, setFilters] = useState({
    barcode: '',
    name: '',
    seller: '',
    category_id: '',
    incomeDateRange: [],
    info: false,
    priority: false,
  });
  const [appliedFilters, setAppliedFilters] = useState(filters);

  useEffect(() => {
    document.title = 'Текущие товары на ФС';
  }, []);

  const fetchData = useCallback(async (page, size, order) => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: size,
        ordering: order,
      };

      if (appliedFilters.barcode.trim()) {
        params.barcode = appliedFilters.barcode.split('\n').map(line => line.trim()).filter(Boolean).join(',');
      }
      if (appliedFilters.name.trim()) {
        params.name = appliedFilters.name.trim();
      }
      if (appliedFilters.seller.trim()) {
        params.seller = appliedFilters.seller.split('\n').map(line => line.trim()).filter(Boolean).join(',');
      }
      if (appliedFilters.category_id.trim()) {
        params.category_id = appliedFilters.category_id.split('\n').map(line => line.trim()).filter(Boolean).join(',');
      }
      if (appliedFilters.incomeDateRange && appliedFilters.incomeDateRange.length === 2) {
        params.income_date_after = appliedFilters.incomeDateRange[0].format('YYYY-MM-DD');
        params.income_date_before = appliedFilters.incomeDateRange[1].format('YYYY-MM-DD');
      }
      if (appliedFilters.info) params.info = true;
      if (appliedFilters.priority) params.priority = true;

      const response = await axios.get(`${API_BASE_URL}/public/current-products/`, { params });
      
      setData(response.data.results || []);
      setPagination(prev => ({ ...prev, total: response.data.count || 0, current: page, pageSize: size }));

    } catch (error) {
      console.error('Ошибка загрузки данных', error);
      message.error('Не удалось загрузить данные. Проверьте консоль для получения подробной информации.');
    } finally {
      setLoading(false);
    }
  }, [appliedFilters]);

  useEffect(() => {
    fetchData(pagination.current, pagination.pageSize, ordering);
  }, [pagination.current, pagination.pageSize, ordering, fetchData]);

  // 👇 ИСПРАВЛЕННЫЙ ОБРАБОТЧИК
  const handleTableChange = (p, f, sorter) => {
    // Эта функция теперь отвечает только за изменение сортировки
    const field = sorter.columnKey || sorter.field;
    const newOrdering = field && sorter.order
      ? (sorter.order === 'descend' ? `-${field}` : sorter.field)
      : 'income_date';
      
    setOrdering(newOrdering);
    
    // При новой сортировке всегда возвращаемся на первую страницу.
    // Важно: мы НЕ трогаем pageSize, он управляется отдельным компонентом Pagination.
    if (p.current !== 1) {
      setPagination(prev => ({ ...prev, current: 1 }));
    }
  };
  
  const handlePaginationChange = (page, pageSize) => {
    setPagination(prev => ({ ...prev, current: page, pageSize: pageSize }));
  };

  const handleSearch = () => {
    setAppliedFilters(filters);
    if (pagination.current !== 1) {
      setPagination(prev => ({ ...prev, current: 1 }));
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const columns = [
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode',
      sorter: false,
      render: (barcode, record) => {
        const adminUrl = `https://admin.teez.kz/ru/product-verification/shop/${record.seller}/product/${record.ProductID}`;
        const canShowLink = record.seller && record.ProductID;
        return (
          <Space>
            <span>{barcode}</span>
            {canShowLink && (
              <Tooltip title="Ссылка на админку">
                <a href={adminUrl} target="_blank" rel="noopener noreferrer">
                  <LinkOutlined />
                </a>
              </Tooltip>
            )}
          </Space>
        );
      },
    },
    { title: 'Наименование', dataIndex: 'name', key: 'name', sorter: false, width: 250 },
    { title: 'ID Магазина', dataIndex: 'seller', key: 'seller', sorter: true },
    {
      title: 'Категория',
      dataIndex: 'category',
      key: 'category_id',
      sorter: true,
      render: (category) => (category ? `${category.id} - ${category.name}` : '-'),
    },
    {
      title: 'Инфо',
      dataIndex: 'info',
      key: 'info',
      sorter: true,
      render: (info) => info || '-',
    },
    {
      title: 'Приоритет',
      dataIndex: 'priority',
      key: 'priority',
      sorter: true,
      render: (priority) => (priority ? 'Да' : '-'),
    },
    {
      title: 'Дата приемки',
      dataIndex: 'income_date',
      key: 'income_date',
      sorter: true,
      render: (date) => (date ? dayjs(date).format('DD.MM.YYYY HH:mm') : '-'),
    },
    {
      title: 'Товаровед',
      dataIndex: 'income_stockman',
      key: 'income_stockman',
      sorter: false,
      render: (user) => {
        if (!user) {
          return '-';
        }
        return (
          <>
            <Popover
              content={<UserInfoCard userId={user.id} />}
              trigger="click"
              placement="right"
            >
              <UserOutlined style={{ marginRight: 8, cursor: 'pointer' }} />
            </Popover>
            <span>{user.full_name}</span>
          </>
        );
      },
    },
    {
      title: 'Созданные заявки',
      dataIndex: 'STRequest2',
      key: 'STRequest2',
      sorter: false,
      render: (reqs) => (Array.isArray(reqs) && reqs.length > 0 ? reqs.join(', ') : '-'),
    },
    {
      title: 'На съемки',
      dataIndex: 'STRequest3',
      key: 'STRequest3',
      sorter: false,
      render: (reqs) => (Array.isArray(reqs) && reqs.length > 0 ? reqs.join(', ') : '-'),
    },
    {
      title: 'Отснятые',
      dataIndex: 'STRequest5',
      key: 'STRequest5',
      sorter: false,
      render: (reqs) => (Array.isArray(reqs) && reqs.length > 0 ? reqs.join(', ') : '-'),
    },
  ];

  return (
    <ConfigProvider locale={ruRU}>
      <Layout>
        <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
        <Content style={{ padding: '16px' }}>
          <h2>Текущие товары на ФС</h2>
          <Space style={{ marginBottom: 16 }} wrap>
            <Space direction="vertical">
              <div>Штрихкод(ы)</div>
              <TextArea placeholder="Каждый на новой строке" value={filters.barcode} onChange={(e) => handleFilterChange('barcode', e.target.value)} style={{ width: 180 }} rows={4} />
            </Space>
            <Space direction="vertical">
              <div>Наименование</div>
              <Input placeholder="Часть наименования" value={filters.name} onChange={(e) => handleFilterChange('name', e.target.value)} style={{ width: 180 }} />
            </Space>
            <Space direction="vertical">
              <div>ID Магазина</div>
              <TextArea placeholder="Каждый на новой строке" value={filters.seller} onChange={(e) => handleFilterChange('seller', e.target.value)} style={{ width: 180 }} rows={4} />
            </Space>
            <Space direction="vertical">
              <div>ID Категории</div>
              <TextArea placeholder="Каждый на новой строке" value={filters.category_id} onChange={(e) => handleFilterChange('category_id', e.target.value)} style={{ width: 180 }} rows={4} />
            </Space>
            <Space direction="vertical">
              <div>Дата приемки</div>
              <RangePicker format="DD.MM.YYYY" value={filters.incomeDateRange} onChange={(dates) => handleFilterChange('incomeDateRange', dates || [])} />
              <Checkbox checked={filters.info} onChange={(e) => handleFilterChange('info', e.target.checked)}>Наличие Инфо</Checkbox>
              <Checkbox checked={filters.priority} onChange={(e) => handleFilterChange('priority', e.target.checked)}>Приоритет</Checkbox>
            </Space>
            <Space direction="vertical" style={{ alignSelf: 'flex-end' }}>
              <Button type="primary" onClick={handleSearch}>Поиск</Button>
            </Space>
          </Space>

          <Pagination
            current={pagination.current}
            pageSize={pagination.pageSize}
            total={pagination.total}
            showSizeChanger
            showTotal={(total, range) => `${range[0]}-${range[1]} из ${total} товаров`}
            onChange={handlePaginationChange}
            onShowSizeChange={handlePaginationChange}
            style={{ marginBottom: 16, textAlign: 'right' }}
            pageSizeOptions={['10', '20', '50', '100']}
          />

          <Table
            columns={columns}
            dataSource={data}
            loading={loading}
            onChange={handleTableChange}
            rowKey="barcode"
            pagination={false}
            scroll={{ x: 1500 }}
          />
        </Content>
      </Layout>
    </ConfigProvider>
  );
};

export default CurrentProductsPage;