import React, { useState, useEffect } from 'react';
import { Layout, Input, Button, Modal, message, Typography, Checkbox } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title } = Typography;

const ManagerCreateOrder = ({ darkMode, setDarkMode }) => {
  const [barcodesText, setBarcodesText] = useState('');
  const [ordersModalVisible, setOrdersModalVisible] = useState(false);
  const [ordersRange, setOrdersRange] = useState('');
  const [priority, setPriority] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = 'Создание заказов';
  }, []);

  const handleCreateOrder = async () => {
    // Разбиваем текст на строки, обрезаем пробелы и отфильтровываем пустые строки
    const barcodesArray = barcodesText
      .split('\n')
      .map(line => line.trim())
      .filter(line => line !== '');
      
    // Проверка, что все штрихкоды состоят только из цифр
    const invalidBarcodes = barcodesArray.filter(bc => !/^\d+$/.test(bc));
    if (invalidBarcodes.length > 0) {
      message.error('Все штрихкоды должны состоять только из цифр');
      return;
    }
    
    if (barcodesArray.length === 0) {
      message.error('Введите хотя бы один штрихкод');
      return;
    }

    const token = localStorage.getItem('accessToken');

    try {
      setLoading(true);
      // Подготавливаем тело запроса для создания заказа
      const payload = { barcodes: barcodesArray };
      if (priority) {
        payload.priority = true;
      }

      const createResponse = await axios.post(
        `${API_BASE_URL}/mn/create-order-end/`,
        payload,
        { headers: { Authorization: token ? `Bearer ${token}` : '' } }
      );

      setOrdersRange(createResponse.data.orders_range);
      setOrdersModalVisible(true);
    } catch (error) {
      message.error(error.response?.data?.error || 'Ошибка при создании заказа');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content
        style={{
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh'
        }}
      >
        <Title level={2}>Создание заказа</Title>
        <Input.TextArea
          rows={15}
          placeholder="Вставьте штрихкоды, каждый на новой строке"
          value={barcodesText}
          onChange={(e) => setBarcodesText(e.target.value)}
          style={{ width: 400, marginBottom: 20 }}
        />
        <Checkbox
          checked={priority}
          onChange={(e) => setPriority(e.target.checked)}
          style={{ marginBottom: 20 }}
        >
          Приоритет
        </Checkbox>
        <Button type="primary" onClick={handleCreateOrder} loading={loading}>
          Создать заказ
        </Button>

        {/* Модальное окно для диапазона созданных заказов */}
        <Modal
          visible={ordersModalVisible}
          title="Созданные заказы"
          onOk={() => setOrdersModalVisible(false)}
          onCancel={() => setOrdersModalVisible(false)}
          className={darkMode ? 'dark-modal' : ''}
        >
          <p>{ordersRange}</p>
        </Modal>
      </Content>
    </Layout>
  );
};

export default ManagerCreateOrder;
