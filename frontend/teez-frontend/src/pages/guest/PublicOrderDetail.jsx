import React, { useState, useEffect } from 'react';
import { Layout, Table, Descriptions, Typography, message, Spin, Button } from 'antd';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';
import * as XLSX from 'xlsx';

const { Content } = Layout;
const { Title } = Typography;

const PublicOrderDetailPage = ({ darkMode, setDarkMode }) => {
  const { order_number } = useParams();
  const [orderData, setOrderData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  useEffect(() => {
    document.title = `Детали заказа "${order_number}"`;
  }, [order_number]);

  useEffect(() => {
    const fetchOrderDetails = async () => {
      setLoading(true);
      try {
        const response = await axios.get(`${API_BASE_URL}/st/order-detail/${order_number}/`);
        setOrderData(response.data);
      } catch (error) {
        message.error('Ошибка загрузки деталей заказа');
      } finally {
        setLoading(false);
      }
    };

    fetchOrderDetails();
  }, [order_number]);

  // Экспорт в Excel без file-saver с нумерацией строк
  const handleExportExcel = async () => {
    if (!orderData) return;
    const hideLoading = message.loading('Формирование файла Excel...', 0);
    setExportLoading(true);
    try {
      // Формируем данные для листа:
      // 1. Первая строка - номер заказа.
      // 2. Пустая строка.
      // 3. Заголовки таблицы с нумерацией.
      // 4. Данные товаров с номером строки.
      const wsData = [];
      wsData.push([`Номер заказа: ${orderData.order_number}`]);
      wsData.push([]); // пустая строка
      wsData.push(['№', 'Штрихкод', 'Наименование', 'Ячейка']);
      orderData.products.forEach((product, index) => {
        wsData.push([index + 1, product.barcode, product.name, product.cell]);
      });
      
      const worksheet = XLSX.utils.aoa_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Order Details');
      const now = new Date();
      const fileName = `Order_${orderData.order_number}_${now.toISOString().slice(0, 19)}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      hideLoading();
      message.success('Excel-файл сформирован');
    } catch (error) {
      console.error(error);
      message.error('Ошибка экспорта Excel');
    } finally {
      setExportLoading(false);
    }
  };

  // Функция печати: открывается новое окно с таблицей, адаптированной для печати с нумерацией
  const handlePrint = () => {
    if (!orderData) return;
    const printWindow = window.open('', '_blank');
    const htmlContent = `
      <html>
      <head>
        <title>Печать - Заказ ${orderData.order_number}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h2 { text-align: center; }
          table { width: 100%; border-collapse: collapse; margin-top: 20px; }
          table, th, td { border: 1px solid #000; }
          th, td { padding: 9px; text-align: left; }
          @media print {
            @page { margin: 20mm; }
            body { margin: 0; }
          }
        </style>
      </head>
      <body>
        <h2>Номер заказа: ${orderData.order_number}</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Штрихкод</th>
              <th>Наименование</th>
              <th>Ячейка</th>
            </tr>
          </thead>
          <tbody>
            ${orderData.products.map((product, index) => `
              <tr>
                <td>${index + 1}</td>
                <td>${product.barcode}</td>
                <td>${product.name}</td>
                <td>${product.cell}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </body>
      </html>
    `;
    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  };

  // Определяем колонки таблицы (для основного отображения)
  const columns = [
    {
      title: '#',
      key: 'index',
      render: (text, record, index) => index + 1,
      width: 50,
    },
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode',
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Ячейка',
      dataIndex: 'cell',
      key: 'cell',
    },
    {
      title: 'Время приемки',
      dataIndex: 'accepted_date',
      key: 'accepted_date',
    },
    {
      title: 'Принят',
      dataIndex: 'accepted',
      key: 'accepted',
      render: (accepted) => (
        <span style={{ color: accepted ? 'green' : 'red' }}>
          {accepted ? 'Да' : 'Нет'}
        </span>
      ),
    },
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '16px' }}>
        {loading ? (
          <Spin size="large" />
        ) : orderData ? (
          <>
            <Title level={2}>Детали заказа "{orderData.order_number}"</Title>
            <Descriptions bordered column={2} size="small" style={{ marginBottom: '24px' }}>
              <Descriptions.Item label="Номер заказа">
                {orderData.order_number}
              </Descriptions.Item>
              <Descriptions.Item label="Статус">
                {orderData.order_status ? orderData.order_status.name : ''}
              </Descriptions.Item>
              <Descriptions.Item label="Заказчик">
                {orderData.creator}
              </Descriptions.Item>
              <Descriptions.Item label="Дата создания">
                {orderData.date}
              </Descriptions.Item>
              <Descriptions.Item label="Сотрудник сборки">
                {orderData.assembly_user}
              </Descriptions.Item>
              <Descriptions.Item label="Время сборки">
                {orderData.assembly_date}
              </Descriptions.Item>
              <Descriptions.Item label="Сотрудник приемки">
                {orderData.accept_user}
              </Descriptions.Item>
              <Descriptions.Item label="Время начала приемки">
                {orderData.accept_date}
              </Descriptions.Item>
              <Descriptions.Item label="Время окончания приемки">
                {orderData.accept_date_end}
              </Descriptions.Item>
              <Descriptions.Item label="Время приемки">
                {orderData.accept_time}
              </Descriptions.Item>
              <Descriptions.Item label="Общее количество товаров">
                {orderData.total_products}
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
              <Button type="primary" onClick={handleExportExcel} loading={exportLoading}>
                Скачать в Excel
              </Button>
              <Button onClick={handlePrint}>
                Печать
              </Button>
            </div>
            <Table
              dataSource={orderData.products}
              columns={columns}
              rowKey="barcode"
              pagination={false}
            />
          </>
        ) : (
          <div>Нет данных</div>
        )}
      </Content>
    </Layout>
  );
};

export default PublicOrderDetailPage;
