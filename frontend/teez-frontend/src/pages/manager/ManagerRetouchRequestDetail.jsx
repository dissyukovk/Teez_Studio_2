import React, { useState, useEffect } from 'react';
import { Layout, Table, Descriptions, Typography, message, Spin, Button } from 'antd';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title } = Typography;

const ManagerRetouchRequestDetail = ({ darkMode, setDarkMode}) => {
  // Извлекаем номер заявки из параметров маршрута
  const { RequestNumber } = useParams();
  const [requestData, setRequestData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = `Детали заявки "${RequestNumber}"`;
  }, [RequestNumber]);

  useEffect(() => {
    const fetchRequestDetails = async () => {
      setLoading(true);
      try {
        const response = await axios.get(`${API_BASE_URL}/mn/RetouchRequestDetail/${RequestNumber}/`);
        setRequestData(response.data);
      } catch (error) {
        message.error('Ошибка загрузки деталей заявки');
      } finally {
        setLoading(false);
      }
    };

    fetchRequestDetails();
  }, [RequestNumber]);

  const columns = [
    {
      title: '№',
      key: 'index',
      render: (text, record, index) => index + 1, // Порядковая нумерация
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
      title: 'Категория',
      key: 'category',
      render: (_, record) => {
        const cat = record.category;
        return cat ? `${cat.id} - ${cat.name}` : '';
      },
    },
    {
      title: 'Ссылка на референс',
      dataIndex: 'reference_link',
      key: 'reference_link',
      render: (reference_link) =>
        reference_link ? (
          <Button type="primary" onClick={() => window.open(reference_link, '_blank')}>
            реф
          </Button>
        ) : (
          '-'
        ),
    },
    {
      title: 'ИНФО',
      dataIndex: 'info',
      key: 'info',
    },
    {
      title: 'Статус ретуши',
      dataIndex: 'retouch_status',
      key: 'retouch_status',
    },
    {
      title: 'Проверка',
      dataIndex: 'sretouch_status',
      key: 'sretouch_status',
    },
    {
      title: 'Комментарий',
      dataIndex: 'comment',
      key: 'comment',
    },
    {
      title: 'Приоритет',
      key: 'priority',
      render: (_, record) => (record.priority ? 'Да' : ''),
    },
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '16px' }}>
        {loading ? (
          <Spin size="large" />
        ) : requestData ? (
          <>
            <Title level={2}>Детали заявки "{requestData.request_number}"</Title>
            <Descriptions bordered column={2} size="small" style={{ marginBottom: '24px' }}>
              <Descriptions.Item label="Дата создания">
                {requestData.creation_date}
              </Descriptions.Item>
              <Descriptions.Item label="Ретушер">
                {requestData.retoucher || ''}
              </Descriptions.Item>
              <Descriptions.Item label="Дата ретуши">
                {requestData.retouch_date || ''}
              </Descriptions.Item>
              <Descriptions.Item label="Время ретуши">
                {requestData.retouch_time || ''}
              </Descriptions.Item>
              <Descriptions.Item label="Статус">
                {requestData.status || ''}
              </Descriptions.Item>
              <Descriptions.Item label="Количество товаров">
                {requestData.products_count}
              </Descriptions.Item>
              <Descriptions.Item label="Количество приоритетных">
                {requestData.priority_products_count}
              </Descriptions.Item>
            </Descriptions>
            <Table
              dataSource={requestData.products}
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

export default ManagerRetouchRequestDetail;
