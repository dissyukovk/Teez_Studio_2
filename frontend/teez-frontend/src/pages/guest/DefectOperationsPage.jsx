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

const DefectOperationsPage = ({ darkMode, setDarkMode }) => {
  useEffect(() => {
    document.title = 'Список браков';
  }, []);

  const [messageApi, contextHolder] = message.useMessage();

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [barcodesMulti, setBarcodesMulti] = useState('');
  const [productName, setProductName] = useState('');
  const [dateRange, setDateRange] = useState([]);
  const [ordering, setOrdering] = useState('-date'); // Начальное состояние сортировки
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  const columns = [
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode',
      sorter: true,
    },
    {
      title: 'Наименование',
      dataIndex: 'product_name',
      key: 'product_name',
      sorter: true,
    },
    {
      title: 'Магазин',
      dataIndex: 'seller',
      key: 'seller',
    },
    {
      title: 'Пользователь',
      dataIndex: 'user_full_name',
      key: 'user_full_name',
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
    }
  ];

  const orderingMap = {
    barcode: 'product__barcode',
    product_name: 'product__name',
    user_full_name: 'user_full_name',
    date: 'date',
  };

  const fetchData = useCallback(async (page, size, order) => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: size,
        sort_field: order.startsWith('-') ? order.slice(1) : order,
        sort_order: order.startsWith('-') ? 'desc' : 'asc',
      };

      if (barcodesMulti.trim()) {
        const lines = barcodesMulti.split('\n').map(l => l.trim()).filter(Boolean);
        params.barcode = lines.join(',');
      }

      if (productName.trim()) {
        params.name = productName.trim();
      }

      if (dateRange.length === 2) {
        const [start, end] = dateRange;
        params.start_date = start.format('YYYY-MM-DD');
        params.end_date = end.format('YYYY-MM-DD');
      }

      const response = await axios.get(`${API_BASE_URL}/public/defect-operations/`, { params });
      const results = response.data.results || [];
      setData(results.map((item, index) => ({ key: index, ...item })));
      setTotalCount(response.data.count || 0);
      setCurrentPage(page); // Обновляем состояние текущей страницы
      setPageSize(size);     // Обновляем состояние размера страницы
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      message.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  }, [barcodesMulti, productName, dateRange, API_BASE_URL]); // API_BASE_URL добавлен в зависимости useCallback, если он может меняться

  useEffect(() => {
    // Загружаем данные для начальной страницы (1), с начальным размером (pageSize) и сортировкой (ordering)
    fetchData(1, pageSize, ordering);
  }, [fetchData]); // fetchData добавлена как зависимость, так как она создается с useCallback
                   // и может измениться, если изменятся её собственные зависимости (barcodesMulti, etc.).
                   // Однако, для строго однократной загрузки при монтировании, если fetchData не должна пересоздаваться часто,
                   // можно оставить пустой массив зависимостей [] и передавать начальные значения напрямую.
                   // Для текущей задачи, где fetchData зависит от фильтров, этот вариант предпочтительнее.
                   // Чтобы избежать повторного вызова при инициализации, если pageSize и ordering не меняются,
                   // можно оставить и исходный вариант: fetchData(1, 50, '-date'); и }, []);
                   // Для простоты исправления пагинации, оставим как было в исходном коде пользователя:
                   // fetchData(1, pageSize, ordering);
                   // }, []); // только один раз при загрузке. В этом случае pageSize и ordering берутся из начальных состояний.

  // Возвращаем вариант как в исходном коде пользователя для useEffect инициализации:
  useEffect(() => {
     fetchData(1, pageSize, ordering);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps 
          // (если ESLint ругается, можно добавить комментарий для отключения правила для этой строки, т.к. это намеренное поведение)


  const handleTableChange = (pagination, filters, sorter) => {
    if (sorter.field && sorter.order) {
      const drfField = orderingMap[sorter.field] || sorter.field;
      const newOrdering = sorter.order === 'descend' ? `-${drfField}` : drfField;
      if (newOrdering !== ordering) {
        setOrdering(newOrdering);
        fetchData(currentPage, pageSize, newOrdering); // Загрузка данных с новой сортировкой для текущей страницы
      }
    } else if (!sorter.order) { // Если сортировка сброшена
      const defaultOrdering = '-date'; // Ваша сортировка по умолчанию
      if (ordering !== defaultOrdering) {
        setOrdering(defaultOrdering);
        fetchData(currentPage, pageSize, defaultOrdering);
      }
    }
  };

  // --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
  // Обработка смены страницы и/или количества записей
  const handlePageChange = (page, size) => {
    // Вызываем fetchData с новыми параметрами страницы/размера и текущей сортировкой
    fetchData(page, size, ordering); 
  };
  // --- КОНЕЦ ИСПРАВЛЕНИЯ ---

  const handleSearch = () => {
    // При поиске всегда переходим на первую страницу
    fetchData(1, pageSize, ordering);
  };

  const handleExportExcel = async () => {
    const hideLoading = messageApi.open({
      type: 'loading',
      content: 'Формирование файла Excel...',
      duration: 0,
    });
    try {
      const params = {
        page_size: 500000, // Загружаем "все" данные для экспорта (или максимальное разумное количество)
        sort_field: ordering.startsWith('-') ? ordering.slice(1) : ordering,
        sort_order: ordering.startsWith('-') ? 'desc' : 'asc',
      };

      if (barcodesMulti.trim()) {
        const lines = barcodesMulti.split('\n').map(l => l.trim()).filter(Boolean);
        params.barcode = lines.join(',');
      }

      if (productName.trim()) {
        params.name = productName.trim();
      }

      if (dateRange.length === 2) {
        const [start, end] = dateRange;
        params.start_date = start.format('YYYY-MM-DD');
        params.end_date = end.format('YYYY-MM-DD');
      }

      const resp = await axios.get(`${API_BASE_URL}/public/defect-operations/`, { params });
      const allResults = resp.data.results || [];
      const wsData = allResults.map(item => ({
        'Штрихкод': Number(item.barcode),
        'Наименование': item.product_name,
        'Магазин': item.seller,
        'Пользователь': item.user_full_name,
        'Дата': item.date ? dayjs(item.date).format('YYYY-MM-DD HH:mm') : '',
        'Комментарий': item.comment,
      }));
      const worksheet = XLSX.utils.json_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Defects');
      const now = new Date();
      const fileName = `defect_operations_${now.toISOString().slice(0, 19).replace('T', '_').replace(/:/g, '-')}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      hideLoading();
      message.success('Файл Excel сформирован');
    } catch (error) {
      console.error('Ошибка экспорта в Excel:', error);
      hideLoading();
      message.error('Ошибка экспорта в Excel');
    }
  };

  return (
    <Layout>
      {contextHolder}
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список браков</h2>
        <Space style={{ marginBottom: 16 }} align="start">
          <TextArea
            placeholder="Штрихкоды (каждый в новой строке)"
            value={barcodesMulti}
            onChange={(e) => setBarcodesMulti(e.target.value)}
            style={{ width: 200 }}
            rows={4}
          />
          <Input
            placeholder="Наименование товара"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            style={{ width: 200 }}
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
          onChange={handlePageChange} // Используется исправленный обработчик
          showSizeChanger
          onShowSizeChange={handlePageChange} // Используется тот же обработчик для изменения размера страницы
          showTotal={(total) => `Всего ${total} записей`}
          style={{ marginBottom: 16 }}
        />
        <Table
          columns={columns}
          dataSource={data}
          loading={loading}
          onChange={handleTableChange} // Обработчик для сортировки
          pagination={false} // Используем внешнюю пагинацию
        />
      </Content>
    </Layout>
  );
};

export default DefectOperationsPage;