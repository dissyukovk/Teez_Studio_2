import React, { useState, useRef } from 'react';
import { Layout, Button, Modal, message, Typography } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';
import * as XLSX from 'xlsx';

const { Content } = Layout;
const { Title } = Typography;

const ManagerBulkUploadProducts = ({ darkMode, setDarkMode }) => {
  const [uploading, setUploading] = useState(false);
  const [errorModalVisible, setErrorModalVisible] = useState(false);
  const [errorText, setErrorText] = useState('');
  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    try {
      // Читаем файл как массив байт
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data, { type: 'array' });
      const firstSheetName = workbook.SheetNames[0];
      const worksheet = workbook.Sheets[firstSheetName];
      // Преобразуем лист в массив массивов (первая строка – заголовки)
      const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
      
      if (jsonData.length < 2) {
        throw new Error("Файл не содержит данных");
      }
      
      // Пропускаем первую строку (заголовки)
      const dataToSend = jsonData.slice(1).map(row => ({
        barcode: String(row[0]),
        name: row[1],
        category_id: row[2],
        seller: row[3],
        in_stock_sum: row[4],
        cell: row[5],
      }));

      const token = localStorage.getItem('accessToken');
      const response = await axios.post(
        `${API_BASE_URL}/mn/manager-bulk-upload/`,
        { data: dataToSend },
        { headers: { Authorization: token ? `Bearer ${token}` : '' } }
      );

      message.success(response.data.message || "Данные успешно внесены!");
    } catch (error) {
      let errorMsg = "";
      if (error.response && error.response.data) {
        if (error.response.data.errors) {
          errorMsg = error.response.data.errors.join("\n");
        } else if (error.response.data.error) {
          errorMsg = error.response.data.error;
        } else {
          errorMsg = error.message;
        }
      } else {
        errorMsg = error.message;
      }
      setErrorText(errorMsg || "Ошибка при загрузке файла");
      setErrorModalVisible(true);
    } finally {
      setUploading(false);
      // Сброс значения input для повторной загрузки того же файла при необходимости
      e.target.value = null;
    }
  };

  const handleUploadClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
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
        <Title level={2}>Массовая загрузка штрихкодов</Title>
        <Button
          type="primary"
          onClick={handleUploadClick}
          loading={uploading}
          style={{ marginTop: 20 }}
        >
          Загрузить Excel-файл
        </Button>
        <input
          type="file"
          accept=".xlsx,.xls"
          style={{ display: 'none' }}
          ref={fileInputRef}
          onChange={handleFileChange}
        />

        <Modal
          visible={errorModalVisible}
          title="Ошибка загрузки"
          onOk={() => setErrorModalVisible(false)}
          onCancel={() => setErrorModalVisible(false)}
          className={darkMode ? 'dark-modal' : ''}
        >
          <pre style={{ whiteSpace: 'pre-wrap' }}>{errorText}</pre>
        </Modal>
      </Content>
    </Layout>
  );
};

export default ManagerBulkUploadProducts;
