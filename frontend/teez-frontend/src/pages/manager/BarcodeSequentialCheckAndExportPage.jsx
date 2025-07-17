import React, { useState, useEffect } from 'react';
import { Layout, Input, Button, Space, Typography, message } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import * as XLSX from 'xlsx';
import dayjs from 'dayjs';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;

const BarcodeSequentialCheckAndExportPage = ({ darkMode, setDarkMode }) => {
  useEffect(() => {
    document.title = 'Проверка и Экспорт ШК';
  }, []);

  const [barcodesText, setBarcodesText] = useState('');
  const [loading, setLoading] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();

  const handleGenerateExcel = async () => {
    const barcodesArray = barcodesText
      .split('\n')
      .map(line => line.trim())
      .filter(line => line !== '');

    if (barcodesArray.length === 0) {
      message.error('Введите хотя бы один штрихкод для проверки.');
      return;
    }

    setLoading(true);
    const hideLoadingMessage = messageApi.open({
      type: 'loading',
      content: 'Получение данных и формирование файла...',
      duration: 0,
    });

    try {
      // 1. Выполняем запрос на сервер
      const response = await axios.post(
        `${API_BASE_URL}/mn/barcode-check-sequential/`,
        { barcodes: barcodesArray }
      );
      
      const results = response.data;

      // 2. Формируем данные для Excel
      const wsData = results.map((item) => {
        const anyDate = item.date || item.photo_date || item.order_date || item.income_date;
        const formattedDate = anyDate ? dayjs(anyDate).format('YYYY-MM-DD HH:mm:ss') : '';

        return {
          'Штрихкод': Number(item.barcode) || 0, // ИЗМЕНЕНИЕ: Преобразуем штрихкод в число
          'Статус': item.barcode_status,
          'Дата': formattedDate,
          'Ссылка на фото': item.retouch_link || '',
        };
      });
      
      // 3. Создаем Excel лист
      const worksheet = XLSX.utils.json_to_sheet(wsData);
      
      // ИЗМЕНЕНИЕ: Проходим по всем ячейкам первой колонки и устанавливаем числовой формат
      const range = XLSX.utils.decode_range(worksheet['!ref']);
      // Начинаем с 1, чтобы пропустить заголовок (который находится в строке 0 по индексу)
      for (let i = range.s.r + 1; i <= range.e.r; i++) {
        // c:0 - это первая колонка (A)
        const cellRef = XLSX.utils.encode_cell({ r: i, c: 0 }); 
        if (worksheet[cellRef]) {
            worksheet[cellRef].t = 'n'; // Устанавливаем тип ячейки "число" (number)
            worksheet[cellRef].z = '0';  // Устанавливаем формат "0" (без десятичных знаков)
        }
      }

      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Статусы ШК');

      // Задаем ширину колонок для лучшего отображения
      worksheet['!cols'] = [
        { wch: 15 }, // A - Штрихкод
        { wch: 25 }, // B - Статус
        { wch: 20 }, // C - Дата
        { wch: 50 }, // D - Ссылка на фото
      ];

      const now = new Date();
      const fileName = `barcode_status_${now.toISOString().slice(0, 19).replace('T', '_').replace(/:/g, '-')}.xlsx`;
      
      XLSX.writeFile(workbook, fileName);

      message.success('Файл Excel успешно сформирован и скачан.');

    } catch (error) {
      const errorMessage = error.response?.data?.error || 'Произошла ошибка при запросе данных.';
      message.error(errorMessage);
      console.error('Error during API call or Excel generation:', error);
    } finally {
      hideLoadingMessage();
      setLoading(false);
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {contextHolder}
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content
          style={{
            padding: 24,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
          }}
        >
          <Title level={2}>Проверка и экспорт статусов ШК</Title>
          <Text type="secondary" style={{ marginBottom: 24, textAlign: 'center' }}>
            Вставьте штрихкоды (каждый на новой строке) для проверки и выгрузки в Excel.
          </Text>

          <Space direction="vertical" style={{ width: '100%', maxWidth: 200 }}>
            <TextArea
              rows={19}
              placeholder="9457393715234&#10;9457393715235&#10;..."
              value={barcodesText}
              onChange={(e) => setBarcodesText(e.target.value)}
            />
            <Button 
              type="primary" 
              onClick={handleGenerateExcel} 
              loading={loading}
              style={{ width: '100%' }}
            >
              Проверить и скачать Excel
            </Button>
          </Space>
        </Content>
      </Layout>
    </Layout>
  );
};

export default BarcodeSequentialCheckAndExportPage;