import React, { useState, useEffect } from 'react';
import { Layout, Input, Button, message, Typography } from 'antd';
import Sidebar from '../../components/Layout/Sidebar'; // Убедитесь, что путь к Sidebar верный
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config'; // Убедитесь, что путь к config верный

const { Content } = Layout;
const { Title } = Typography;

const RetouchBlockPage = ({ darkMode, setDarkMode }) => {
  const [barcodesText, setBarcodesText] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = 'Блокировка шк для рендеров';
  }, []);

  const handleBlockProducts = async () => {
    // Разбиваем текст на строки, обрезаем пробелы и отфильтровываем пустые строки
    const barcodesArray = barcodesText
      .split('\n')
      .map(line => line.trim())
      .filter(line => line !== '');

    // Проверка, что все штрихкоды состоят только из цифр и имеют корректную длину (опционально, но рекомендуется)
    // В вашем примере была проверка только на цифры, добавлю и ее.
    // Если у штрихкодов есть определенная длина, например 13, можно добавить:
    // const invalidBarcodes = barcodesArray.filter(bc => !/^\d{13}$/.test(bc));
    const invalidBarcodes = barcodesArray.filter(bc => !/^\d+$/.test(bc));
    if (invalidBarcodes.length > 0) {
      message.error(`Обнаружены некорректные штрихкоды: ${invalidBarcodes.join(', ')}. Все штрихкоды должны состоять только из цифр.`);
      return;
    }

    if (barcodesArray.length === 0) {
      message.error('Введите хотя бы один штрихкод');
      return;
    }

    const token = localStorage.getItem('accessToken');
    if (!token) {
      message.error('Ошибка аутентификации: токен не найден. Пожалуйста, войдите в систему.');
      // Здесь можно добавить логику для перенаправления на страницу входа
      return;
    }

    try {
      setLoading(true);
      const payload = { barcodes: barcodesArray };

      const response = await axios.post(
        `${API_BASE_URL}/rd/block-for-retouch/`, // Ваш эндпоинт
        payload,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      message.success(response.data.message || 'Продукты успешно заблокированы для ретуши.');
      setBarcodesText(''); // Очищаем поле ввода после успешной отправки
    } catch (error) {
      if (error.response) {
        // Ошибка от сервера (например, 4xx, 5xx)
        message.error(error.response.data.error || error.response.data.message || 'Ошибка при блокировке продуктов.');
      } else if (error.request) {
        // Запрос был сделан, но ответ не получен
        message.error('Ошибка сети: не удалось связаться с сервером.');
      } else {
        // Другая ошибка
        message.error('Произошла неизвестная ошибка.');
      }
      console.error("Ошибка при блокировке продуктов:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout className="site-layout">
        <Content
          style={{
            margin: '0 16px',
            padding: 24,
            minHeight: 'calc(100vh - 64px)', // 64px - примерная высота хедера, если он есть
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            // justifyContent: 'center', // Раскомментируйте, если нужно строго по центру по вертикали
          }}
        >
          <Title level={2} style={{ marginBottom: '24px' }}>
            Блокировка продуктов для ретуши
          </Title>
          <Input.TextArea
            rows={15}
            placeholder="Вставьте штрихкоды, каждый на новой строке"
            value={barcodesText}
            onChange={(e) => setBarcodesText(e.target.value)}
            style={{ width: '100%', maxWidth: 500, marginBottom: 20 }}
          />
          <Button
            type="primary"
            onClick={handleBlockProducts}
            loading={loading}
            style={{ minWidth: 200 }}
          >
            Заблокировать для ретуши
          </Button>
        </Content>
      </Layout>
    </Layout>
  );
};

export default RetouchBlockPage;