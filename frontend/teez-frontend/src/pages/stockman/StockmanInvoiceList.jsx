import React, { useState, useEffect, useRef } from 'react';
import { Layout, Table, Input, Button, Space, Drawer, Pagination, message } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { TextArea } = Input;

// Значения по умолчанию (на случай, если в localStorage пусто)
const defaultCorrectSound = 'data:audio/wav;base64,...';
const defaultIncorrectSound = 'data:audio/wav;base64,...';

const StockmanInvoiceList = ({ darkMode, setDarkMode }) => {
  // Состояния для поиска накладных
  const [invoiceNumbers, setInvoiceNumbers] = useState('');
  const [barcodesSearch, setBarcodesSearch] = useState('');
  const [invoiceData, setInvoiceData] = useState([]);
  const [loading, setLoading] = useState(false);

  // Состояния для пагинации
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalCount, setTotalCount] = useState(0);

  // Состояние сортировки, по умолчанию - по убыванию номера накладной
  const [ordering, setOrdering] = useState("-InvoiceNumber");

  // Состояния для работы со сканированием в Drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [scannedItems, setScannedItems] = useState([]);
  const [barcodeBuffer, setBarcodeBuffer] = useState('');
  const bufferTimer = useRef(null);

  // Создаем рефы для звуков
  const correctSoundRef = useRef(null);
  const incorrectSoundRef = useRef(null);

  // Инициализируем аудио-объекты, беря URL из localStorage
  useEffect(() => {
    const storedCorrectSound = localStorage.getItem('correctSound') || defaultCorrectSound;
    const storedIncorrectSound = localStorage.getItem('incorrectSound') || defaultIncorrectSound;
    correctSoundRef.current = new Audio(storedCorrectSound);
    incorrectSoundRef.current = new Audio(storedIncorrectSound);
  }, []);

  // Функции для воспроизведения звуков
  const playCorrectSound = () => {
    if (correctSoundRef.current) {
      correctSoundRef.current.pause();
      correctSoundRef.current.currentTime = 0;
      correctSoundRef.current.play().catch((err) => {
        console.error('Ошибка воспроизведения correctSound:', err);
      });
    }
  };

  const playIncorrectSound = () => {
    if (incorrectSoundRef.current) {
      incorrectSoundRef.current.pause();
      incorrectSoundRef.current.currentTime = 0;
      incorrectSoundRef.current.play().catch((err) => {
        console.error('Ошибка воспроизведения incorrectSound:', err);
      });
    }
  };

  // Функция загрузки данных с учетом пагинации, поиска и сортировки
  const fetchInvoiceData = async (page = 1, size = pageSize, orderingParam = ordering) => {
    setLoading(true);
    try {
      const params = { page, page_size: size, ordering: orderingParam };

      if (invoiceNumbers.trim()) {
        const lines = invoiceNumbers.split('\n').map(s => s.trim()).filter(Boolean);
        if (lines.length > 0) {
          params.invoice_numbers = lines.join(',');
        }
      }
      if (barcodesSearch.trim()) {
        const lines = barcodesSearch.split('\n').map(s => s.trim()).filter(Boolean);
        if (lines.length > 0) {
          params.barcodes = lines.join(',');
        }
      }
      const response = await axios.get(`${API_BASE_URL}/st/invoices/`, { params });
      setInvoiceData(response.data.results || []);
      setTotalCount(response.data.count || 0);
      setCurrentPage(page);
      setPageSize(size);
    } catch (error) {
      message.error('Ошибка загрузки накладных');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoiceData();
    document.title = 'Список накладных';
  }, []);

  const handleSearch = () => {
    fetchInvoiceData(1, pageSize, ordering);
  };

  const handleTableChange = (pagination, filters, sorter) => {
    let newOrdering = ordering;
    if (sorter && sorter.field) {
      newOrdering = sorter.order === 'ascend' ? sorter.field : `-${sorter.field}`;
    }
    setOrdering(newOrdering);
    fetchInvoiceData(pagination.current, pagination.pageSize, newOrdering);
  };

  const handlePageChange = (page, size) => {
    setCurrentPage(page);
    setPageSize(size);
    fetchInvoiceData(page, size, ordering);
  };

  const openScannerDrawer = () => {
    setDrawerOpen(true);
  };

  const closeScannerDrawer = () => {
    setDrawerOpen(false);
    setBarcodeBuffer('');
    setScannedItems([]);
  };

  const checkProduct = async (barcode) => {
    if (scannedItems.some(item => item.barcode === barcode)) {
      playIncorrectSound();
      message.error('Этот штрихкод уже просканирован');
      return;
    }
    try {
      const response = await axios.post(`${API_BASE_URL}/st/invoice-check-barcode/`, { barcode });
      playCorrectSound();
      const product = response.data;
      setScannedItems(prev => [
        {
          barcode: product.barcode,
          name: product.name,
          move_status: product.move_status?.name || '',
          alert_st_requests: product.alert_st_requests || [],
        },
        ...prev,
      ]);
    } catch (error) {
      playIncorrectSound();
      const errMsg = error.response?.data?.error || 'Ошибка проверки штрихкода';
      message.error(errMsg);
    }
  };

  const handleKeyDown = (e) => {
    if (!drawerOpen) return;
    if (e.key === 'Enter') {
      if (barcodeBuffer) {
        if (barcodeBuffer.length === 13) {
          checkProduct(barcodeBuffer);
        } else {
          message.error('Неверная длина штрихкода');
        }
        setBarcodeBuffer('');
      }
      return;
    }
    if (/[0-9]/.test(e.key)) {
      e.preventDefault();
      setBarcodeBuffer(prev => prev + e.key);
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

  const handleRemoveScanned = (barcode) => {
    setScannedItems(prev => prev.filter(item => item.barcode !== barcode));
  };

  const scannedColumns = [
    {
      title: '№',
      key: 'index',
      width: 30,
      render: (text, record, index) => index + 1,
    },
    { title: 'Штрихкод', dataIndex: 'barcode', key: 'barcode', width: 120 },
    { title: 'Наименование', dataIndex: 'name', key: 'name', width: 200 },
    { title: 'Статус', dataIndex: 'move_status', key: 'move_status', width: 100 },
    {
      title: 'Заявки',
      key: 'alert_st_requests',
      width: 200,
      render: (text, record) => {
        if (record.alert_st_requests && record.alert_st_requests.length > 0) {
          return record.alert_st_requests
            .map(req => `${req.RequestNumber} - ${req.status?.name || ''}`)
            .join(', ');
        }
        return '';
      },
    },
    {
      title: 'Удалить',
      key: 'delete',
      width: 80,
      render: (_, record) => (
        <Button danger size="small" onClick={() => handleRemoveScanned(record.barcode)}>
          Удалить
        </Button>
      ),
    },
  ];

  const invoiceColumns = [
    {
      title: 'Номер',
      dataIndex: 'InvoiceNumber',
      key: 'InvoiceNumber',
      sorter: true,
      defaultSortOrder: 'descend',
      render: (text) => (
        <a href={`/stockman-invoice-detail/${text}/`} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      ),
    },
    { title: 'Дата', dataIndex: 'date', key: 'date', sorter: true },
    { title: 'Товаровед', dataIndex: 'creator', key: 'creator', sorter: true },
    { title: 'Количество товаров', dataIndex: 'product_count', key: 'product_count', sorter: true },
  ];

  const handleFinishScan = async () => {
    if (scannedItems.length === 0) {
      message.error('Нет просканированных штрихкодов');
      playIncorrectSound();
      return;
    }
    const barcodes = scannedItems.map(item => item.barcode);
    const token = localStorage.getItem('accessToken');
    try {
      const response = await axios.post(
        `${API_BASE_URL}/st/invoice-create/`,
        { barcodes },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const invoiceNumber = response.data.InvoiceNumber;
      window.open(`/stockman-invoice-detail/${invoiceNumber}/`, '_blank');
      message.success('Накладная создана');
      playCorrectSound();
      closeScannerDrawer();
      fetchInvoiceData(currentPage, pageSize, ordering);
    } catch (error) {
      const errMsg = error.response?.data?.error || 'Ошибка создания накладной';
      message.error(errMsg);
      playIncorrectSound();
    }
  };  

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16 }}>
        <h2>Список накладных</h2>
        <Space style={{ marginBottom: 16 }}>
          <Space direction="vertical">
            <div>Поиск по номерам накладных</div>
            <TextArea
              placeholder="Номера накладных (каждый с новой строки)"
              value={invoiceNumbers}
              onChange={(e) => setInvoiceNumbers(e.target.value)}
              rows={4}
              style={{ width: 200 }}
            />
          </Space>
          <Space direction="vertical">
            <div>Поиск по штрихкодам</div>
            <TextArea
              placeholder="Штрихкоды (каждый с новой строки)"
              value={barcodesSearch}
              onChange={(e) => setBarcodesSearch(e.target.value)}
              rows={4}
              style={{ width: 200 }}
            />
          </Space>
          <Button type="primary" onClick={handleSearch}>
            Поиск
          </Button>
        </Space>
        <div style={{ marginBottom: 16 }}>
          <Button type="primary" onClick={openScannerDrawer}>
            Отправка
          </Button>
        </div>
        <div style={{ marginBottom: 16 }}>
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            total={totalCount}
            onChange={handlePageChange}
            showSizeChanger
            onShowSizeChange={handlePageChange}
            showTotal={(total) => `Всего ${total} записей`}
          />
        </div>
        <Table
          columns={invoiceColumns}
          dataSource={invoiceData}
          rowKey="InvoiceNumber"
          loading={loading}
          pagination={false}
          onChange={handleTableChange}
        />
      </Content>
      <Drawer
        title="Сканируйте для начала отправки"
        placement="right"
        width="55vw"
        onClose={closeScannerDrawer}
        open={drawerOpen}
        extra={<Space><Button onClick={closeScannerDrawer}>Закрыть</Button></Space>}
      >
        <div style={{ marginBottom: 16 }}>Количество: {scannedItems.length}</div>
        <Table
          columns={scannedColumns}
          dataSource={scannedItems}
          rowKey="barcode"
          pagination={false}
          scroll={{ y: '75vh' }}
          tableLayout="fixed"
        />
        <Space style={{ marginTop: 16 }}>
          <Button onClick={closeScannerDrawer}>Отменить</Button>
          <Button type="primary" onClick={handleFinishScan}>
            Завершить
          </Button>
        </Space>
      </Drawer>
    </Layout>
  );
};

export default StockmanInvoiceList;
