import React, { useState, useEffect } from 'react';
import { Layout, Table, Input, Button, Space, Pagination, message } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { TextArea } = Input;

const GuestInvoiceList = ({ darkMode, setDarkMode }) => {
  // Состояния для поиска накладных
  const [invoiceNumbers, setInvoiceNumbers] = useState('');
  const [barcodesSearch, setBarcodesSearch] = useState('');
  const [invoiceData, setInvoiceData] = useState([]);
  const [loading, setLoading] = useState(false);

  // Состояния для пагинации
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  // Состояние сортировки, по умолчанию - по убыванию номера накладной
  const [ordering, setOrdering] = useState("-InvoiceNumber");

  // Функция загрузки данных с учетом пагинации, поиска и сортировки
  const fetchInvoiceData = async (page = 1, size = pageSize, orderingParam = ordering) => {
    setLoading(true);
    try {
      const params = { page, page_size: size, ordering: orderingParam };

      if (invoiceNumbers.trim()) {
        const lines = invoiceNumbers.split('\n').map(s => s.trim()).filter(Boolean);
        if (lines.length > 0) {
          params.invoice_numbers = lines.join(',');
        }
      }
      if (barcodesSearch.trim()) {
        const lines = barcodesSearch.split('\n').map(s => s.trim()).filter(Boolean);
        if (lines.length > 0) {
          params.barcodes = lines.join(',');
        }
      }
      const response = await axios.get(`${API_BASE_URL}/st/invoices/`, { params });
      setInvoiceData(response.data.results || []);
      setTotalCount(response.data.count || 0);
      setCurrentPage(page);
      setPageSize(size);
    } catch (error) {
      message.error('Ошибка загрузки накладных');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoiceData();
    document.title = 'Список накладных';
  }, []);

  const handleSearch = () => {
    fetchInvoiceData(1, pageSize, ordering);
  };

  const handleTableChange = (pagination, filters, sorter) => {
    let newOrdering = ordering;
    if (sorter && sorter.field) {
      newOrdering = sorter.order === 'ascend' ? sorter.field : `-${sorter.field}`;
    }
    setOrdering(newOrdering);
    fetchInvoiceData(pagination.current, pagination.pageSize, newOrdering);
  };

  const handlePageChange = (page, size) => {
    setCurrentPage(page);
    setPageSize(size);
    fetchInvoiceData(page, size, ordering);
  };

  const invoiceColumns = [
    {
      title: 'Номер',
      dataIndex: 'InvoiceNumber',
      key: 'InvoiceNumber',
      sorter: true,
      defaultSortOrder: 'descend',
      render: (text) => (
        <a href={`/stockman-invoice-detail/${text}/`} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      ),
    },
    { title: 'Дата', dataIndex: 'date', key: 'date', sorter: true },
    { title: 'Товаровед', dataIndex: 'creator', key: 'creator', sorter: true },
    { title: 'Количество товаров', dataIndex: 'product_count', key: 'product_count', sorter: true },
  ]; 

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список накладных</h2>
        <Space style={{ marginBottom: 16 }}>
          <Space direction="vertical">
            <div>Поиск по номерам накладных</div>
            <TextArea
              placeholder="Номера накладных (каждый с новой строки)"
              value={invoiceNumbers}
              onChange={(e) => setInvoiceNumbers(e.target.value)}
              rows={4}
              style={{ width: 200 }}
            />
          </Space>
          <Space direction="vertical">
            <div>Поиск по штрихкодам</div>
            <TextArea
              placeholder="Штрихкоды (каждый с новой строки)"
              value={barcodesSearch}
              onChange={(e) => setBarcodesSearch(e.target.value)}
              rows={4}
              style={{ width: 200 }}
            />
          </Space>
          <Button type="primary" onClick={handleSearch}>
            Поиск
          </Button>
        </Space>
        <div style={{ marginBottom: 16 }}>
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            total={totalCount}
            onChange={handlePageChange}
            showSizeChanger
            onShowSizeChange={handlePageChange}
            showTotal={(total) => `Всего ${total} записей`}
          />
        </div>
        <Table
          columns={invoiceColumns}
          dataSource={invoiceData}
          rowKey="InvoiceNumber"
          loading={loading}
          pagination={false}
          onChange={handleTableChange}
        />
      </Content>
    </Layout>
  );
};

export default GuestInvoiceList;
