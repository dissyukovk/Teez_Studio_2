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
  Drawer,
  Space
} from 'antd';
import { useParams, useNavigate } from 'react-router-dom';
import axiosInstance from '../../utils/axiosInstance'; // <-- наш настроенный axios
import Sidebar from '../../components/Layout/Sidebar';
import * as XLSX from 'xlsx';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title } = Typography;

const StockmanOrderDetailPage = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const { order_number } = useParams();

  const [user, setUser] = useState(null);
  const [accessChecked, setAccessChecked] = useState(false);

  // Данные о заказе
  const [orderData, setOrderData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  // Для Drawer "Сканирование"
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Буфер для сканера и массив отсканированных товаров
  const [barcodeBuffer, setBarcodeBuffer] = useState('');
  const bufferTimer = useRef(null);
  const [scannedItems, setScannedItems] = useState([]); // Массив объектов { barcode, name, move_status, strequestnumber }

  // Звуки из localStorage (base64)
  const correctSound = localStorage.getItem('correctSound');
  const incorrectSound = localStorage.getItem('incorrectSound');

  // 1) Читаем пользователя из localStorage
  useEffect(() => {
    const storedUser = JSON.parse(localStorage.getItem('user') || '{}');
    setUser(storedUser);
  }, []);

  // 2) Проверяем группу "Товаровед"
  useEffect(() => {
    if (!accessChecked) {
      if (!user || Object.keys(user).length === 0) {
        return;
      }
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

  useEffect(() => {
    document.title = `Детали заказа "${order_number}"`;
  }, [order_number]);

  // Подтягиваем детали заказа (GET)
  const fetchOrderDetails = async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get(`/st/order-detail/${order_number}/`);
      setOrderData(response.data);
    } catch (error) {
      message.error('Ошибка загрузки деталей заказа');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrderDetails();
  }, [order_number]);

  // ----------- Обработка статуса и кнопок -------------
  const statusId = orderData?.order_status?.id;

  // "Начать приемку" (POST)
  const handleStartAccept = async () => {
    try {
      await axiosInstance.post(`/st/OrderAcceptStart/${order_number}/`);
      message.success('Приемка начата');
      await fetchOrderDetails(); // Обновить данные (статус станет 4)
    } catch (error) {
      message.error('Ошибка при старте приемки');
    }
  };

  // "Завершить приемку" (POST)
  const handleFinishAccept = async () => {
    try {
      await axiosInstance.post(`/st/order-accept-end/${order_number}/`);
      message.success('Приемка завершена');
      await fetchOrderDetails(); // обновить статус на 5 или 6
    } catch (error) {
      message.error('Ошибка при завершении приемки');
    }
  };

  // Определяем какие кнопки показывать
  const renderActionButtons = () => {
    if (!statusId) return null;
    switch (statusId) {
      case 2:
      case 3:
        return (
          <Button type="primary" onClick={handleStartAccept}>
            Начать приемку
          </Button>
        );
      case 4:
        return (
          <Space>
            <Button type="primary" onClick={openScannerDrawer}>
              Сканировать
            </Button>
            <Button danger onClick={handleFinishAccept}>
              Завершить приемку
            </Button>
          </Space>
        );
      case 5:
      case 6:
        return (
          <Button type="primary" onClick={openScannerDrawer}>
            Сканировать
          </Button>
        );
      default:
        return null;
    }
  };

  // ----------- Логика Drawer (сканирование) ------------
  const openScannerDrawer = () => {
    document.activeElement.blur(); // сброс фокуса
    setDrawerOpen(true);
  };

  const closeScannerDrawer = () => {
    setDrawerOpen(false);
    setBarcodeBuffer('');
    setScannedItems([]);
  };

  // Проигрывание звука из base64
  const playSound = (base64) => {
    if (!base64) return;
    const audio = new Audio(base64);
    audio.play().catch(() => {});
  };

  // Функция проверки товара по штрихкоду (GET)
  const checkProduct = async (barcode) => {
    // 3) Проверяем, не сканировали ли уже этот штрихкод
    if (scannedItems.some((item) => item.barcode === barcode)) {
      playSound(incorrectSound);
      message.error('Этот штрихкод уже просканирован');
      return;
    }

    try {
      const response = await axiosInstance.get(`/st/OrderCheckProduct/${order_number}/${barcode}`);
      // Успех
      playSound(correctSound);
      const data = response.data;
      const product = data.product || {};

      // 2) Новые штрихкоды добавляются наверх
      setScannedItems((prev) => [
        {
          barcode: product.barcode,
          name: product.name,
          move_status: product.move_status,
          strequestnumber: data.duplicate ? data.strequestnumber : '',
        },
        ...prev,
      ]);
    } catch (error) {
      playSound(incorrectSound);
      if (error.response && error.response.data && error.response.data.error) {
        message.error(error.response.data.error);
      } else {
        message.error('Ошибка при проверке штрихкода');
      }
    }
  };

  // Обработчик нажатий клавиш
  const handleKeyDown = (e) => {
    if (!drawerOpen) return;

    if (e.key === 'Enter') {
      if (barcodeBuffer) {
        checkProduct(barcodeBuffer);
        setBarcodeBuffer('');
      }
      return;
    }

    if (/[0-9]/.test(e.key)) {
      e.preventDefault();
      setBarcodeBuffer((prev) => prev + e.key);

      if (bufferTimer.current) {
        clearTimeout(bufferTimer.current);
      }
      bufferTimer.current = setTimeout(() => {
        setBarcodeBuffer('');
      }, 1000);
    }
  };

  useEffect(() => {
    if (drawerOpen) {
      window.addEventListener('keydown', handleKeyDown);
    } else {
      window.removeEventListener('keydown', handleKeyDown);
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [drawerOpen, barcodeBuffer]);

  // Удаление из массива
  const handleRemoveScanned = (barcode) => {
    setScannedItems((prev) => prev.filter((item) => item.barcode !== barcode));
  };

  // Колонки для таблицы сканирования
  const scannedColumns = [
    {
      title: '№',
      key: 'index',
      width: 30,
      render: (text, record, index) => index + 1,
    },
    {
      title: 'Штрихкод',
      dataIndex: 'barcode',
      key: 'barcode',
      width: 100,
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
      width: 200,
    },
    {
      title: 'Статус',
      dataIndex: 'move_status',
      key: 'move_status',
      width: 80,
    },
    {
      title: 'Есть в заявках',
      dataIndex: 'strequestnumber',
      key: 'strequestnumber',
      width: 120,
    },
    {
      title: 'Удалить',
      width: 80,
      render: (_, record) => (
        <Button danger size="small" onClick={() => handleRemoveScanned(record.barcode)}>
          Удалить
        </Button>
      ),
    },
  ];

  // Принять товары (POST)
  const handleAcceptProducts = async (barcodes) => {
    await axiosInstance.post(`/st/OrderAcceptProduct/${order_number}/`, {
      barcodes,
    });
  };

  const handleAcceptClick = async () => {
    if (scannedItems.length === 0) {
      message.warning('Список пуст');
      return;
    }
    const barcodes = scannedItems.map((item) => item.barcode);
    try {
      await handleAcceptProducts(barcodes);
      message.success('Товары успешно приняты');
      closeScannerDrawer();
      await fetchOrderDetails();
    } catch (error) {
      message.error('Ошибка при приёмке товаров');
    }
  };

  const handleCreateRequestClick = async () => {
    if (scannedItems.length === 0) {
      message.warning('Список пуст');
      return;
    }
    const barcodes = scannedItems.map((item) => item.barcode);
    try {
      // 1) Принять
      await handleAcceptProducts(barcodes);

      // 2) Создать заявку
      const response = await axiosInstance.post('/st/strequest-create-barcodes/', {
        barcodes,
      });
      const { RequestNumber } = response.data;
      if (RequestNumber) {
        message.success(`Заявка №${RequestNumber} создана`);
        window.open(`/stockman-strequest-detail/${RequestNumber}`, '_blank');
      }

      closeScannerDrawer();
      await fetchOrderDetails();
    } catch (error) {
      message.error('Ошибка при создании заявки');
    }
  };

  // Экспорт в Excel
  const handleExportExcel = async () => {
    if (!orderData) return;
    const hideLoading = message.loading('Формирование файла Excel...', 0);
    setExportLoading(true);
    try {
      const wsData = [];
      wsData.push([`Номер заказа: ${orderData.order_number}`]);
      wsData.push([]);
      wsData.push(['№', 'Штрихкод', 'Наименование', 'Ячейка']);
      orderData.products.forEach((product, index) => {
        wsData.push([index + 1, product.barcode, product.name, product.cell]);
      });

      const worksheet = XLSX.utils.aoa_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Order Details');
      const now = new Date();
      const fileName = `Order_${orderData.order_number}_${now.toISOString().slice(0, 19)}.xlsx`;
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

  // Печать
  const handlePrint = () => {
    if (!orderData) return;
    const printWindow = window.open('', '_blank');
    const htmlContent = `
      <html>
      <head>
        <title>Печать - Заказ ${orderData.order_number}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h2 { text-align: center; }
          table { width: 100%; border-collapse: collapse; margin-top: 20px; }
          table, th, td { border: 1px solid #000; }
          th, td { padding: 9px; text-align: left; }
          @media print {
            @page { margin: 20mm; }
            body { margin: 0; }
          }
        </style>
      </head>
      <body>
        <h2>Номер заказа: ${orderData.order_number}</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Штрихкод</th>
              <th>Наименование</th>
              <th>Ячейка</th>
            </tr>
          </thead>
          <tbody>
            ${orderData.products
              .map(
                (product, index) => `
                  <tr>
                    <td>${index + 1}</td>
                    <td>${product.barcode}</td>
                    <td>${product.name}</td>
                    <td>${product.cell}</td>
                  </tr>
                `
              )
              .join('')}
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

  // Колонки для основной таблицы
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
    },
    {
      title: 'Наименование',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Ячейка',
      dataIndex: 'cell',
      key: 'cell',
    },
    {
      title: 'Время приемки',
      dataIndex: 'accepted_date',
      key: 'accepted_date',
    },
    {
      title: 'Принят',
      dataIndex: 'accepted',
      key: 'accepted',
      render: (accepted) => (
        <span style={{ color: accepted ? 'green' : 'red' }}>
          {accepted ? 'Да' : 'Нет'}
        </span>
      ),
    },
  ];

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '16px' }}>
        {loading ? (
          <Spin size="large" />
        ) : orderData ? (
          <>
            <Title level={2}>Детали заказа "{orderData.order_number}"</Title>
            <Descriptions bordered column={2} size="small" style={{ marginBottom: '24px' }}>
              <Descriptions.Item label="Номер заказа">
                {orderData.order_number}
              </Descriptions.Item>
              <Descriptions.Item label="Статус">
                {orderData.order_status ? orderData.order_status.name : ''}
              </Descriptions.Item>
              <Descriptions.Item label="Заказчик">
                {orderData.creator}
              </Descriptions.Item>
              <Descriptions.Item label="Дата создания">
                {orderData.date}
              </Descriptions.Item>
              <Descriptions.Item label="Сотрудник сборки">
                {orderData.assembly_user}
              </Descriptions.Item>
              <Descriptions.Item label="Время сборки">
                {orderData.assembly_date}
              </Descriptions.Item>
              <Descriptions.Item label="Сотрудник приемки">
                {orderData.accept_user}
              </Descriptions.Item>
              <Descriptions.Item label="Время начала приемки">
                {orderData.accept_date}
              </Descriptions.Item>
              <Descriptions.Item label="Время окончания приемки">
                {orderData.accept_date_end}
              </Descriptions.Item>
              <Descriptions.Item label="Время приемки">
                {orderData.accept_time}
              </Descriptions.Item>
              <Descriptions.Item label="Общее количество товаров">
                {orderData.total_products}
              </Descriptions.Item>
            </Descriptions>

            {/* Кнопки действий в зависимости от статуса */}
            <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
              {renderActionButtons()}
              <Button type="primary" onClick={handleExportExcel} loading={exportLoading}>
                Скачать в Excel
              </Button>
              <Button onClick={handlePrint}>Печать</Button>
            </div>

            <Table
              dataSource={orderData.products}
              columns={columns}
              rowKey="barcode"
              pagination={false}
            />

            {/* Drawer для сканирования */}
            <Drawer
              title="Приемка"
              placement="right"
              width='55vw'
              onClose={closeScannerDrawer}
              open={drawerOpen}
              extra={
                <Space>
                  <Button onClick={closeScannerDrawer}>Закрыть</Button>
                </Space>
              }
            >
              <div style={{ marginBottom: 16 }}>Количество: {scannedItems.length}</div>
              <Table
                columns={scannedColumns}
                // Массив уже идёт в порядке "новые сверху",
                // т.к. мы вставляем новый штрихкод в начало
                dataSource={scannedItems}
                rowKey="barcode"
                pagination={false}
                // 1) Высота ~75vh
                scroll={{ y: '75vh' }}
                // 4) Фиксированная ширина столбцов, чтобы заработали width
                tableLayout="fixed"
              />

              <Space style={{ marginTop: 16 }}>
                <Button type="primary" onClick={handleAcceptClick}>
                  Принять
                </Button>
                <Button onClick={handleCreateRequestClick}>Создать заявку</Button>
              </Space>
            </Drawer>
          </>
        ) : (
          <div>Нет данных</div>
        )}
      </Content>
    </Layout>
  );
};

export default StockmanOrderDetailPage;
