import React, { useState, useEffect } from 'react';
import { Layout, Table, Button, Modal, Input, Select, message, Spin, Pagination } from 'antd';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';
import { CopyOutlined, LinkOutlined, SaveOutlined } from '@ant-design/icons';

const { Content } = Layout;
const { Option } = Select;

// Список вариантов для причин отклонения
const reasonOptions = [
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

const GOOGLE_API_KEY = 'AIzaSyBGBcR20R_hQP_yNrfA_L2oWl-0G75BR84';

const RetoucherRenderCheck = ({ darkMode, setDarkMode }) => {
  // Состояния для таблицы
  const [tableData, setTableData] = useState([]);
  const [loadingTable, setLoadingTable] = useState(false);

  // Состояния пагинации (по умолчанию 600 записей на страницу)
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 600,
    total: 0,
  });

  // Состояния для модального окна "Отбор"
  const [isStartCheckModalVisible, setIsStartCheckModalVisible] = useState(false);
  const [startCheckData, setStartCheckData] = useState(null);
  const [startCheckLoading, setStartCheckLoading] = useState(false);
  const [modalIsSuitable, setModalIsSuitable] = useState(undefined);
  const [modalCheckResult, setModalCheckResult] = useState([]);
  const [modalCheckComment, setModalCheckComment] = useState('');

  // Состояния для модального окна "Проставить ссылки"
  const [isSetLinksModalVisible, setIsSetLinksModalVisible] = useState(false);
  const [googleLink, setGoogleLink] = useState('');
  const [setLinksLoading, setSetLinksLoading] = useState(false);
  const [emptyFolders, setEmptyFolders] = useState([]);

  // Функция для получения заголовков с токеном (django simple jwt, Bearer)
  const getAuthHeaders = () => {
    const token = localStorage.getItem('accessToken');
    return { headers: { Authorization: token ? `Bearer ${token}` : '' } };
  };

  // Функция для загрузки списка рендеров с пагинацией
  const fetchRenderList = async (page = pagination.current, pageSize = pagination.pageSize) => {
    setLoadingTable(true);
    try {
      const resp = await axios.get(
        `${API_BASE_URL}/rd/retoucher-render-list/?page=${page}&page_size=${pageSize}`,
        getAuthHeaders()
      );
      // Ожидается, что сервер вернёт { count, next, previous, results }
      setTableData(resp.data.results || []);
      setPagination(prev => ({
        ...prev,
        current: page,
        pageSize: pageSize,
        total: resp.data.count || 0,
      }));
    } catch (error) {
      message.error('Ошибка при загрузке списка рендеров');
    } finally {
      setLoadingTable(false);
    }
  };

  useEffect(() => {
    document.title = 'Проверка и рендеры';
    fetchRenderList();
  }, []);

  // Обновление конкретной записи (если IsSuitable === false, причины отклонения обязательны)
  const handleSave = async (record) => {
    if (record.IsSuitable === false && (!record.CheckResult || record.CheckResult.length === 0)) {
      message.error("Поле 'Причины отклонения' обязательно для заполнения");
      return;
    }
    const payload = {
      CheckResult: record.CheckResult ? record.CheckResult.map(item => item.id) : [],
      CheckComment: record.CheckComment,
      IsSuitable: record.IsSuitable,
      RetouchPhotosLink: record.RetouchPhotosLink,
    };
    try {
      await axios.patch(`${API_BASE_URL}/rd/update-render/${record.id}/`, payload, getAuthHeaders());
      message.success('Запись успешно обновлена');
      fetchRenderList();
    } catch (error) {
      message.error('Ошибка при обновлении записи');
    }
  };

  // Обработка изменений в таблице
  const handleTableChange = (id, field, value) => {
    const newData = tableData.map(item => {
      if (item.id === id) {
        return { ...item, [field]: value };
      }
      return item;
    });
    setTableData(newData);
  };

  // Определяем колонки таблицы
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
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
      key: 'comments',
      render: (text, record) => (
        <div>
          {record.product.ModerationComment} {record.product.RejectComment}
        </div>
      ),
    },
    {
      title: 'Пригодно для рендера',
      key: 'IsSuitable',
      render: (text, record) => (
        <Select
          value={
            record.IsSuitable === true
              ? 'true'
              : record.IsSuitable === false
              ? 'false'
              : undefined
          }
          onChange={(value) =>
            handleTableChange(record.id, 'IsSuitable', value === 'true')
          }
          style={{ width: 120 }}
          placeholder="Выбрать"
        >
          <Option value="true" style={{ color: 'green' }}>
            Да
          </Option>
          <Option value="false" style={{ color: 'red' }}>
            Нет
          </Option>
        </Select>
      ),
    },
    {
      title: 'Причины отклонения',
      key: 'CheckResult',
      render: (text, record) => (
        <Select
          mode="multiple"
          value={record.CheckResult ? record.CheckResult.map(item => item.id) : []}
          onChange={(value) => {
            const selected = value.map(val => ({ id: val }));
            handleTableChange(record.id, 'CheckResult', selected);
          }}
          style={{ width: 200 }}
          placeholder="Выбрать причины"
        >
          {reasonOptions.map(option => (
            <Option key={option.value} value={option.value}>
              {option.label}
            </Option>
          ))}
        </Select>
      ),
    },
    {
      title: 'Комментарий',
      key: 'CheckComment',
      render: (text, record) => (
        <Input
          value={record.CheckComment}
          onChange={(e) => handleTableChange(record.id, 'CheckComment', e.target.value)}
          placeholder="Комментарий"
        />
      ),
    },
    {
      title: 'Ссылка на фото',
      key: 'RetouchPhotosLink',
      render: (text, record) => (
        <Input
          value={record.RetouchPhotosLink}
          onChange={(e) =>
            handleTableChange(record.id, 'RetouchPhotosLink', e.target.value)
          }
          placeholder="Ссылка"
        />
      ),
    },
    {
      title: 'Сохранить',
      key: 'save',
      render: (text, record) => (
        <Button type="primary" icon={<SaveOutlined />} onClick={() => handleSave(record)} />
      ),
    },
  ];

  // Обработка модального окна "Отбор"
  const handleStartCheck = async () => {
    if (isStartCheckModalVisible || startCheckLoading) return;
    setIsStartCheckModalVisible(true);
    loadStartCheckData();
  };

  const loadStartCheckData = async () => {
    setStartCheckLoading(true);
    try {
      const resp = await axios.post(`${API_BASE_URL}/rd/start-check/`, null, getAuthHeaders());
      setStartCheckData(resp.data);
      // Сброс локальных состояний для модального окна
      setModalIsSuitable(undefined);
      setModalCheckResult([]);
      setModalCheckComment('');
    } catch (error) {
      const serverError =
      error.response && error.response.data && error.response.data.error
        ? error.response.data.error
        : 'Ошибка при загрузке данных для отбора';
      message.error(serverError);
      setIsStartCheckModalVisible(false);
    } finally {
      setStartCheckLoading(false);
    }
  };

  // Отправка данных из модального окна "Отбор" с обновлением записи и без закрытия окна
  const handleStartCheckNext = async () => {
    if (modalIsSuitable === undefined) {
      message.error('Укажите, подходит ли штрихкод для рендера');
      return;
    }
    if (modalIsSuitable === false && modalCheckResult.length === 0) {
      message.error('При выборе "Нет" обязательно заполните поле "Причины отклонения"');
      return;
    }
    const payload = {
      CheckResult: modalCheckResult,
      CheckComment: modalCheckComment,
      IsSuitable: modalIsSuitable,
      RetouchPhotosLink: '',
    };
    try {
      await axios.patch(`${API_BASE_URL}/rd/update-render/${startCheckData.id}/`, payload, getAuthHeaders());
      message.success('Запись успешно обновлена');
      // Обновляем данные, запрашивая новую запись, не закрывая окно
      loadStartCheckData();
      fetchRenderList();
    } catch (error) {
      message.error('Ошибка при обновлении данных');
    }
  };

  // Отправка данных из модального окна "Отбор" с завершением (закрытие окна)
  const handleFinishCheck = async () => {
    if (modalIsSuitable === undefined) {
      message.error('Укажите, подходит ли штрихкод для рендера');
      return;
    }
    if (modalIsSuitable === false && modalCheckResult.length === 0) {
      message.error('При выборе "Нет" обязательно заполните поле "Причины отклонения"');
      return;
    }
    const payload = {
      CheckResult: modalCheckResult,
      CheckComment: modalCheckComment,
      IsSuitable: modalIsSuitable,
      RetouchPhotosLink: '',
    };
    try {
      await axios.patch(`${API_BASE_URL}/rd/update-render/${startCheckData.id}/`, payload, getAuthHeaders());
      message.success('Запись успешно обновлена');
      // Завершаем отбор, закрывая модальное окно
      setIsStartCheckModalVisible(false);
      fetchRenderList();
    } catch (error) {
      message.error('Ошибка при обновлении данных');
    }
  };

  // Функции для копирования штрихкода и открытия ссылки проверки
  const handleCopyBarcode = (barcode) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(barcode)
        .then(() => {
          message.success('Штрихкод скопирован');
        })
        .catch(err => {
          console.error('Не удалось скопировать: ', err);
          message.error('Не удалось скопировать штрихкод');
        });
    } else {
      message.error('Копирование не поддерживается в этом браузере или небезопасном контексте (HTTP). Используйте HTTPS или localhost.');
      // Можно попытаться использовать устаревший document.execCommand('copy'), но он сложнее и не рекомендуется.
    }
  };

  const handleOpenLink = (shopId, productId) => {
    const url = `https://admin.teez.kz/ru/product-verification/shop/${shopId}/product/${productId}`;
    window.open(url, '_blank');
  };

  // Обработка модального окна "Проставить ссылки"
  const handleSetLinks = () => {
    setEmptyFolders([]);
    setIsSetLinksModalVisible(true);
  };

  // Функция для получения ссылок из Google Drive с проверкой наличия файлов
  const getFolderLinks = async (parentFolderId) => {
    const driveUrl = 'https://www.googleapis.com/drive/v3/files';
    const paramsFolders = {
      q: `'${parentFolderId}' in parents and mimeType='application/vnd.google-apps.folder' and trashed = false`,
      includeItemsFromAllDrives: true,
      supportsAllDrives: true,
      fields: 'files(id, name)',
      key: GOOGLE_API_KEY,
    };

    const resFolders = await axios.get(driveUrl, { params: paramsFolders });
    const childFolders = resFolders.data.files || [];
    const folderMap = {};
    childFolders.forEach(folder => {
      folderMap[folder.name] = folder.id;
    });

    const folderLinks = {};
    const emptyFolderBarcodes = [];
    const suitableItems = tableData.filter(item => item.IsSuitable === true);
    for (let item of suitableItems) {
      const barcode = item.product.barcode;
      if (folderMap[barcode]) {
        const childFolderId = folderMap[barcode];
        const paramsFiles = {
          q: `'${childFolderId}' in parents and trashed = false`,
          includeItemsFromAllDrives: true,
          supportsAllDrives: true,
          fields: 'files(id)',
          key: GOOGLE_API_KEY,
        };
        const resFiles = await axios.get(driveUrl, { params: paramsFiles });
        const files = resFiles.data.files || [];
        if (files.length > 0) {
          folderLinks[barcode] = `https://drive.google.com/drive/folders/${childFolderId}`;
        } else {
          emptyFolderBarcodes.push(barcode);
        }
      }
    }
    return { folderLinks, emptyFolderBarcodes };
  };

  // Отправка данных для массового обновления ссылок
  const submitSetLinks = async () => {
    if (!googleLink) {
      message.error('Введите ссылку');
      return;
    }
    const match = googleLink.match(/folders\/([^/]+)/);
    if (!match) {
      message.error('Неверный формат ссылки');
      return;
    }
    const parentFolderId = match[1];
    setSetLinksLoading(true);
    try {
      const { folderLinks, emptyFolderBarcodes } = await getFolderLinks(parentFolderId);
      setEmptyFolders(emptyFolderBarcodes);
      const updateData = tableData
        .filter(item => item.IsSuitable === true && folderLinks[item.product.barcode])
        .map(item => ({
          id: item.id,
          RetouchPhotosLink: folderLinks[item.product.barcode],
        }));

      if (updateData.length > 0) {
        await axios.post(`${API_BASE_URL}/rd/mass-update-retouchlinks/`, updateData, getAuthHeaders());
        message.success('Ссылки успешно обновлены');
      } else {
        message.info('Нет записей для обновления ссылок');
      }
      fetchRenderList();
    } catch (error) {
      message.error('Ошибка при обновлении ссылок');
    } finally {
      setSetLinksLoading(false);
    }
  };

  // Обработка кнопки "Отправить на проверку"
  const handleSendForCheck = async () => {
    try {
      const resp = await axios.post(`${API_BASE_URL}/rd/send-for-check/`, null, getAuthHeaders());
      if (resp.data.message) {
        message.success(resp.data.message);
      }
      fetchRenderList();
    } catch (error) {
      message.error('Ошибка при отправке на проверку');
    }
  };

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16, minHeight: '100vh' }}>
        <h2>Проверка и рендеры</h2>
        <div
          style={{
            marginBottom: 16,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Button
            type="primary"
            onClick={handleStartCheck}
            disabled={startCheckLoading}
          >
            Начать отбор
          </Button>
          <div>
            <Button
              type="primary"
              onClick={handleSetLinks}
              style={{ marginRight: 8 }}
            >
              Проставить ссылки
            </Button>
            <Button type="primary" onClick={handleSendForCheck}>
              Отправить на проверку
            </Button>
          </div>
        </div>
        <Pagination
          total={pagination.total}
          current={pagination.current}
          pageSize={pagination.pageSize}
          onChange={(page, pageSize) => fetchRenderList(page, pageSize)}
          showTotal={(total, range) => `${range[0]}-${range[1]} из ${total} записей`}
          style={{ marginBottom: 16 }}
        />
        {loadingTable ? (
          <Spin />
        ) : (
          <Table
            dataSource={tableData}
            columns={columns}
            rowKey="id"
            style={{ width: '100%' }}
            pagination={false}
          />
        )}

        <Modal
          title="Отбор"
          visible={isStartCheckModalVisible}
          onCancel={() => {
            setIsStartCheckModalVisible(false);
            fetchRenderList();
          }}
          footer={null}
          maskClosable={false}
          width="25vw"
          bodyStyle={{ minHeight: '50vh' }}
        >
          {startCheckLoading || !startCheckData ? (
            <Spin />
          ) : (
            <div style={{justifyContent: 'center'}}>
              <div style={{ marginBottom: 16, justifyContent: 'center' }}>
                <strong>Подходящие: </strong>
                {startCheckData.accepted} &nbsp;
                <strong>Отклоненные: </strong>
                {startCheckData.declined}
              </div>
              <div style={{ marginBottom: 16 }}>
                <Input
                  value={startCheckData.Barcode}
                  readOnly
                  addonAfter={
                    <>
                      <Button
                        icon={<CopyOutlined />}
                        onClick={() => handleCopyBarcode(startCheckData.Barcode)}
                      />
                      <Button
                        icon={<LinkOutlined />}
                        onClick={() => {
                          // handleCopyBarcode(startCheckData.Barcode);
                          handleOpenLink(startCheckData.ShopID, startCheckData.ProductID);
                        }}
                      />
                    </>
                  }
                />
              </div>
              <div style={{ marginBottom: 16 }}>
                <Select
                  value={modalIsSuitable}
                  onChange={(value) => setModalIsSuitable(value)}
                  style={{ width: "22vw" }}
                  placeholder="Подходит для рендера"
                >
                  <Option value={true} style={{ color: 'green' }}>
                    Да
                  </Option>
                  <Option value={false} style={{ color: 'red' }}>
                    Нет
                  </Option>
                </Select>
              </div>
              {modalIsSuitable === false && (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <Select
                      mode="multiple"
                      value={modalCheckResult}
                      onChange={(value) => setModalCheckResult(value)}
                      style={{ width: '100%' }}
                      placeholder="Причины отклонения"
                    >
                      {reasonOptions.map(option => (
                        <Option key={option.value} value={option.value}>
                          {option.label}
                        </Option>
                      ))}
                    </Select>
                  </div>
                  <div style={{ marginBottom: 16 }}>
                    <Input
                      value={modalCheckComment}
                      onChange={(e) => setModalCheckComment(e.target.value)}
                      placeholder="Комментарий"
                    />
                  </div>
                </>
              )}
              <Button type="primary" onClick={handleStartCheckNext}>
                Далее
              </Button>
              <Button type="default" style={{ marginLeft: 8 }} onClick={handleFinishCheck}>
                Завершить
              </Button>
            </div>
          )}
        </Modal>

        <Modal
          title="Проставить ссылки"
          visible={isSetLinksModalVisible}
          onCancel={() => setIsSetLinksModalVisible(false)}
          footer={null}
        >
          <div style={{ marginBottom: 16 }}>
            <Input
              value={googleLink}
              onChange={(e) => setGoogleLink(e.target.value)}
              placeholder="Введите ссылку (пример: https://drive.google.com/drive/folders/ID)"
            />
          </div>
          {emptyFolders.length > 0 && (
            <div style={{ marginBottom: 16, color: 'red' }}>
              Пустые папки: {emptyFolders.join(', ')}
            </div>
          )}
          <Button type="primary" loading={setLinksLoading} onClick={submitSetLinks}>
            Применить
          </Button>
        </Modal>
      </Content>
    </Layout>
  );
};

export default RetoucherRenderCheck;
