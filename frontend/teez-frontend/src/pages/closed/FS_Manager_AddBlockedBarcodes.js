import React, { useState } from 'react';
import { Input, Button, message } from 'antd';
import axios from 'axios';

const { TextArea } = Input;

const getAuthHeaders = () => {
  const token = localStorage.getItem('accessToken');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const API_URL = 'http://192.168.6.17:8000/';

const AddBlockedBarcodes = () => {
  const [barcodesText, setBarcodesText] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    // Разбиваем текст на строки, удаляем лишние пробелы и пустые строки
    const barcodesArray = barcodesText
      .split('\n')
      .map(b => b.trim())
      .filter(Boolean);

    if (!barcodesArray.length) {
      message.error("Введите хотя бы один штрихкод");
      return;
    }

    // Проверка: каждый штрихкод должен быть ровно 13 цифр
    const invalidBarcodes = barcodesArray.filter(b => !/^\d{13}$/.test(b));
    if (invalidBarcodes.length > 0) {
      message.error("Каждый штрихкод должен состоять из 13 цифр");
      return;
    }

    setLoading(true);
    try {
      // Отправляем массив штрихкодов на сервер
      const response = await axios.post(
        `${API_URL}blocked-barcodes/add/`,
        { barcodes: barcodesArray },
        { headers: getAuthHeaders() }
      );
      message.success(response.data.message || "Штрихкоды добавлены");
      // Очищаем поле после успешного запроса
      setBarcodesText('');
    } catch (error) {
      console.error("Ошибка добавления:", error);
      message.error("Ошибка добавления штрихкодов");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        marginLeft: 200, // Резервируем 200px слева для сайдбара
        marginTop: 20,   // Отступ сверху в 20px
        display: 'flex',
        justifyContent: 'center'
      }}
    >
      <div style={{ width: 400 }}>
        <h2>Добавление заблокированных штрихкодов</h2>
        <div style={{ marginBottom: 16 }}>
          <TextArea
            placeholder="Введите штрихкоды (каждый на новой строке)"
            value={barcodesText}
            onChange={(e) => setBarcodesText(e.target.value)}
            rows={6}
          />
        </div>
        <Button type="primary" onClick={handleSubmit} loading={loading}>
          Добавить штрихкоды
        </Button>
      </div>
    </div>
  );
};

export default AddBlockedBarcodes;
