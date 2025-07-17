import React, { useState, useEffect, useRef } from 'react';
import {
  Layout,
  Table,
  Descriptions,
  Typography,
  message,
  Spin,
  Button,
  Modal,
  Space,
  Select,
} from 'antd';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';
import { requestTypeOptions } from '../../utils/requestTypeOptions';
import * as XLSX from 'xlsx';

const { Content } = Layout;
const { Title } = Typography;

const StockmanSTRequestDetailPage = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const { STRequestNumber } = useParams();

  // Проверка доступа
  const [user, setUser] = useState(null);
  const [accessChecked, setAccessChecked] = useState(false);
  useEffect(() => {
    const storedUser = JSON.parse(localStorage.getItem('user') || '{}');
    setUser(storedUser);
  }, []);
  useEffect(() => {
    if (!accessChecked) {
      if (!user || Object.keys(user).length === 0) return;
      if (!user.groups || !user.groups.includes('Товаровед')) {
        Modal.error({
          title: 'Ошибка доступа',
          content: 'У вас нет доступа на эту страницу',
          okText: 'На главную',
          onOk: () => navigate('/'),
        });
      }
      setAccessChecked(true);
    }
  }, [user, accessChecked, navigate]);

  // Данные заявки
  const [detailData, setDetailData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  // Режимы сканирования: null, 'add', 'delete'
  const [scanMode, setScanMode] = useState(null);

  useEffect(() => {
    document.title = `Детали заявки ${STRequestNumber}`;
  }, [STRequestNumber]);

  // Загрузка деталей заявки
  const fetchDetail = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('accessToken');
      const response = await axios.get(
        `${API_BASE_URL}/st/strequest-detail/${STRequestNumber}/`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setDetailData(response.data);
    } catch (error) {
      message.error('Ошибка загрузки деталей заявки');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    fetchDetail();
  }, [STRequestNumber]);

  // ================================
  // ЗВУКИ
  // ================================
  const incorrectSoundUrl = localStorage.getItem('incorrectSound');
  const correctSoundUrl = localStorage.getItem('correctSound');
  const incorrectSoundRef = useRef(null);
  const correctSoundRef = useRef(null);

  useEffect(() => {
    if (incorrectSoundUrl) {
      const audio = new Audio(incorrectSoundUrl);
      audio.volume = 1.0;
      audio.load();
      incorrectSoundRef.current = audio;
    }
  }, [incorrectSoundUrl]);

  useEffect(() => {
    if (correctSoundUrl) {
      const audio = new Audio(correctSoundUrl);
      audio.volume = 1.0;
      audio.load();
      correctSoundRef.current = audio;
    }
  }, [correctSoundUrl]);

  const playIncorrectSound = () => {
    if (incorrectSoundRef.current) {
      incorrectSoundRef.current.pause();
      incorrectSoundRef.current.currentTime = 0;
      incorrectSoundRef.current.load();
      incorrectSoundRef.current.play().catch((err) => {
        console.error('Ошибка воспроизведения incorrectSound:', err);
      });
    }
  };

  const playCorrectSound = () => {
    if (correctSoundRef.current) {
      correctSoundRef.current.pause();
      correctSoundRef.current.currentTime = 0;
      correctSoundRef.current.load();
      correctSoundRef.current.play().catch((err) => {
        console.error('Ошибка воспроизведения correctSound:', err);
      });
    }
  };

  // ================================
  // Логика сканирования через клавиатуру
  // Используем useRef для буфера и времени
  // ================================
  const inputBufferRef = useRef('');
  const lastKeyTimeRef = useRef(0);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!scanMode) return;
      // Если фокус в input/textarea – игнорируем
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      if (activeTag === 'input' || activeTag === 'textarea') return;
      // Если фокус находится на кнопке, убираем его
      if (activeTag === 'button') {
        document.activeElement.blur();
      }

      const now = Date.now();
      if (now - lastKeyTimeRef.current > 1000) {
        inputBufferRef.current = '';
      }
      lastKeyTimeRef.current = now;

      if (/^[0-9]$/.test(e.key)) {
        inputBufferRef.current += e.key;
      } else if (e.key === 'Enter') {
        if (inputBufferRef.current.length === 13) {
          handleScanSubmit(inputBufferRef.current);
        }
        inputBufferRef.current = '';
      } else {
        inputBufferRef.current = '';
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [scanMode]);

  // Отправка запроса при сканировании.
  // scanMode остается активным до явного отключения.
  const handleScanSubmit = async (barcode) => {
    const token = localStorage.getItem('accessToken');
    try {
      if (scanMode === 'add') {
        await axios.post(
          `${API_BASE_URL}/st/strequest-add-barcode/${STRequestNumber}/${barcode}/`,
          {},
          { headers: { Authorization: `Bearer ${token}` } }
        );
        message.success(`Продукт ${barcode} успешно добавлен`);
        playCorrectSound();
      } else if (scanMode === 'delete') {
        await axios.delete(
          `${API_BASE_URL}/st/strequest-delete-barcode/${STRequestNumber}/${barcode}/`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        message.success(`Продукт ${barcode} успешно удалён`);
        playCorrectSound();
      } else {
        return;
      }
      await fetchDetail();
    } catch (error) {
      const errMsg = error?.response?.data?.error || 'Ошибка операции';
      message.error(errMsg);
      playIncorrectSound();
      // Режим сканирования не сбрасывается
    }
  };

  // ================================
  // Обработчики кнопок для переключения режимов сканирования
  // ================================
  const handleToggleAddScan = () => {
    if (scanMode === 'add') {
      setScanMode(null);
    } else {
      setScanMode('add');
    }
  };

  const handleToggleDeleteScan = () => {
    if (scanMode === 'delete') {
      setScanMode(null);
    } else {
      setScanMode('delete');
    }
  };

  // Печать (без столбца "Ссылка на фото")
  const handlePrint = () => {
    if (!detailData) return;
    const printWindow = window.open('', '_blank');
    const htmlContent = `
      <html>
      <head>
        <title>Печать - Заявка ${detailData.RequestNumber}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h2 { text-align: center; }
          table { width: 100%; border-collapse: collapse; margin-top: 20px; }
          table, th, td { border: 1px solid #000; }
          th, td { padding: 5px; text-align: left; }
          @media print {
            @page { margin: 20mm; }
            body { margin: 0; }
          }
        </style>
      </head>
      <body>
        <h2>Детали заявки ${detailData.RequestNumber}</h2>
        <div>
          <p><strong>Статус:</strong> ${detailData.status ? detailData.status.name : ''}</p>
          <p><strong>Дата создания:</strong> ${detailData.creation_date}</p>
          <p><strong>Товаровед:</strong> ${detailData.stockman}</p>
          <p><strong>Дата фото:</strong> ${detailData.photo_date || ''}</p>
          <p><strong>Фотограф:</strong> ${detailData.photographer || ''}</p>
          <p><strong>Количество товаров:</strong> ${detailData.products_count}</p>
          <p><strong>Количество приоритетных товаров:</strong> ${detailData.priority_products_count}</p>
        </div>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Штрихкод</th>
              <th>Наименование</th>
              <th>Инфо</th>
              <th>Приоритет</th>
            </tr>
          </thead>
          <tbody>
            ${detailData.products.map((product, index) => `
              <tr>
                <td>${index + 1}</td>
                <td>${product.barcode}</td>
                <td>${product.name}</td>
                <td>${product.info || ''}</td>
                <td>${product.priority ? 'Да' : ''}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </body>
      </html>
    `;
    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  };

  // Экспорт в Excel (включая столбец "Ссылка на фото")
  const handleExportExcel = async () => {
    if (!detailData) return;
    const hideLoading = message.loading('Формирование файла Excel...', 0);
    setExportLoading(true);
    try {
      const wsData = [];
      wsData.push([`Номер заявки: ${detailData.RequestNumber}`]);
      wsData.push([`Статус: ${detailData.status ? detailData.status.name : ''}`]);
      wsData.push([`Дата создания: ${detailData.creation_date}`]);
      wsData.push([`Товаровед: ${detailData.stockman}`]);
      wsData.push([`Дата фото: ${detailData.photo_date}`]);
      wsData.push([`Фотограф: ${detailData.photographer}`]);
      wsData.push([`Количество товаров: ${detailData.products_count}`]);
      wsData.push([`Количество приоритетных товаров: ${detailData.priority_products_count}`]);
      wsData.push([]); // пустая строка
      wsData.push([
        '№',
        'Штрихкод',
        'Наименование',
        'Принял',
        'Дата приемки',
        'Статус фото',
        'Статус проверки',
        'Ссылка на фото',
        'Инфо',
        'Приоритет',
      ]);
      detailData.products.forEach((product, index) => {
        wsData.push([
          index + 1,
          product.barcode ? Number(product.barcode) : '',
          product.name,
          product.income_stockman || '',
          product.income_date || '',
          product.photo_status ? product.photo_status.name : '',
          product.sphoto_status ? product.sphoto_status.name : '',
          product.photos_link ? product.photos_link : '',
          product.info || '',
          product.priority ? 'Да' : '',
        ]);
      });
      const worksheet = XLSX.utils.aoa_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Детали заявки');
      const now = new Date();
      const fileName = `Zayavka_${detailData.RequestNumber}_${now.toISOString().slice(0, 19)}.xlsx`;
      XLSX.writeFile(workbook, fileName);
      hideLoading();
      message.success('Excel-файл сформирован');
    } catch (error) {
      console.error(error);
      message.error('Ошибка экспорта Excel');
    } finally {
      setExportLoading(false);
    }
  };

  const handleTypeChange = async (newTypeId) => {
    const token = localStorage.getItem('accessToken');
    try {
      await axios.post(
        `${API_BASE_URL}/st/change-request-type/${STRequestNumber}/${newTypeId}/`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success('Тип заявки успешно изменён');
      await fetchDetail(); // обновляем данные
    } catch {
      message.error('Ошибка при изменении типа заявки');
    }
  };

  const columns = [
    {
      title: '#',
      key: 'index',
      render: (text, record, index) => index + 1,
      width: 50,
    },
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode',
      width: 150,
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
      width: 300,
    },
    {
      title: 'Принял',
      dataIndex: 'income_stockman',
      key: 'income_stockman',
      width: 150,
    },
    {
      title: 'Дата приемки',
      dataIndex: 'income_date',
      key: 'income_date',
      width: 150,
    },
    {
      title: 'Статус фото',
      dataIndex: 'photo_status',
      key: 'photo_status',
      width: 150,
      render: (photo_status) => (photo_status ? photo_status.name : '-'),
    },
    {
      title: 'Статус проверки',
      dataIndex: 'sphoto_status',
      key: 'sphoto_status',
      width: 150,
      render: (sphoto_status) => (sphoto_status ? sphoto_status.name : '-'),
    },
    {
      title: 'Ссылка на фото',
      dataIndex: 'photos_link',
      key: 'photos_link',
      width: 200,
      render: (photos_link) =>
        photos_link ? (
          <a href={photos_link} target="_blank" rel="noopener noreferrer">
            {photos_link}
          </a>
        ) : (
          '-'
        ),
    },
    {
      title: 'Инфо',
      dataIndex: 'info',
      key: 'info',
      width: 300,
    },
    {
      title: 'Приоритет',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (priority) => (priority ? 'Да' : ''),
    },
  ];

  const isScanActive = scanMode !== null;

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '16px' }}>
        {loading ? (
          <Spin size="large" />
        ) : detailData ? (
          <>
            <Title level={2}>Детали заявки "{detailData.RequestNumber}"</Title>
            <Descriptions bordered column={2} size="small" style={{ marginBottom: '24px' }}>
              <Descriptions.Item label="Номер заявки">
                {detailData.RequestNumber}
              </Descriptions.Item>
              <Descriptions.Item label="Статус">
                {detailData.status ? detailData.status.name : ''}
              </Descriptions.Item>
              <Descriptions.Item label="Дата создания">
                {detailData.creation_date}
              </Descriptions.Item>
              <Descriptions.Item label="Товаровед">
                {detailData.stockman}
              </Descriptions.Item>
              <Descriptions.Item label="Дата фото">
                {detailData.photo_date}
              </Descriptions.Item>
              <Descriptions.Item label="Фотограф">
                {detailData.photographer}
              </Descriptions.Item>
              <Descriptions.Item label="Тип заявки">
                 <Select
                  value={detailData.STRequestType?.id}
                  style={{ width: 200 }}
                  onChange={handleTypeChange}
                >
                  {requestTypeOptions.map(opt => (
                    <Select.Option key={opt.id} value={opt.id}>
                      {opt.name}
                    </Select.Option>
                  ))}
                </Select>
              </Descriptions.Item>
              <Descriptions.Item label="Количество товаров">
                {detailData.products_count}
              </Descriptions.Item>
              <Descriptions.Item label="Количество приоритетных товаров">
                {detailData.priority_products_count}
              </Descriptions.Item>
            </Descriptions>
            <Space style={{ marginBottom: '16px' }}>
              <Button
                type="primary"
                onClick={handleExportExcel}
                loading={exportLoading}
                disabled={isScanActive}
              >
                Скачать в Excel
              </Button>
              <Button onClick={handlePrint} disabled={isScanActive}>
                Печать
              </Button>
              <Button
                type={scanMode === 'add' ? 'primary' : 'default'}
                onClick={handleToggleAddScan}
              >
                Добавить товары
              </Button>
              <Button
                type={scanMode === 'delete' ? 'primary' : 'default'}
                onClick={handleToggleDeleteScan}
              >
                Удалить товары
              </Button>
            </Space>
            <Table
              dataSource={detailData.products}
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

export default StockmanSTRequestDetailPage;
