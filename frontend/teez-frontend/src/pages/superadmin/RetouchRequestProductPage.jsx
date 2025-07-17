import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Table, Input, Button, Space, DatePicker, Pagination, message, Select, Tag } from 'antd';
import Sidebar from '../../components/Layout/Sidebar'; // Assuming this path is correct
import axios from 'axios';
import * as XLSX from 'xlsx';
import dayjs from 'dayjs';
import { API_BASE_URL } from '../../utils/config'; // Assuming this path is correct

const { Content } = Layout;
const { RangePicker } = DatePicker;

const RetouchRequestProductPage = ({ darkMode, setDarkMode }) => {
  useEffect(() => {
    document.title = 'Продукты в заявках на ретушь';
  }, []);

  const [messageApi, contextHolder] = message.useMessage();

  // --- Состояния для данных и фильтров ---
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [ordering, setOrdering] = useState('-retouch_request__creation_date');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  // --- Состояния фильтров ---
  const [filters, setFilters] = useState({
    requestNumber: '',
    barcode: '',
    retouchStatus: null,
    sretouchStatus: null,
    dateRange: [],
  });
  
  // --- Options for Select Filters ---
  const [retouchStatusOptions, setRetouchStatusOptions] = useState([]);
  const [sretouchStatusOptions, setSretouchStatusOptions] = useState([]);

  // --- Fetch Status Options for Filters ---
  useEffect(() => {
    // Fetch Retouch Statuses
    axios.get(`${API_BASE_URL}/api/retouch-statuses/`) // Adjust this URL if needed
      .then(response => {
        setRetouchStatusOptions(response.data.map(item => ({ value: item.id, label: item.name })));
      })
      .catch(error => console.error('Error fetching retouch statuses:', error));

    // Fetch Senior Retouch Statuses
    axios.get(`${API_BASE_URL}/api/sretouch-statuses/`) // Adjust this URL if needed
      .then(response => {
        setSretouchStatusOptions(response.data.map(item => ({ value: item.id, label: item.name })));
      })
      .catch(error => console.error('Error fetching senior retouch statuses:', error));
  }, []);


  // --- Data Fetching ---
  const fetchData = useCallback(async (page = 1, size = 50, order = ordering) => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: size,
        ordering: order,
        // Add filters to params if they are set
        ...(filters.requestNumber && { 'retouch_request__RequestNumber': filters.requestNumber }),
        ...(filters.barcode && { 'st_request_product__product__barcode': filters.barcode }),
        ...(filters.retouchStatus && { 'retouch_status': filters.retouchStatus }),
        ...(filters.sretouchStatus && { 'sretouch_status': filters.sretouchStatus }),
        ...(filters.dateRange && filters.dateRange.length === 2 && {
          'retouch_request__creation_date__gte': filters.dateRange[0].format('YYYY-MM-DD'),
          'retouch_request__creation_date__lte': filters.dateRange[1].format('YYYY-MM-DD'),
        }),
      };

      const response = await axios.get(`${API_BASE_URL}/srt/retouch-request-products/`, { params });
      setData(response.data.results || []);
      setTotalCount(response.data.count || 0);
      setCurrentPage(page);
      setPageSize(size);

    } catch (error) {
      console.error('Error loading data:', error);
      message.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  }, [filters, ordering]);

  // --- Event Handlers ---
  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const handleSearch = () => {
    fetchData(1, pageSize, ordering);
  };
  
  const handleTableChange = (pagination, tableFilters, sorter) => {
    const orderingMap = {
      // Maps antd column `key` to the DRF ordering field
      request_number: 'retouch_request__RequestNumber',
      creation_date: 'retouch_request__creation_date',
      retoucher: 'retouch_request__retoucher__full_name',
      barcode: 'st_request_product__product__barcode',
      product_name: 'st_request_product__product__name',
      retouch_status: 'retouch_status__name',
      sretouch_status: 'sretouch_status__name',
    };

    let newOrdering = ordering;
    if (sorter.field && sorter.order) {
      const drfField = orderingMap[sorter.field] || sorter.field;
      newOrdering = sorter.order === 'descend' ? `-${drfField}` : drfField;
    }
    
    setOrdering(newOrdering);
    fetchData(currentPage, pageSize, newOrdering);
  };

  const handlePageChange = (page, size) => {
    fetchData(page, size, ordering);
  };

  // --- Excel Export ---
  const handleExportExcel = async () => {
    const hideLoading = messageApi.open({
      type: 'loading',
      content: 'Формирование файла Excel...',
      duration: 0,
    });
    try {
      // Fetch all data (up to a large limit)
      const params = {
        page_size: totalCount > 0 ? totalCount : 999999, // Use totalCount or a large number
        ordering,
        ...(filters.requestNumber && { 'retouch_request__RequestNumber': filters.requestNumber }),
        ...(filters.barcode && { 'st_request_product__product__barcode': filters.barcode }),
        ...(filters.retouchStatus && { 'retouch_status': filters.retouchStatus }),
        ...(filters.sretouchStatus && { 'sretouch_status': filters.sretouchStatus }),
        ...(filters.dateRange && filters.dateRange.length === 2 && {
          'retouch_request__creation_date__gte': filters.dateRange[0].format('YYYY-MM-DD'),
          'retouch_request__creation_date__lte': filters.dateRange[1].format('YYYY-MM-DD'),
        }),
      };

      const response = await axios.get(`${API_BASE_URL}/srt/retouch-request-products/`, { params });
      const allResults = response.data.results || [];

      // Map nested data to a flat structure for the Excel sheet
      const wsData = allResults.map(item => ({
        'ID Записи': item.id,
        'Номер заявки на ретушь': item.retouch_request?.RequestNumber,
        'Ретушер': item.retouch_request?.retoucher?.full_name,
        'Дата создания заявки': item.retouch_request?.creation_date ? dayjs(item.retouch_request.creation_date).format('YYYY-MM-DD HH:mm') : '',
        'Дата ретуши заявки': item.retouch_request?.retouch_date ? dayjs(item.retouch_request.retouch_date).format('YYYY-MM-DD HH:mm') : '',
        'Статус заявки': item.retouch_request?.status?.name,
        'Штрихкод': item.st_request_product?.product?.barcode,
        'Наименование товара': item.st_request_product?.product?.name,
        'Категория товара': item.st_request_product?.product?.category?.name,
        'Магазин': item.st_request_product?.product?.seller,
        'Приоритет': item.st_request_product?.product?.priority ? 'Да' : 'Нет',
        'Ссылка на фото (съемка)': item.st_request_product?.photos_link,
        'Комментарий (Фотограф -> Ретушер)': item.st_request_product?.ph_to_rt_comment,
        'Статус ретуши': item.retouch_status?.name,
        'Статус проверки ст. ретушером': item.sretouch_status?.name,
        'Ссылка на ретушь': item.retouch_link,
        'Комментарий ст. ретушера': item.comment,
        'В Загрузке': item.IsOnUpload ? 'Да' : 'Нет',
        'Номер заявки на съемку': item.st_request_product?.request?.RequestNumber,
        'Фотограф': item.st_request_product?.request?.photographer?.full_name,
        'Кладовщик': item.st_request_product?.request?.stockman?.full_name,
        'Ассистент': item.st_request_product?.request?.assistant?.full_name,
        'Статус заявки на съемку': item.st_request_product?.request?.status?.name,
        'Дата создания заявки на съемку': item.st_request_product?.request?.creation_date ? dayjs(item.st_request_product.request.creation_date).format('YYYY-MM-DD HH:mm') : '',
        'Дата фотосъемки': item.st_request_product?.request?.photo_date ? dayjs(item.st_request_product.request.photo_date).format('YYYY-MM-DD HH:mm') : '',
        'Дата назначения ассистента': item.st_request_product?.request?.assistant_date ? dayjs(item.st_request_product.request.assistant_date).format('YYYY-MM-DD HH:mm') : '',
      }));

      const worksheet = XLSX.utils.json_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'RetouchProducts');
      const fileName = `retouch_products_${dayjs().format('YYYY-MM-DD_HH-mm-ss')}.xlsx`;
      XLSX.writeFile(workbook, fileName);

      messageApi.destroy();
      message.success('Файл Excel успешно сформирован');

    } catch (error) {
      console.error('Excel export error:', error);
      messageApi.destroy();
      message.error('Ошибка экспорта в Excel');
    }
  };

  // --- Table Columns Definition ---
  const columns = [
    // From RetouchRequest
    { title: 'Номер заявки', dataIndex: ['retouch_request', 'RequestNumber'], key: 'request_number', sorter: true },
    { title: 'Дата создания', dataIndex: ['retouch_request', 'creation_date'], key: 'creation_date', sorter: true, render: (text) => text ? dayjs(text).format('YYYY-MM-DD HH:mm') : '-' },
    { title: 'Ретушер', dataIndex: ['retouch_request', 'retoucher', 'full_name'], key: 'retoucher', sorter: true },
    
    // From Product
    { title: 'Штрихкод', dataIndex: ['st_request_product', 'product', 'barcode'], key: 'barcode', sorter: true },
    { title: 'Наименование товара', dataIndex: ['st_request_product', 'product', 'name'], key: 'product_name', sorter: true },
    
    // From RetouchRequestProduct, RetouchStatus, SRetouchStatus
    { title: 'Статус ретуши', dataIndex: ['retouch_status', 'name'], key: 'retouch_status', sorter: true, render: (text) => <Tag>{text || 'Нет'}</Tag> },
    { title: 'Статус проверки', dataIndex: ['sretouch_status', 'name'], key: 'sretouch_status', sorter: true, render: (text) => <Tag>{text || 'Нет'}</Tag> },
    { title: 'В загрузке', dataIndex: 'IsOnUpload', key: 'IsOnUpload', render: (is) => (is ? 'Да' : 'Нет') },

    // Links and Comments
    { title: 'Ссылка на ретушь', dataIndex: 'retouch_link', key: 'retouch_link', render: (link) => link ? <a href={link} target="_blank" rel="noopener noreferrer">Ссылка</a> : '-' },
    { title: 'Комментарий ст. ретушера', dataIndex: 'comment', key: 'comment' },
  ];

  return (
    <Layout>
      {contextHolder}
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Продукты в заявках на ретушь</h2>
        
        {/* --- Filter Controls --- */}
        <Space direction="vertical" style={{ marginBottom: 16, width: '100%' }}>
            <Space wrap>
                <Input
                    placeholder="Номер заявки"
                    value={filters.requestNumber}
                    onChange={(e) => handleFilterChange('requestNumber', e.target.value)}
                    style={{ width: 200 }}
                />
                <Input
                    placeholder="Штрихкод товара"
                    value={filters.barcode}
                    onChange={(e) => handleFilterChange('barcode', e.target.value)}
                    style={{ width: 200 }}
                />
                <Select
                    placeholder="Статус ретуши"
                    allowClear
                    style={{ width: 200 }}
                    options={retouchStatusOptions}
                    value={filters.retouchStatus}
                    onChange={(value) => handleFilterChange('retouchStatus', value)}
                />
                <Select
                    placeholder="Статус проверки"
                    allowClear
                    style={{ width: 200 }}
                    options={sretouchStatusOptions}
                    value={filters.sretouchStatus}
                    onChange={(value) => handleFilterChange('sretouchStatus', value)}
                />
                <RangePicker
                    format="YYYY-MM-DD"
                    value={filters.dateRange}
                    onChange={(values) => handleFilterChange('dateRange', values || [])}
                />
                <Button type="primary" onClick={handleSearch}>Поиск</Button>
                <Button onClick={handleExportExcel}>Скачать Excel</Button>
            </Space>
        </Space>

        {/* --- Pagination --- */}
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

        {/* --- Data Table --- */}
        <Table
          columns={columns}
          dataSource={data}
          loading={loading}
          onChange={handleTableChange}
          pagination={false}
          rowKey="id"
          scroll={{ x: 1300 }} // Enable horizontal scroll for many columns
        />
      </Content>
    </Layout>
  );
};

export default RetouchRequestProductPage;