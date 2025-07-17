// src/pages/guest/ReadyPhotos2.jsx
import React, { useEffect, useState } from 'react';
import { Layout, Space, Typography, Button, message, DatePicker, Input, Pagination, Table } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import * as XLSX from 'xlsx';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title } = Typography;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

const ReadyPhotos2 = ({ darkMode, setDarkMode }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  // Фильтры
  const [barcodesMulti, setBarcodesMulti] = useState('');
  const [sellersMulti, setSellersMulti] = useState('');
  const [dateRange, setDateRange] = useState([null, null]);

  // Пагинация
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  // Не найденные штрихкоды
  const [notFound, setNotFound] = useState([]);

  useEffect(() => {
    document.title = 'Готовые фото 2.0';
    fetchData(currentPage, pageSize);
    // eslint-disable-next-line
  }, []);

  const fetchData = async (page = 1, size = 50) => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: size,
      };

      // Штрихкоды
      if (barcodesMulti.trim()) {
        const lines = barcodesMulti
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean);
        params.barcodes = lines.join(',');
      }

      // Магазины
      if (sellersMulti.trim()) {
        const lines = sellersMulti
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean);
        params.seller = lines.join(',');
      }

      // Даты
      if (dateRange[0] && dateRange[1]) {
        params.date_from = dateRange[0].format('DD.MM.YYYY');
        params.date_to = dateRange[1].format('DD.MM.YYYY');
      }

      const resp = await axios.get(`${API_BASE_URL}/ft/ready-photos/`, { params });
      const results = resp.data.results || resp.data || [];
      setData(results);
      setTotalCount(resp.data.count || 0);
      setNotFound(resp.data.not_found || []);
      setCurrentPage(page);
      setPageSize(size);
    } catch (error) {
      console.error(error);
      message.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  // Поиск
  const handleSearch = () => {
    fetchData(1, pageSize);
  };

  // Скачивание Excel
  const handleExportExcel = async () => {
    const hideLoading = message.loading('Формирование файла Excel...', 0);
    try {
      const params = {
        page_size: 999999,
      };

      if (barcodesMulti.trim()) {
        const lines = barcodesMulti
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean);
        params.barcodes = lines.join(',');
      }
      if (sellersMulti.trim()) {
        const lines = sellersMulti
          .split('\n')
          .map((l) => l.trim())
          .filter(Boolean);
        params.seller = lines.join(',');
      }
      if (dateRange[0] && dateRange[1]) {
        params.date_from = dateRange[0].format('DD.MM.YYYY');
        params.date_to = dateRange[1].format('DD.MM.YYYY');
      }

      const resp = await axios.get(`${API_BASE_URL}/ft/ready-photos/`, { params });
      const allData = resp.data.results || resp.data || [];

      // Формируем лист
      const wsData = allData.map((item) => ({
        'Штрихкод': Number(item.barcode),
        Наименование: item.product_name,
        'ID магазина': item.seller,
        'Дата съёмки': item.photo_date,
        'Ссылка на фото': item.retouch_link,
      }));

      const worksheet = XLSX.utils.json_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Готовые фото 2.0');
      const now = new Date();
      const fileName = `gotovye_foto_2_0_${now.toISOString().slice(0, 19)}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      hideLoading();
      message.success('Excel-файл сформирован');
    } catch (error) {
      console.error(error);
      message.error('Ошибка экспорта Excel');
    }
  };

  // Пагинация
  const handlePageChange = (page, size) => {
    fetchData(page, size);
  };

  // Колонки
  const columns = [
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode',
      width: 150,
    },
    {
      title: 'Наименование',
      dataIndex: 'product_name',
      key: 'product_name',
      width: 600,
    },
    {
      title: 'ID магазина',
      dataIndex: 'seller',
      key: 'seller',
      width: 120,
    },
    {
      title: 'Дата съёмки',
      dataIndex: 'photo_date',
      key: 'photo_date',
      width: 120,
    },
    {
      title: 'Ссылка на фото',
      dataIndex: 'retouch_link',
      key: 'retouch_link',
      render: (text) => text ? (
        <a href={text} target="_blank" rel="noopener noreferrer">{text}</a>
      ) : '-',
    },
  ];

  // Только цифры и переносы строк
  const handleBarcodesChange = (e) => {
    const val = e.target.value;
    const filtered = val.replace(/[^\d\n]/g, '');
    setBarcodesMulti(filtered);
  };
  const handleSellersChange = (e) => {
    const val = e.target.value;
    const filtered = val.replace(/[^\d\n]/g, '');
    setSellersMulti(filtered);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content style={{ padding: 16 }}>
          <Title level={2}>Готовые фото 2.0</Title>
          {/* Верхняя панель */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            marginBottom: 16
          }}>
            {/* Левая часть */}
            <Space align="center" wrap>
              <div>
                <p>Штрихкоды (каждый с новой строки):</p>
                <TextArea
                  rows={3}
                  style={{ width: 200 }}
                  value={barcodesMulti}
                  onChange={handleBarcodesChange}
                  placeholder="Только цифры"
                />
              </div>
              <div>
                <p>ID магазинов (каждый с новой строки):</p>
                <TextArea
                  rows={3}
                  style={{ width: 200 }}
                  value={sellersMulti}
                  onChange={handleSellersChange}
                  placeholder="Только цифры"
                />
              </div>
              <div>
                <p>Дата съёмки:</p>
                <RangePicker
                  format="DD.MM.YYYY"
                  value={dateRange}
                  onChange={(val) => setDateRange(val)}
                />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Button type="primary" onClick={handleSearch} style={{ marginBottom: 8 }}>
                  Поиск
                </Button>
                <Button onClick={handleExportExcel}>
                  Скачать в Excel
                </Button>
              </div>
            </Space>

            {/* Правая часть: не найденные */}
            <div>
              <h4>Не найденные штрихкоды</h4>
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

export default ReadyPhotos2;
