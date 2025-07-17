import React, { useState, useEffect } from 'react';
import { Layout, Table, Descriptions, Typography, message, Spin, Button } from 'antd';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title } = Typography;

const ManagerSTRequestDetail = ({ darkMode, setDarkMode }) => {
  // Параметр из маршрута: /mn/strequest-detail/:requestnumber
  const { requestnumber } = useParams();

  const [requestData, setRequestData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = `Детали заявки "${requestnumber}"`;
  }, [requestnumber]);

  // Загружаем данные детали заявки
  useEffect(() => {
    const fetchRequestDetails = async () => {
      setLoading(true);
      try {
        const response = await axios.get(`${API_BASE_URL}/mn/strequest-detail/${requestnumber}/`);
        setRequestData(response.data);
      } catch (error) {
        message.error('Ошибка загрузки деталей заявки');
      } finally {
        setLoading(false);
      }
    };

    fetchRequestDetails();
  }, [requestnumber]);

  // Определяем колонки для таблицы товаров
  const columns = [
    {
      title: '№',
      key: 'index',
      render: (text, record, index) => index + 1, // Нумерация на фронте
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
        if (!cat) return '';
        return `${cat.id} - ${cat.name}`;
      },
    },
    {
      title: 'РЕФ',
      dataIndex: 'reference_link',
      key: 'reference_link',
      render: (reference_link) =>
        reference_link ? (
          <Button type="primary" onClick={() => window.open(reference_link, '_blank')}>
            Реф
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
      title: 'Пррт',
      key: 'priority',
      render: (_, record) => (record.priority ? 'Да' : ''),
    },
    {
      title: 'Статус',
      dataIndex: 'photo_status',
      key: 'photo_status',
    },
    {
      title: 'Проверка',
      dataIndex: 'sphoto_status',
      key: 'sphoto_status',
    },
    {
      title: 'Ссылка на фото',
      dataIndex: 'photos_link',
      key: 'photos_link',
      render: (photos_link) =>
        photos_link ? (
          <a href={photos_link} target="_blank" rel="noopener noreferrer">
            {photos_link}
          </a>
        ) : (
          '-'
        ),
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
              <Descriptions.Item label="Товаровед">
                {requestData.stockman || ''}
              </Descriptions.Item>
              <Descriptions.Item label="Дата съемки">
                {requestData.photo_date || ''}
              </Descriptions.Item>
              <Descriptions.Item label="Фотограф">
                {requestData.photographer || ''}
              </Descriptions.Item>
              <Descriptions.Item label="Статус">
                {requestData.status || ''}
              </Descriptions.Item>
              <Descriptions.Item label="Количество товаров">
                {requestData.total_products}
              </Descriptions.Item>
              <Descriptions.Item label="Количество приоритетных">
                {requestData.count_priority}
              </Descriptions.Item>
              <Descriptions.Item label="Количество отснятых">
                {requestData.count_photo}
              </Descriptions.Item>
              <Descriptions.Item label="Количество проверенных">
                {requestData.count_checked}
              </Descriptions.Item>
              <Descriptions.Item label="Количество ИНФО">
                {requestData.count_info}
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

export default ManagerSTRequestDetail;
