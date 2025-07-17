import React, { useState, useEffect } from 'react';
import { Layout, Input, Button, message, Typography, Modal } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title } = Typography;

const ManagerBulkUpdateInfo = ({ darkMode, setDarkMode }) => {
  const [barcodesText, setBarcodesText] = useState('');
  const [infoText, setInfoText] = useState('');
  const [loading, setLoading] = useState(false);
  const [missingModalVisible, setMissingModalVisible] = useState(false);
  const [missingBarcodes, setMissingBarcodes] = useState([]);

  useEffect(() => {
    document.title = 'Обновление информации товаров';
  }, []);

  const handleUpdateInfo = async () => {
    // Разбиваем текст со штрихкодами на строки, удаляем лишние пробелы и пустые строки
    const barcodesArray = barcodesText
      .split('\n')
      .map(line => line.trim())
      .filter(line => line !== '');
      
    if (barcodesArray.length === 0) {
      message.error('Введите хотя бы один штрихкод');
      return;
    }
    
    if (!infoText.trim()) {
      message.error('Поле "Инфо" обязательно для заполнения');
      return;
    }

    const token = localStorage.getItem('accessToken');
    setLoading(true);
    try {
      const response = await axios.post(
        `${API_BASE_URL}/products/update-info/`,
        {
          barcodes: barcodesArray,
          info: infoText,
        },
        { headers: { Authorization: token ? `Bearer ${token}` : '' } }
      );
      
      // Выводим сообщение об успехе
      message.success(response.data.message);
      
      // Если имеются отсутствующие штрихкоды, сохраняем их в состоянии и показываем модальное окно
      if (response.data.missing_barcodes && response.data.missing_barcodes.length > 0) {
        setMissingBarcodes(response.data.missing_barcodes);
        setMissingModalVisible(true);
      }
      
      // Очищаем поля после успешного запроса
      setBarcodesText('');
      setInfoText('');
    } catch (error) {
      message.error(error.response?.data?.error || 'Ошибка при обновлении информации');
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
          minHeight: '100vh',
        }}
      >
        <Title level={2}>Обновление информации товаров</Title>
        <Input.TextArea
          rows={10}
          placeholder="Вставьте штрихкоды, каждый на новой строке"
          value={barcodesText}
          onChange={(e) => setBarcodesText(e.target.value)}
          style={{ width: 400, marginBottom: 20 }}
        />
        <Input.TextArea
          rows={3}
          placeholder="Введите информацию для обновления"
          value={infoText}
          onChange={(e) => setInfoText(e.target.value)}
          style={{ width: 400, marginBottom: 20 }}
        />
        <Button type="primary" onClick={handleUpdateInfo} loading={loading}>
          Обновить информацию
        </Button>

        {/* Модальное окно для отсутствующих штрихкодов */}
        <Modal
          visible={missingModalVisible}
          title="Отсутствующие штрихкоды"
          onCancel={() => setMissingModalVisible(false)}
          footer={null}
          className={darkMode ? 'dark-modal' : ''}
        >
          <Input.TextArea
            value={missingBarcodes.join('\n')}
            readOnly
            autoSize={{ minRows: 3, maxRows: 6 }}
          />
        </Modal>
      </Content>
    </Layout>
  );
};

export default ManagerBulkUpdateInfo;
