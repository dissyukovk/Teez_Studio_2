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

const NofotoPage = ({ darkMode, setDarkMode }) => {
  useEffect(() => {
    document.title = 'Товары без фото';
  }, []);

  // Используем message.useMessage для отображения индикатора экспорта Excel
  const [messageApi, contextHolder] = message.useMessage();

  // Состояния для данных и фильтров
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [barcodesMulti, setBarcodesMulti] = useState('');
  const [seller, setSeller] = useState('');
  const [dateRange, setDateRange] = useState([]);
  const [ordering, setOrdering] = useState('-date');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  // Определение колонок таблицы
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
      dataIndex: 'shop',
      key: 'shop',
      sorter: true,
    },
    {
      title: 'Дата',
      dataIndex: 'date',
      key: 'date',
      sorter: true,
      render: (value) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'),
    },
  ];

  // Маппинг полей для сортировки (фронт → DRF)
  const orderingMap = {
    barcode: 'product__barcode',
    name: 'product__name',
    shop: 'product__seller',
    date: 'date',
  };

  // Функция для загрузки данных с сервера
  const fetchData = useCallback(
    async (page = 1, size = 50, order = '-date') => {
      setLoading(true);
      try {
        const params = {
          page,
          page_size: size,
          ordering: order,
        };

        // Фильтрация по штрихкодам (несколько значений через многострочный ввод)
        if (barcodesMulti.trim()) {
          const lines = barcodesMulti
            .split('\n')
            .map((l) => l.trim())
            .filter(Boolean);
          params.barcodes = lines.join(',');
        }

        // Фильтрация по магазинам (несколько значений, каждый на новой строке; только цифры)
        if (seller.trim()) {
          const sellers = seller
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean);
          params.seller = sellers.join(',');
        }

        // Фильтрация по диапазону дат
        if (dateRange.length === 2) {
          const [start, end] = dateRange;
          params.start_date = start.format('YYYY-MM-DD');
          params.end_date = end.format('YYYY-MM-DD');
        }

        const response = await axios.get(`${API_BASE_URL}/nofoto_list/`, { params });
        const results = response.data.results || [];
        setData(
          results.map((item) => ({
            key: item.id,
            barcode: item.barcode,
            name: item.name,
            shop: item.shop,
            date: item.date,
          }))
        );
        setTotalCount(response.data.count || 0);
        setCurrentPage(page);
        setPageSize(size);
      } catch (error) {
        console.error('Error loading data:', error);
        message.error('Ошибка загрузки данных');
      } finally {
        setLoading(false);
      }
    },
    [barcodesMulti, seller, dateRange]
  );

  // Первый рендер: загрузка данных
  useEffect(() => {
    fetchData(currentPage, pageSize, ordering);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Обработка изменений в таблице (сортировка)
  const handleTableChange = (pagination, filters, sorter) => {
    let newOrdering = ordering;
    if (sorter.field) {
      const drfField = orderingMap[sorter.field] || sorter.field;
      newOrdering = sorter.order === 'descend' ? `-${drfField}` : drfField;
    }
    setOrdering(newOrdering);
    fetchData(currentPage, pageSize, newOrdering);
  };

  // Обработка пагинации (смена страницы и/или количества записей на странице)
  const handlePageChange = (page, size) => {
    setCurrentPage(page);
    setPageSize(size);
    fetchData(page, size, ordering);
  };

  // Обработка нажатия на кнопку "Поиск/Фильтр"
  const handleSearch = () => {
    fetchData(1, pageSize, ordering);
  };

  // Экспорт данных в Excel с индикатором загрузки
  const handleExportExcel = async () => {
    // Показываем индикатор загрузки
    const hideLoading = messageApi.open({
      type: 'loading',
      content: 'Формирование файла Excel...',
      duration: 0,
    });
    try {
      const params = {
        page_size: 500000,
        ordering,
      };
      if (barcodesMulti.trim()) {
        const lines = barcodesMulti
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean);
        params.barcodes = lines.join(',');
      }
      if (seller.trim()) {
        const sellers = seller
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean);
        params.seller = sellers.join(',');
      }
      if (dateRange.length === 2) {
        const [start, end] = dateRange;
        params.start_date = start.format('YYYY-MM-DD');
        params.end_date = end.format('YYYY-MM-DD');
      }
      const resp = await axios.get(`${API_BASE_URL}/nofoto_list/`, { params });
      const allResults = resp.data.results || [];
      const wsData = allResults.map((item) => ({
        'Штрихкод': Number(item.barcode) || item.barcode,
        'Наименование': item.name || '',
        'Магазин': item.shop || '',
        'Дата': item.date ? dayjs(item.date).format('YYYY-MM-DD HH:mm') : '',
      }));
      const worksheet = XLSX.utils.json_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Nofoto');
      const now = new Date();
      const fileName = `nofoto_${now
        .toISOString()
        .slice(0, 19)
        .replace('T', '_')
        .replace(/:/g, '-')}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      hideLoading();
      message.success('Файл Excel сформирован');
    } catch (error) {
      console.error('Excel export error:', error);
      hideLoading();
      message.error('Ошибка экспорта в Excel');
    }
  };

  return (
    <Layout>
      {contextHolder}
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список товаров, которые не получилось снять без вскрытия</h2>
        <Space style={{ marginBottom: 16 }} align="start">
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

export default NofotoPage;
