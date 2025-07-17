import React, { useState, useEffect } from 'react';
import { Layout, Table, Descriptions, Typography, Spin, Button, Space, message } from 'antd';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';
import * as XLSX from 'xlsx';

const { Content } = Layout;
const { Title } = Typography;

const GuestInvoiceDetail = ({ darkMode, setDarkMode }) => {
  const { invoceNumber } = useParams();
  const [invoiceData, setInvoiceData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  useEffect(() => {
    document.title = `Детали накладной № ${invoceNumber}`;
  }, [invoceNumber]);

  const fetchInvoiceDetail = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/st/invoice-detail/${invoceNumber}/`);
      setInvoiceData(response.data);
    } catch (error) {
      message.error('Ошибка загрузки деталей накладной');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoiceDetail();
  }, [invoceNumber]);

  const handlePrint = () => {
    if (!invoiceData) return;
    const printWindow = window.open('', '_blank');
    const htmlContent = `
      <html>
      <head>
        <title>Накладная № ${invoiceData.InvoiceNumber}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h2 { text-align: center; }
          table { width: 100%; border-collapse: collapse; margin-top: 20px; }
          table, th, td { border: 1px solid #000; }
          th, td { padding: 8px; text-align: left; }
          .signature { margin-top: 30px; }
          .signature div { margin-bottom: 10px; }
          @media print {
            @page { margin: 20mm; }
            body { margin: 3mm; }
          }
        </style>
      </head>
      <body>
        <h2>Накладная № ${invoiceData.InvoiceNumber}</h2>
        <p><strong>Дата:</strong> ${invoiceData.date}</p>
        <p><strong>Товаровед:</strong> ${invoiceData.creator}</p>
        <table>
          <thead>
            <tr>
              <th>Штрихкод</th>
              <th>Наименование</th>
              <th>Заявки</th>
            </tr>
          </thead>
          <tbody>
            ${invoiceData.products.map(product => `
              <tr>
                <td>${product.barcode}</td>
                <td>${product.name}</td>
                <td>${product.st_requests.join(', ')}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <div class="signature">
          <div>
            <p>
            <strong>Отправил:</strong> ${invoiceData.creator} _____________________ 
            &nbsp;&nbsp;&nbsp;<strong>Дата отправки:</strong> ${invoiceData.date}
          </div>
          <div>
            <p>
            <strong>Получил:</strong> _____________________
          </div>
        </div>
      </body>
      </html>
    `;
    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  };

  const handleExportExcel = () => {
    if (!invoiceData) return;
    setExportLoading(true);
    try {
      const wsData = [];
      wsData.push([`Накладная № ${invoiceData.InvoiceNumber}`]);
      wsData.push([`Дата: ${invoiceData.date}`]);
      wsData.push([`Товаровед: ${invoiceData.creator}`]);
      wsData.push([]); // пустая строка
      wsData.push(['Штрихкод', 'Наименование', 'Заявки']);
      invoiceData.products.forEach(product => {
        wsData.push([
          product.barcode,
          product.name,
          product.st_requests.join(', ')
        ]);
      });
      const worksheet = XLSX.utils.aoa_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Накладная');
      const now = new Date();
      const fileName = `Накладная_${invoiceData.InvoiceNumber}_${now.toISOString().slice(0,19)}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      message.success('Excel-файл сформирован');
    } catch (error) {
      console.error(error);
      message.error('Ошибка экспорта Excel');
    } finally {
      setExportLoading(false);
    }
  };

  const columns = [
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode'
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name'
    },
    {
      title: 'Заявки',
      dataIndex: 'st_requests',
      key: 'st_requests',
      render: (st_requests) => st_requests.join(', ')
    }
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '16px' }}>
        {loading ? (
          <Spin size="large" />
        ) : invoiceData ? (
          <>
            <Title level={2}>Детали накладной № {invoiceData.InvoiceNumber}</Title>
            <Descriptions bordered column={2} size="small" style={{ marginBottom: '16px' }}>
              <Descriptions.Item label="Дата">{invoiceData.date}</Descriptions.Item>
              <Descriptions.Item label="Товаровед">{invoiceData.creator}</Descriptions.Item>
            </Descriptions>
            <Space style={{ marginBottom: '16px' }}>
              <Button type="primary" onClick={handlePrint}>Печать</Button>
              <Button onClick={handleExportExcel} loading={exportLoading}>Скачать Excel</Button>
            </Space>
            <Table
              columns={columns}
              dataSource={invoiceData.products}
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

export default GuestInvoiceDetail;
