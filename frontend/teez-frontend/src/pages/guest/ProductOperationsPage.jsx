import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Table, Input, Button, Space, DatePicker, Pagination, message } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import * as XLSX from 'xlsx';
import dayjs from 'dayjs';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

const ProductOperationsPage = ({ darkMode, setDarkMode }) => {
  useEffect(() => {
    document.title = 'История операций с товарами';
  }, []);

  // Контекст для сообщений (включая loading)
  const [messageApi, contextHolder] = message.useMessage();

  // Состояния для данных и фильтров
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [barcodesMulti, setBarcodesMulti] = useState('');
  const [seller, setSeller] = useState('');
  // Выбранные типы операций храним в виде массива ID
  const [opTypeFilter, setOpTypeFilter] = useState([]);
  const [dateRange, setDateRange] = useState([]);
  const [ordering, setOrdering] = useState('-date');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);
  // Список типов операций для фильтрации (получаем с бэка)
  const [operationTypesOptions, setOperationTypesOptions] = useState([]);
  // Штрихкоды, для которых не найдены записи (возвращается бэком)
  const [notFoundBarcodes, setNotFoundBarcodes] = useState([]);

  // Загрузка списка типов операций для фильтрации в колонке
  useEffect(() => {
    axios
      .get(`${API_BASE_URL}/ft/product-operation-types/`)
      .then((response) => {
        const options = response.data.map((item) => ({
          text: item.name,
          value: item.id, // value – это ID, т.к. фильтрация идёт по ID
        }));
        setOperationTypesOptions(options);
      })
      .catch((error) => {
        console.error('Error fetching operation types:', error);
      });
  }, []);

  // Функция для загрузки данных с сервера
  const fetchData = useCallback(
    async (page = 1, size = 50, order = '-date', opType = []) => {
      setLoading(true);
      try {
        const params = {
          page,
          page_size: size,
          ordering: order,
        };

        // Фильтрация по штрихкодам (каждый штрихкод с новой строки)
        if (barcodesMulti.trim()) {
          const lines = barcodesMulti.split('\n').map((l) => l.trim()).filter(Boolean);
          params.barcode = lines.join(',');
        }

        // Фильтрация по магазинам (каждый id с новой строки)
        if (seller.trim()) {
          const sellers = seller.split('\n').map((s) => s.trim()).filter(Boolean);
          params.seller = sellers.join(',');
        }

        // Если выбран фильтр по типам операций – передаем их как "5,6" (один параметр)
        if (Array.isArray(opType) && opType.length > 0) {
          params.operation_type = opType.join(',');
        }

        // Фильтрация по диапазону дат (включительно)
        if (dateRange.length === 2) {
          const [start, end] = dateRange;
          params.date_from = start.format('YYYY-MM-DD');
          params.date_to = end.format('YYYY-MM-DD');
        }

        const response = await axios.get(`${API_BASE_URL}/ft/product-operations/`, { params });
        const results = response.data.results || [];
        setData(
          results.map((item, index) => ({
            key: index,
            barcode: item.barcode,
            name: item.name,
            seller: item.seller,
            operation_type: item.operation_type, // отображается как имя операции
            user: item.user,
            date: item.date,
            comment: item.comment,
          }))
        );
        setTotalCount(response.data.count || 0);
        setCurrentPage(page);
        setPageSize(size);
        // Обновляем штрихкоды, для которых не найдены записи
        if (response.data.not_found_barcodes) {
          setNotFoundBarcodes(response.data.not_found_barcodes);
        } else {
          setNotFoundBarcodes([]);
        }
      } catch (error) {
        console.error('Error loading data:', error);
        message.error('Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    },
    [barcodesMulti, seller, dateRange]
  );

  // Маппинг полей для сортировки (фронт → DRF)
  const orderingMap = {
    barcode: 'product__barcode',
    name: 'product__name',
    seller: 'product__seller',
    operation_type: 'operation_type__name',
    user: 'user__first_name',
    date: 'date',
    comment: 'comment',
  };

  const handleTableChange = (pagination, filters, sorter) => {
    let newOrdering = ordering;
    if (sorter.field) {
      const drfField = orderingMap[sorter.field] || sorter.field;
      newOrdering = sorter.order === 'descend' ? `-${drfField}` : drfField;
    }
    const opFilter = (filters && filters.operation_type) || [];
    setOpTypeFilter(opFilter);
    setOrdering(newOrdering);
    fetchData(currentPage, pageSize, newOrdering, opFilter);
  };

  const handlePageChange = (page, size) => {
    setCurrentPage(page);
    setPageSize(size);
    fetchData(page, size, ordering, opTypeFilter);
  };

  const handleSearch = () => {
    fetchData(1, pageSize, ordering, opTypeFilter);
  };

  const handleExportExcel = async () => {
    // Показываем индикатор загрузки
    const hideLoading = messageApi.open({
      type: 'loading',
      content: 'Формирование файла Excel...',
      duration: 0,
    });
    try {
      const params = {
        page_size: 900000,
        ordering,
      };
      if (barcodesMulti.trim()) {
        const lines = barcodesMulti.split('\n').map((l) => l.trim()).filter(Boolean);
        params.barcode = lines.join(',');
      }
      if (seller.trim()) {
        const sellers = seller.split('\n').map((s) => s.trim()).filter(Boolean);
        params.seller = sellers.join(',');
      }
      if (opTypeFilter && opTypeFilter.length > 0) {
        params.operation_type = opTypeFilter.join(',');
      }
      if (dateRange.length === 2) {
        const [start, end] = dateRange;
        params.date_from = start.format('YYYY-MM-DD');
        params.date_to = end.format('YYYY-MM-DD');
      }
      const resp = await axios.get(`${API_BASE_URL}/ft/product-operations/`, { params });
      const allResults = resp.data.results || [];
      const wsData = allResults.map((item) => ({
        'Штрихкод': Number(item.barcode),
        'Наименование': item.name || '',
        'Магазин': item.seller || '',
        'Тип операции': item.operation_type || '',
        'Пользователь': item.user || '',
        'Дата': item.date ? dayjs(item.date).format('YYYY-MM-DD HH:mm') : '',
        'Комментарий': item.comment || '',
      }));
      const worksheet = XLSX.utils.json_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'ProductOperations');
      const now = new Date();
      const fileName = `product_operations_${now.toISOString().slice(0, 19).replace('T', '_').replace(/:/g, '-')}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      messageApi.destroy();
      message.success('Файл Excel сформирован');
    } catch (error) {
      console.error('Excel export error:', error);
      messageApi.destroy();
      message.error('Ошибка экспорта в Excel');
    }
  };

  const columns = [
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode',
      sorter: true,
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
      sorter: true,
    },
    {
      title: 'Магазин',
      dataIndex: 'seller',
      key: 'seller',
      sorter: true,
    },
    {
      title: 'Тип операции',
      dataIndex: 'operation_type',
      key: 'operation_type',
      sorter: true,
      filters: operationTypesOptions,
    },
    {
      title: 'Пользователь',
      dataIndex: 'user',
      key: 'user',
      sorter: true,
    },
    {
      title: 'Дата',
      dataIndex: 'date',
      key: 'date',
      sorter: true,
      render: (value) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: 'Комментарий',
      dataIndex: 'comment',
      key: 'comment',
      sorter: true,
    },
  ];

  return (
    <Layout>
      {contextHolder}
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>История операций с товарами</h2>
        <Space style={{ marginBottom: 16, width: '100%' }} align="start">
          {/* Группа фильтров слева */}
          <Space size="middle">
            <TextArea
              placeholder="Штрихкоды (каждый в новой строке)"
              value={barcodesMulti}
              onChange={(e) => setBarcodesMulti(e.target.value)}
              style={{ width: 200 }}
              rows={4}
            />
            <TextArea
              placeholder="Магазины (каждый в новой строке, только цифры)"
              value={seller}
              onChange={(e) => setSeller(e.target.value.replace(/[^\d\n]/g, ''))}
              style={{ width: 200 }}
              rows={4}
            />
            <RangePicker
              format="YYYY-MM-DD"
              value={dateRange}
              onChange={(values) => setDateRange(values || [])}
            />
            <Button type="primary" onClick={handleSearch}>
              Поиск
            </Button>
            <Button onClick={handleExportExcel}>Скачать Excel</Button>
          </Space>
          {/* Блок с штрихкодами, для которых не найдены записи, прижат к правому краю */}
          <TextArea
            placeholder="Не найдены штрихкоды"
            value={notFoundBarcodes.join('\n')}
            style={{ width: 200, marginLeft: 'auto' }}
            rows={4}
            readOnly
          />
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

export default ProductOperationsPage;
