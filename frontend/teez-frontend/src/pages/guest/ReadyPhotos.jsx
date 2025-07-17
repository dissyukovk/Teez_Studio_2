import React, { useEffect, useState } from 'react';
import { Layout, Table, Input, Button, Space, DatePicker, Pagination, message, Typography } from 'antd';
import axios from 'axios';
import * as XLSX from 'xlsx';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;
const { RangePicker } = DatePicker;

const ReadyPhotos = ({ darkMode, setDarkMode }) => {
  // Устанавливаем заголовок вкладки
  useEffect(() => {
    document.title = 'Готовое фото 1.0';
  }, []);

  // Состояния для данных и фильтров
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  // Фильтры: штрихкоды, ID магазина и диапазон дат
  const [barcodesMulti, setBarcodesMulti] = useState('');
  const [sellersMulti, setSellersMulti] = useState('');
  const [dateRange, setDateRange] = useState([null, null]);

  // Состояния для сортировки (если нужно)
  const [sortField, setSortField] = useState('barcode');
  const [sortOrder, setSortOrder] = useState('asc');

  // Пагинация
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  // Список не найденных штрихкодов (возвращается с бэка)
  const [notFound, setNotFound] = useState([]);

  // Функция загрузки данных с бэка
  const fetchData = async (page = 1, size = 50) => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: size,
        sort_field: sortField,
        sort_order: sortOrder,
      };

      // Если штрихкоды введены, объединяем строки через запятую
      if (barcodesMulti.trim()) {
        const lines = barcodesMulti.split('\n').map(line => line.trim()).filter(Boolean);
        params.barcode = lines.join(',');
      }

      // Если ID магазина введены
      if (sellersMulti.trim()) {
        const lines = sellersMulti.split('\n').map(line => line.trim()).filter(Boolean);
        params.seller_id = lines.join(',');
      }

      // Если выбран диапазон дат, передаем date_from и date_to в формате YYYY-MM-DD
      if (dateRange[0] && dateRange[1]) {
        params.date_from = dateRange[0].format('YYYY-MM-DD');
        params.date_to = dateRange[1].format('YYYY-MM-DD');
      }

      const response = await axios.get(`${API_BASE_URL}/public/ready-photos/`, { params });
      const results = response.data.results || [];
      setData(results);
      setTotalCount(response.data.count || 0);
      setNotFound(response.data.not_found || []);
      setCurrentPage(page);
      setPageSize(size);
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      message.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  // Первичная загрузка
  useEffect(() => {
    fetchData(currentPage, pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Обработчик кнопки "Поиск"
  const handleSearch = () => {
    fetchData(1, pageSize);
  };

  // Экспорт в Excel
  const handleExportExcel = async () => {
    const hideLoading = message.loading('Формирование файла Excel...', 0);
    try {
      const params = {
        page_size: 500000, // Получаем все данные без пагинации
        sort_field: sortField,
        sort_order: sortOrder,
      };

      if (barcodesMulti.trim()) {
        const lines = barcodesMulti.split('\n').map(line => line.trim()).filter(Boolean);
        params.barcode = lines.join(',');
      }
      if (sellersMulti.trim()) {
        const lines = sellersMulti.split('\n').map(line => line.trim()).filter(Boolean);
        params.seller_id = lines.join(',');
      }
      if (dateRange[0] && dateRange[1]) {
        params.date_from = dateRange[0].format('YYYY-MM-DD');
        params.date_to = dateRange[1].format('YYYY-MM-DD');
      }

      const resp = await axios.get(`${API_BASE_URL}/public/ready-photos/`, { params });
      const allResults = resp.data.results || [];
      const formattedData = allResults.map(item => ({
        'Штрихкод': Number(item.barcode),
        'Наименование': item.name,
        'ID магазина': item.seller_id,
        'Ссылка на фото': item.retouch_link,
      }));
      const worksheet = XLSX.utils.json_to_sheet(formattedData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'ReadyPhotos');
      const now = new Date();
      const fileName = `readyphotos_1.0_${now.toISOString().slice(0, 19).replace(/:/g, '-')}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      hideLoading();
      message.success('Excel-файл сформирован');
    } catch (error) {
      console.error('Ошибка экспорта в Excel:', error);
      message.error('Ошибка экспорта в Excel');
    }
  };

  // Обработчик пагинации
  const handlePageChange = (page, size) => {
    fetchData(page, size);
  };

  // Ограничиваем ввод для штрихкодов: разрешаем только цифры и переводы строки
  const handleBarcodesChange = (e) => {
    const val = e.target.value;
    const filtered = val.replace(/[^\d\n]/g, '');
    setBarcodesMulti(filtered);
  };

  // Ограничиваем ввод для ID магазина
  const handleSellersChange = (e) => {
    const val = e.target.value;
    const filtered = val.replace(/[^\d\n]/g, '');
    setSellersMulti(filtered);
  };

  // Определяем колонки таблицы
  const columns = [
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode',
      width: 150,
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
      width: 300,
    },
    {
      title: 'ID магазина',
      dataIndex: 'seller_id',
      key: 'seller_id',
      width: 120,
    },
    {
      title: 'Ссылка на фото',
      dataIndex: 'retouch_link',
      key: 'retouch_link',
      render: (text) =>
        text ? (
          <a href={text} target="_blank" rel="noopener noreferrer">
            {text}
          </a>
        ) : (
          '-'
        ),
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* Сайдбар */}
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content style={{ margin: '24px', padding: '24px' }}>
          <Title level={2}>Готовое фото 1.0</Title>
          {/* Верхняя панель с фильтрами */}
          <div
            style={{
              marginBottom: 16,
              display: 'flex',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
            }}
          >
            <Space align="center" wrap>
              <div>
                <Text>Поиск по штрихкоду:</Text>
                <TextArea
                  rows={4}
                  style={{ width: 200 }}
                  value={barcodesMulti}
                  onChange={handleBarcodesChange}
                  placeholder="Введите штрихкоды (каждый на новой строке)"
                />
              </div>
              <div>
                <Text>Поиск по ID магазина:</Text>
                <TextArea
                  rows={4}
                  style={{ width: 200 }}
                  value={sellersMulti}
                  onChange={handleSellersChange}
                  placeholder="Введите ID магазина (каждый на новой строке)"
                />
              </div>
              <div>
                <Text>Дата съёмки:</Text>
                <RangePicker
                  format="YYYY-MM-DD"
                  value={dateRange}
                  onChange={(val) => setDateRange(val)}
                  style={{ width: 220 }}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Button type="primary" onClick={handleSearch} style={{ marginBottom: 8 }}>
                  Поиск
                </Button>
                <Button onClick={handleExportExcel}>
                  Скачать Excel
                </Button>
              </div>
            </Space>
            <div>
              <Title level={4}>Не найденные штрихкоды</Title>
              <TextArea
                readOnly
                rows={4}
                value={notFound.join('\n')}
                style={{ width: 200 }}
                placeholder="Нет"
              />
            </div>
          </div>
          {/* Пагинация сверху */}
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
          {/* Таблица */}
          <Table
            rowKey={(record, index) => `${record.barcode}_${index}`}
            columns={columns}
            dataSource={data}
            loading={loading}
            pagination={false}
            scroll={{ x: 800 }}
          />
        </Content>
      </Layout>
    </Layout>
  );
};

export default ReadyPhotos;
