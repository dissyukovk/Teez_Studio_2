import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Table, Button, Space, message, Modal, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import 'dayjs/locale/ru'; // Импорт русской локали для дат

import Sidebar from '../../components/Layout/Sidebar'; // Укажите правильный путь
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config'; // Укажите правильный путь

const { Content } = Layout;
const { Title } = Typography;

const RetoucherRequestsListPage = ({ darkMode, setDarkMode, statusId, pageTitle }) => {
  const navigate = useNavigate();
  const [token] = useState(localStorage.getItem('accessToken'));

  // Состояния
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 50,
    total: 0,
  });

  // Загрузка данных
  const fetchData = useCallback(async (page = pagination.current, size = pagination.pageSize) => {
    if (!token) return;
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/rt/requests/${statusId}/`, {
        params: { page, page_size: size },
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(response.data.results.map(item => ({ ...item, key: item.id })));
      setPagination(prev => ({ ...prev, total: response.data.count }));
    } catch (error) {
      message.error(`Ошибка загрузки заявок: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }, [token, statusId, pagination.current, pagination.pageSize]);

  useEffect(() => {
    document.title = pageTitle;
    if (!token) {
      Modal.error({
        title: 'Ошибка доступа',
        content: 'Токен авторизации не найден. Пожалуйста, выполните вход.',
        okText: 'Войти',
        onOk: () => navigate('/login'),
      });
    } else {
      fetchData();
    }
  }, [navigate, token, pageTitle, fetchData]);

  const handleTableChange = (newPagination) => {
    setPagination(newPagination);
    fetchData(newPagination.current, newPagination.pageSize);
  };

  const columns = [
    {
      title: 'Номер заявки',
      dataIndex: 'RequestNumber',
      key: 'RequestNumber',
      render: (text, record) => <a onClick={() => navigate(`/rt/RetoucherRequestDetailPage/${record.RequestNumber}/`)}>{text}</a>,
    },
    {
      title: 'Дата создания',
      dataIndex: 'creation_date',
      key: 'creation_date',
      render: (date) => dayjs(date).isValid() ? dayjs(date).format('DD.MM.YYYY HH:mm') : '-',
    },
    {
      title: 'Количество товаров',
      dataIndex: 'total_products',
      key: 'total_products',
      align: 'center',
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content style={{ padding: '24px', background: darkMode ? '#001529' : '#fff' }}>
          <Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>{pageTitle}</Title>
          <Table
            columns={columns}
            dataSource={data}
            loading={loading}
            pagination={{
              ...pagination,
              showSizeChanger: true,
              pageSizeOptions: ['10', '20', '50', '100'],
              showTotal: total => `Всего: ${total}`,
            }}
            onChange={handleTableChange}
            scroll={{ x: 800 }}
            bordered
          />
        </Content>
      </Layout>
    </Layout>
  );
};

export default RetoucherRequestsListPage;