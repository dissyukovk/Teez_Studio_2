import React, { useState, useEffect, useCallback } from 'react';
import {
  Layout,
  Table,
  Input,
  Button,
  Space,
  Pagination,
  message, // <-- ИЗМЕНЕНИЕ: импорт message
  Modal,
  Select,
  Checkbox,
  Tag,
  Typography,
} from 'antd';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import dayjs from 'dayjs'; // <-- ИЗМЕНЕНИЕ: импорт dayjs
import * as XLSX from 'xlsx'; // <-- ИЗМЕНЕНИЕ: импорт xlsx
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { TextArea } = Input;
const { Link } = Typography;

const AllRendersListPage = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const [token, setToken] = useState(null);

  // --- ИЗМЕНЕНИЕ: Добавлен messageApi для уведомлений о загрузке ---
  const [messageApi, contextHolder] = message.useMessage();

  // --- Состояния для данных и управления таблицей ---
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [ordering, setOrdering] = useState('pk');

  // --- Состояния для опций фильтров (загружаются с бэкенда) ---
  const [statusOptions, setStatusOptions] = useState([]);
  const [retoucherOptions, setRetoucherOptions] = useState([]);

  // --- Временные состояния для полей ввода фильтров ---
  const [tempBarcodes, setTempBarcodes] = useState('');
  const [tempStatus, setTempStatus] = useState(null);
  const [tempRetoucher, setTempRetoucher] = useState(null);
  const [tempIsSuitable, setTempIsSuitable] = useState(null);

  // --- Примененные состояния фильтров (используются в запросе) ---
  const [appliedBarcodes, setAppliedBarcodes] = useState('');
  const [appliedStatus, setAppliedStatus] = useState(null);
  const [appliedRetoucher, setAppliedRetoucher] = useState(null);
  const [appliedIsSuitable, setAppliedIsSuitable] = useState(null);

  useEffect(() => {
    document.title = 'Все рендеры';
  }, []);

  useEffect(() => {
    const storedToken = localStorage.getItem('accessToken');
    if (!storedToken) {
      Modal.error({
        title: 'Ошибка доступа',
        content: 'Токен авторизации не найден. Пожалуйста, выполните вход.',
        okText: 'Войти',
        onOk: () => navigate('/login'),
      });
    } else {
      setToken(storedToken);
    }
  }, [navigate]);

  useEffect(() => {
    if (token) {
      axios.get(`${API_BASE_URL}/rd/retouch-statuses/`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(response => {
        setStatusOptions(response.data.map(item => ({ label: item.name, value: item.id })));
      }).catch(error => console.error("Ошибка загрузки статусов:", error));

      axios.get(`${API_BASE_URL}/rd/list_retouchers_with_status3/`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(response => {
        setRetoucherOptions(response.data.map(item => ({ label: item.name, value: item.id })));
      }).catch(error => console.error("Ошибка загрузки ретушеров:", error));
    }
  }, [token]);

  const fetchData = useCallback(async (page, size, order, filters) => {
    if (!token) return;
    setLoading(true);
    try {
      const params = {
        page,
        page_size: size,
        ordering: order,
      };

      if (filters.barcodes) {
        params.Product__Barcode = filters.barcodes.split('\n').map(b => b.trim()).filter(Boolean).join(',');
      }
      if (filters.status) {
        params.RetouchStatus__id = filters.status;
      }
      if (filters.retoucher) {
        params.Retoucher__id = filters.retoucher;
      }
      if (filters.isSuitable !== null) {
        params.IsSuitable = filters.isSuitable;
      }

      const response = await axios.get(`${API_BASE_URL}/rd/all-renders/`, {
        params,
        headers: { Authorization: `Bearer ${token}` },
      });

      setData(response.data.results.map((item) => ({ key: item.id, ...item })));
      setTotalCount(response.data.count || 0);
    } catch (error) {
      console.error('Ошибка загрузки данных', error);
      message.error('Не удалось загрузить данные.');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    const appliedFilters = {
      barcodes: appliedBarcodes,
      status: appliedStatus,
      retoucher: appliedRetoucher,
      isSuitable: appliedIsSuitable,
    };
    fetchData(currentPage, pageSize, ordering, appliedFilters);
  }, [currentPage, pageSize, ordering, appliedBarcodes, appliedStatus, appliedRetoucher, appliedIsSuitable, fetchData]);

  const handleSearch = () => {
    setAppliedBarcodes(tempBarcodes);
    setAppliedStatus(tempStatus);
    setAppliedRetoucher(tempRetoucher);
    setAppliedIsSuitable(tempIsSuitable);
    setCurrentPage(1);
  };

  const handleTableChange = (pagination, filters, sorter) => {
    const newOrdering = sorter.order
      ? `${sorter.order === 'descend' ? '-' : ''}${sorter.field}`
      : 'pk';
    setOrdering(newOrdering);
  };

  const handlePageChange = (page, size) => {
    setCurrentPage(page);
    setPageSize(size);
  };

  // --- ИЗМЕНЕНИЕ: Новая функция для экспорта в Excel ---
  const handleExportExcel = async () => {
    messageApi.open({
      type: 'loading',
      content: 'Формирование файла Excel...',
      duration: 0,
    });

    try {
      const params = {
        page_size: 900000, // Устанавливаем большой лимит для получения всех данных
        ordering,
      };

      // Применяем те же фильтры, что и для таблицы
      if (appliedBarcodes) {
        params.Product__Barcode = appliedBarcodes.split('\n').map(b => b.trim()).filter(Boolean).join(',');
      }
      if (appliedStatus) {
        params.RetouchStatus__id = appliedStatus;
      }
      if (appliedRetoucher) {
        params.Retoucher__id = appliedRetoucher;
      }
      if (appliedIsSuitable !== null) {
        params.IsSuitable = appliedIsSuitable;
      }

      const response = await axios.get(`${API_BASE_URL}/rd/all-renders/`, {
        params,
        headers: { Authorization: `Bearer ${token}` },
      });

      const allResults = response.data.results || [];

      // Подготовка данных для листа Excel
      const wsData = allResults.map(item => ({
        'ID': item.id,
        'Barcode': item.product?.barcode || '',
        'Name': item.product?.name || '',
        'CheckTimeStart': item.CheckTimeStart ? dayjs(item.CheckTimeStart).format('YYYY-MM-DD  HH:mm:ss') : '',
        'RetouchStatus': item.RetouchStatus ? `${item.RetouchStatus.id} - ${item.RetouchStatus.name}` : '',
        'CheckResult': item.CheckResult?.map(r => `${r.id} - ${r.name}`).join('; ') || '', // Преобразуем массив в строку
        'RetoucherName': item.RetoucherName || '',
        'IsSuitable': item.IsSuitable === null ? 'N/A' : (item.IsSuitable ? 'Да' : 'Нет'),
        'RetouchPhotosLink': item.RetouchPhotosLink || ''
      }));

      const worksheet = XLSX.utils.json_to_sheet(wsData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, 'AllRenders');
      const fileName = `all_renders_${dayjs().format('YYYY-MM-DD_HH-mm')}.xlsx`;
      XLSX.writeFile(workbook, fileName);

      messageApi.destroy();
      message.success('Файл Excel успешно сформирован!');

    } catch (error) {
      console.error('Ошибка экспорта в Excel:', error);
      messageApi.destroy();
      message.error('Не удалось сформировать файл Excel.');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', sorter: true },
    { title: 'Barcode', dataIndex: ['product', 'barcode'], key: 'Barcode', sorter: false },
    { title: 'Name', dataIndex: ['product', 'name'], key: 'Name', sorter: false, width: 300 },
    {
      title: 'CheckTimeStart',
      dataIndex: 'CheckTimeStart',
      key: 'CheckTimeStart',
      sorter: true,
      render: (text) => text ? dayjs(text).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: 'RetouchStatus',
      dataIndex: 'RetouchStatus',
      key: 'RetouchStatus',
      render: (status) => status ? `${status.id} - ${status.name}` : '-',
    },
    {
      title: 'CheckResult',
      dataIndex: 'CheckResult',
      key: 'CheckResult',
      render: (results) => (
        <>
          {results.map(result => (
            <Tag key={result.id}>{`${result.id} - ${result.name}`}</Tag>
          ))}
        </>
      ),
    },
    { title: 'RetoucherName', dataIndex: 'RetoucherName', key: 'RetoucherName', sorter: false },
    {
      title: 'IsSuitable',
      dataIndex: 'IsSuitable',
      key: 'IsSuitable',
      sorter: true,
      render: (isSuitable) => {
        if (isSuitable === null) return 'N/A';
        return isSuitable ? 'Да' : 'Нет';
      },
    },
    {
      title: 'RetouchPhotosLink',
      dataIndex: 'RetouchPhotosLink',
      key: 'RetouchPhotosLink',
      render: (link) => link ? <Link href={link} target="_blank" rel="noopener noreferrer">Ссылка</Link> : '-',
    },
  ];

  return (
    <Layout>
      {/* --- ИЗМЕНЕНИЕ: Добавлен contextHolder --- */}
      {contextHolder}
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: '16px' }}>
        <h2>Все рендеры</h2>
        
        <Space wrap style={{ marginBottom: 16 }} align="end">
          <Space direction="vertical">
            <span>Штрихкоды</span>
            <TextArea
              placeholder="Каждый на новой строке"
              value={tempBarcodes}
              onChange={(e) => setTempBarcodes(e.target.value)}
              rows={3}
              style={{ width: 200 }}
            />
          </Space>
          <Space direction="vertical">
            <span>Статус ретуши</span>
            <Select
              allowClear
              placeholder="Выберите статус"
              value={tempStatus}
              onChange={(value) => setTempStatus(value)}
              options={statusOptions}
              style={{ width: 200 }}
            />
          </Space>
          <Space direction="vertical">
            <span>Ретушер</span>
            <Select
              allowClear
              placeholder="Выберите ретушера"
              value={tempRetoucher}
              onChange={(value) => setTempRetoucher(value)}
              options={retoucherOptions}
              style={{ width: 200 }}
            />
          </Space>
          <Space direction="vertical">
             <span>Пригоден</span>
             <Select
              allowClear
              placeholder="Да/Нет/Все"
              value={tempIsSuitable}
              onChange={(value) => setTempIsSuitable(value)}
              style={{ width: 120 }}
            >
              <Select.Option value={true}>Да</Select.Option>
              <Select.Option value={false}>Нет</Select.Option>
            </Select>
          </Space>
          <Button type="primary" onClick={handleSearch}>Поиск</Button>
          {/* --- ИЗМЕНЕНИЕ: Добавлена кнопка экспорта --- */}
          <Button onClick={handleExportExcel} disabled={loading}>
            Скачать Excel
          </Button>
        </Space>

        <Pagination
          current={currentPage}
          pageSize={pageSize}
          total={totalCount}
          onChange={handlePageChange}
          showSizeChanger
          onShowSizeChange={handlePageChange}
          pageSizeOptions={['10', '20', '50', '100']}
          showTotal={(total) => `Всего: ${total}`}
          style={{ marginBottom: 16 }}
        />

        <Table
          columns={columns}
          dataSource={data}
          loading={loading}
          onChange={handleTableChange}
          pagination={false}
          scroll={{ x: 1300 }}
        />
      </Content>
    </Layout>
  );
};

export default AllRendersListPage;