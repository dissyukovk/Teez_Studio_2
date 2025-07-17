import React, { useState, useEffect } from 'react';
import {
  Layout,
  Table,
  Descriptions,
  Typography,
  message,
  Spin,
  Button,
  Space
} from 'antd';
import { useParams } from 'react-router-dom';
import axiosInstance from '../../utils/axiosInstance';
import Sidebar from '../../components/Layout/Sidebar';
import * as XLSX from 'xlsx';
import { API_BASE_URL } from '../../utils/config';
import fsCellImage from '../../assets/fs_cell.jpg';

const { Content } = Layout;
const { Title } = Typography;

const OkzOrderDetail = ({ darkMode, setDarkMode }) => {
  const { order_number } = useParams();

  const [orderData, setOrderData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  useEffect(() => {
    document.title = `Детали заказа "${order_number}"`;
  }, [order_number]);

  const fetchOrderDetails = async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get(`/okz/order-detail/${order_number}/`);
      setOrderData(response.data);
    } catch (error) {
      message.error('Ошибка загрузки деталей заказа');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrderDetails();
  }, [order_number]);

  const handleStartAssembly = async () => {
    try {
      await axiosInstance.post(`/okz/order-start-assembly/${order_number}/`);
      message.success('Сборка начата успешно.');
      await fetchOrderDetails();
    } catch (error) {
      message.error('Ошибка при старте сборки');
    }
  };

  const handleExportExcel = async () => {
    if (!orderData) return;
    const hideLoading = message.loading('Формирование файла Excel...', 0);
    setExportLoading(true);
    try {
      const wsData = [];
      wsData.push([`Номер заказа: ${orderData.order_number}`]);
      wsData.push([]);
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

  const handlePrint = () => {
    if (!orderData) return;
    const printWindow = window.open('', '_blank');
  
    const htmlContent = `
      <html>
      <head>
        <title>Печать - Заказ ${orderData.order_number}</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            margin: 20px;
          }
          /* Контейнер для шапки с текстом и картинкой */
          .header-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
          }
          /* Адаптивный размер картинки */
          .header-container img {
            max-width: 200px; /* при необходимости меняйте это значение */
            height: auto;
          }
          table {
            width: 99%;
            border-collapse: collapse;
            margin-top: 20px;
          }
          table, th, td {
            border: 1px solid #000;
          }
          th, td {
            padding: 9px;
            text-align: left;
          }
          @media print {
            @page {
              margin: 20mm;
            }
            body {
              margin: 0;
            }
          }
        </style>
      </head>
      <body>
        <div class="header-container">
          <span>Заказ № ${orderData.order_number}</span>
          <img src="${fsCellImage}" alt="fs_cell" />
        </div>
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
            ${orderData.products
              .map(
                (product, index) => `
                  <tr>
                    <td>${index + 1}</td>
                    <td>${product.barcode}</td>
                    <td>${product.name}</td>
                    <td>${product.cell}</td>
                  </tr>
                `
              )
              .join('')}
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
  ];

  return (
    <Layout style={{ minHeight: '100vh', background: darkMode ? '#1f1f1f' : '#fff' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '16px' }}>
        {loading ? (
          <Spin size="large" />
        ) : orderData ? (
          <>
            <Title level={2}>Детали заказа "{orderData.order_number}"</Title>
            <div>
                <p><h3>Инструкция:</h3></p>
                <p><h3>Кнопка "начать сбор" убрана. Теперь при печати или скачивании в Excel автоматически начинает сбор и выставляется время</h3></p>
              </div>
            <Descriptions
              bordered
              size="small"
              style={{ marginBottom: '24px' }}
              column={{ xs: 1, sm: 2, md: 2 }}
            >
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
              <Descriptions.Item label="Общее количество товаров">
                {orderData.total_products}
              </Descriptions.Item>
            </Descriptions>

            {/* Кнопки действий */}
            <Space wrap style={{ marginBottom: 16 }}>
              <Button
                type="primary"
                onClick={() => {
                  handleStartAssembly();
                  handleExportExcel();
                }}
                loading={exportLoading}
              >
                Скачать в Excel
              </Button>
              <Button
                onClick={() => {
                  handleStartAssembly();
                  handlePrint();
                }}
              >
                Печать
              </Button>
            </Space>
            <Table
              dataSource={orderData.products}
              columns={columns}
              rowKey="barcode"
              pagination={false}
              // Горизонтальная прокрутка для узких экранов
              scroll={{ x: 'max-content' }}
            />
          </>
        ) : (
          <div>Нет данных</div>
        )}
      </Content>
    </Layout>
  );
};

export default OkzOrderDetail;
