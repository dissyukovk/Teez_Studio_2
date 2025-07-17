import React, { useState, useEffect } from 'react';
import { Layout, Table, Pagination, Button, Select, Input, Modal, message, Typography } from 'antd';
import Sidebar from '../../components/Layout/Sidebar';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Option } = Select;
const { Title } = Typography;
const { TextArea } = Input;

// Опции для причин отклонения
const rejectReasonOptions = [
  { value: 10, label: 'Товар не соответствует названию' },
  { value: 9, label: 'Товар виден не полностью/Нет лицевой стороны' },
  { value: 8, label: 'Плохое качество исходника' },
  { value: 7, label: 'Инфографика/Watermark' },
  { value: 6, label: 'Сложный фон' },
  { value: 5, label: 'Разрешение слишком маленькое' },
  { value: 4, label: 'Коллаж' },
  { value: 3, label: 'Нет фото' },
  { value: 2, label: 'Дубль' },
  { value: 1, label: 'Соответствует регламенту' },
];

const SeniorRetoucherCheck = ({ darkMode, setDarkMode }) => {
  const [data, setData] = useState([]);
  const [retoucherOptions, setRetoucherOptions] = useState([]);
  const [retoucherFilter, setRetoucherFilter] = useState([]); // массив выбранных id
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 600, total: 0 });
  const [bulkStatus, setBulkStatus] = useState(null);

  // Состояния для модального окна "Отклонить"
  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [currentRender, setCurrentRender] = useState(null);
  const [modalIsSuitable, setModalIsSuitable] = useState(null); // true или false
  const [modalReasons, setModalReasons] = useState([]); // массив выбранных причин (id)
  const [modalComment, setModalComment] = useState(''); // комментарий для отклонения

  // Функция загрузки списка ретушёров для фильтрации
  const fetchRetoucherOptions = async () => {
    const token = localStorage.getItem('accessToken');
    try {
      const response = await axios.get(`${API_BASE_URL}/rd/list_retouchers_with_status3/`, {
        headers: { Authorization: token ? `Bearer ${token}` : '' }
      });
      setRetoucherOptions(response.data);
    } catch (error) {
      message.error('Ошибка при загрузке списка ретушёров');
    }
  };

  // Функция загрузки данных с сервера с учётом фильтра по ретушёрам
  const fetchData = async (page = 1, retoucherFilters = retoucherFilter) => {
    setLoading(true);
    const token = localStorage.getItem('accessToken');
    try {
      const params = { page };
      if (retoucherFilters && retoucherFilters.length > 0) {
        params.retoucher = retoucherFilters.join(',');
      }
      const response = await axios.get(`${API_BASE_URL}/rd/senior-render-list/`, {
        headers: { Authorization: token ? `Bearer ${token}` : '' },
        params
      });
      const { results, count } = response.data;
      // Добавляем к записям локальные поля для редактирования:
      const mappedData = results.map(item => ({
        ...item,
        key: item.id,
        customStatus: null,
        customComment: item.RetouchSeniorComment || '',
        retoucher_id: item.Retoucher && item.Retoucher.id ? item.Retoucher.id : null
      }));
      setData(mappedData);
      setPagination({ current: page, pageSize: 600, total: count });
    } catch (error) {
      message.error('Ошибка при загрузке данных');
    }
    setLoading(false);
  };

  useEffect(() => {
    document.title = 'Проверка рендеров';
    fetchData();
    fetchRetoucherOptions();
  }, []);

  // Обработчик изменения фильтров в таблице – для серверной фильтрации
  const handleTableChange = (pagination, filters, sorter) => {
    const selectedRetouchers = filters.retoucher || [];
    setRetoucherFilter(selectedRetouchers);
    fetchData(1, selectedRetouchers);
  };

  // Функция открытия модального окна для отклонения
  const openRejectModal = (record) => {
    setCurrentRender(record);
    setModalIsSuitable(null);
    setModalReasons([]);
    setModalComment('');
    setRejectModalVisible(true);
  };

  // Обработчик для выбора статуса в столбце "Статус"
  const handleStatusSelect = (record, value) => {
    if (value === 'reject') {
      openRejectModal(record);
    } else {
      handleStatusChange(record.id, value);
    }
  };

  // Обработчик сохранения данных из модального окна
  const handleModalSave = async () => {
    if (modalIsSuitable === null) {
      message.error('Укажите, подходит ли для рендера.');
      return;
    }
    const token = localStorage.getItem('accessToken');
    // Формирование payload согласно backend: IsSuitable, CheckResult, CheckComment
    let payload = {
      IsSuitable: modalIsSuitable,
    };
    if (modalIsSuitable === false) {
      payload.CheckResult = modalReasons;
      payload.CheckComment = modalComment;
    }
    try {
      const response = await axios.patch(
        `${API_BASE_URL}/rd/senior-update-render/${currentRender.id}/`,
        payload,
        {
          headers: { Authorization: token ? `Bearer ${token}` : '' }
        }
      );
      message.success(response.data.message || 'Запись успешно обновлена.');
      setRejectModalVisible(false);
      // Обновляем данные таблицы
      fetchData(pagination.current);
    } catch (error) {
      message.error(error.response?.data?.message || 'Ошибка при обновлении записи.');
    }
  };

  // Обработчики для модального окна
  const handleModalCancel = () => {
    setRejectModalVisible(false);
  };

  // Определяем колонки таблицы, добавляем столбцы "Статус" и "Отклонить"
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: 'Ретушер',
      dataIndex: 'RetoucherName',
      key: 'retoucher',
      filters: retoucherOptions.map(option => ({ text: option.name, value: option.id })),
      filteredValue: retoucherFilter,
    },
    {
      title: 'Штрихкод',
      dataIndex: ['product', 'barcode'],
      key: 'barcode',
    },
    {
      title: 'Наименование',
      dataIndex: ['product', 'name'],
      key: 'name',
    },
    {
      title: 'Общие комментарии',
      key: 'commonComments',
      render: (text, record) => {
        const modComment = record.product.ModerationComment || '';
        const rejectComment = record.product.RejectComment || '';
        return `${modComment} ${rejectComment}`.trim();
      },
    },
    {
      title: 'Комментарий ретушера',
      key: 'retoucherComment',
      render: (text, record) => {
        const checkComment = record.CheckComment || '';
        const retouchComment = record.RetouchComment || '';
        return `${checkComment} ${retouchComment}`.trim();
      },
    },
    {
      title: 'Ссылка',
      dataIndex: 'RetouchPhotosLink',
      key: 'RetouchPhotosLink',
      render: (link) => (
        <a href={link} target="_blank" rel="noopener noreferrer">
          {link}
        </a>
      ),
    },
    {
      title: 'Статус',
      key: 'status',
      render: (text, record) => (
        <Select
          style={{ width: 120 }}
          value={record.customStatus}
          placeholder="Выбрать"
          onChange={(value) => handleStatusSelect(record, value)}
        >
          <Option value={6}>Проверено</Option>
          <Option value={4}>Правки</Option>
          <Option value="reject">Отклонить на рендер</Option>
        </Select>
      ),
    },
    {
      title: 'Комментарий',
      key: 'comment',
      render: (text, record) => (
        <Input
          value={record.customComment}
          onChange={(e) => handleCommentChange(record.id, e.target.value)}
        />
      ),
    },
  ];

  // Обработчики изменения значения статуса и комментария для отдельной записи
  const handleStatusChange = (id, value) => {
    const newData = data.map(item => {
      if (item.id === id) {
        return { ...item, customStatus: value };
      }
      return item;
    });
    setData(newData);
  };

  const handleCommentChange = (id, value) => {
    const newData = data.map(item => {
      if (item.id === id) {
        return { ...item, customComment: value };
      }
      return item;
    });
    setData(newData);
  };

  // Bulk‑обновление: изменение статуса для выбранных записей
  const handleBulkStatusChange = (value) => {
    setBulkStatus(value);
    const newData = data.map(item => {
      if (selectedRowKeys.includes(item.id)) {
        return { ...item, customStatus: value };
      }
      return item;
    });
    setData(newData);
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: (selectedKeys) => {
      setSelectedRowKeys(selectedKeys);
    },
  };

  // Обработчик нажатия на кнопку "Готово" для bulk‑обновления
  const handleSubmit = async () => {
    const rowsWithStatus = data.filter(item => item.customStatus !== null);
    if (rowsWithStatus.length === 0) {
      message.error('Нет записей с установленным статусом');
      return;
    }
    const payload = {
      renders: rowsWithStatus.map(item => ({
        render_id: item.id,
        retouch_status_id: item.customStatus,
        comment: item.customComment
      }))
    };
    const token = localStorage.getItem('accessToken');
    try {
      const response = await axios.post(`${API_BASE_URL}/rd/senior-to-edit-render/`, payload, {
        headers: { Authorization: token ? `Bearer ${token}` : '' }
      });
      message.success(response.data.message || 'Статус обновлён.');
      fetchData(pagination.current);
      setSelectedRowKeys([]);
    } catch (error) {
      message.error(error.response?.data?.message || 'Ошибка при обновлении статуса');
    }
  };

  // Обработчик изменения страницы
  const handlePageChange = (page) => {
    fetchData(page);
  };

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content
        style={{
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          minHeight: '100vh',
          width: '100%',
        }}
      >
        <Title level={2} style={{ marginBottom: 16 }}>
          Проверка рендеров
        </Title>

        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Select
            placeholder="Установить статус для выбранных"
            style={{ width: 200 }}
            onChange={handleBulkStatusChange}
            value={bulkStatus}
          >
            <Option value={6}>Проверено</Option>
            <Option value={4}>Правки</Option>
          </Select>
          <Button type="primary" onClick={handleSubmit}>
            Готово
          </Button>
        </div>

        <div style={{ marginBottom: 16 }}>
          <Pagination
            total={pagination.total}
            showTotal={(total, range) => `${range[0]}-${range[1]} из ${total} записей`}
            defaultPageSize={600}
            current={pagination.current}
            onChange={handlePageChange}
          />
        </div>

        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={data}
          style={{ width: '100%' }}
          loading={loading}
          pagination={false}
          onChange={handleTableChange}
        />

        <div style={{ marginTop: 16 }}>
          <Pagination
            total={pagination.total}
            showTotal={(total, range) => `${range[0]}-${range[1]} из ${total} записей`}
            defaultPageSize={600}
            current={pagination.current}
            onChange={handlePageChange}
          />
        </div>

        {/* Модальное окно для отклонения */}
        <Modal
          title="Отклонить рендер"
          visible={rejectModalVisible}
          onCancel={handleModalCancel}
          footer={[
            <Button key="cancel" onClick={handleModalCancel}>
              Отмена
            </Button>,
            <Button key="save" type="primary" onClick={handleModalSave}>
              Сохранить
            </Button>,
          ]}
        >
          <div style={{ marginBottom: 16 }}>
            <span style={{ marginRight: 8 }}>Пригодно для рендера:</span>
            <Select
              placeholder="Выбрать"
              style={{ width: 200 }}
              value={modalIsSuitable}
              onChange={setModalIsSuitable}
            >
              <Option value={true}>Да</Option>
              <Option value={false}>Нет</Option>
            </Select>
          </div>
          {modalIsSuitable === false && (
            <>
              <div style={{ marginBottom: 16 }}>
                <span style={{ marginRight: 8 }}>Причины отклонения:</span>
                <Select
                  mode="multiple"
                  style={{ width: '100%' }}
                  placeholder="Выберите причины"
                  value={modalReasons}
                  onChange={setModalReasons}
                >
                  {rejectReasonOptions.map(option => (
                    <Option key={option.value} value={option.value}>
                      {option.label}
                    </Option>
                  ))}
                </Select>
              </div>
              <div>
                <TextArea
                  rows={3}
                  placeholder="Комментарий"
                  value={modalComment}
                  onChange={(e) => setModalComment(e.target.value)}
                />
              </div>
            </>
          )}
        </Modal>
      </Content>
    </Layout>
  );
};

export default SeniorRetoucherCheck;
