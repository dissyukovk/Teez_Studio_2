import React, { useState } from 'react';
import { Layout, Input, Button, Row, Col, Typography, message, Space } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;

const BarcodeCheckPage = ({ darkMode, setDarkMode }) => {
  const [barcodesText, setBarcodesText] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);

  // Обновленные метки для всех возможных категорий ответа
  const categoryLabels = {
    has_photo: 'Есть фото',
    in_retouch_queue: 'В очереди на ретушь',
    nofoto: 'Без фото',
    blocked_by_shop: 'Блок (магазин)',
    blocked_by_category: 'Блок (категория)',
    blocked_by_barcode: 'Блок (SKU)',
    ordered: 'Заказано',
    onfs: 'На ФС',
    possible_zero_stock: 'Возможно нет остатков',
    missed: 'Не найдены',
  };

  const handleCheck = async () => {
    const barcodesArray = barcodesText
      .split('\n')
      .map(line => line.trim())
      .filter(line => line !== '');

    if (barcodesArray.length === 0) {
      message.error('Введите хотя бы один штрихкод');
      return;
    }

    setLoading(true);
    setResults(null); // Сбрасываем предыдущие результаты перед новым запросом
    try {
      const token = localStorage.getItem('accessToken');
      const response = await axios.post(
        `${API_BASE_URL}/mn/barcode-check/`, // Убедитесь, что URL правильный
        { barcodes: barcodesArray },
        { headers: { Authorization: `Bearer ${token}` } } // Добавлен заголовок авторизации
      );
      setResults(response.data);
    } catch (error) {
      message.error(error.response?.data?.error || 'Ошибка при проверке штрихкодов');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content
          style={{
            padding: 24,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <Title level={2}>Проверка штрихкодов</Title>
          <Text type="secondary" style={{ marginBottom: 16 }}>
            Вставьте штрихкоды, каждый на новой строке.
          </Text>

          <Space direction="vertical" style={{ width: '100%', maxWidth: 400 }}>
            <TextArea
              rows={10}
              placeholder="9182736450123..."
              value={barcodesText}
              onChange={e => setBarcodesText(e.target.value)}
            />
            <Button type="primary" onClick={handleCheck} loading={loading} block>
              Проверить
            </Button>
          </Space>

          {results && (
            <Row gutter={[16, 16]} style={{ width: '100%', marginTop: 32 }}>
              {/* Итерация по ключам из ответа API */}
              {Object.keys(results)
                // Фильтрация: показываем только те категории, где есть штрихкоды
                .filter(cat => results[cat] && results[cat].length > 0)
                .map(cat => (
                  <Col key={cat} xs={24} sm={12} md={8} lg={6} xl={4} style={{ flexGrow: 1 }}>
                    {/* Выводим заголовок с количеством */}
                    <Text strong>
                      {`${categoryLabels[cat] || cat} (${results[cat].length})`}
                    </Text>
                    <TextArea
                      rows={8}
                      value={results[cat].join('\n')}
                      readOnly
                      style={{ marginTop: 8, resize: 'none' }}
                    />
                  </Col>
                ))}
            </Row>
          )}
        </Content>
      </Layout>
    </Layout>
  );
};

export default BarcodeCheckPage;