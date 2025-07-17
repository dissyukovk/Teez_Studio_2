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

const RetoucherRenderEdit = ({ darkMode, setDarkMode }) => {
  // Состояния для таблицы
  const [tableData, setTableData] = useState([]);
  const [loadingTable, setLoadingTable] = useState(false);

  // Состояния пагинации (по умолчанию 600 записей на страницу)
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 600,
    total: 0,
  });

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
        `${API_BASE_URL}/rd/retoucher-render-edit-list/?page=${page}&page_size=${pageSize}`,
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
    document.title = 'Правки по рендерам';
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
      await axios.patch(`${API_BASE_URL}/rd/update-render-edit/${record.id}/`, payload, getAuthHeaders());
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
      title: 'Комментарий правки',
      key: 'editcomment',
      render: (text, record) => (
        <div>
          {record.RetouchSeniorComment} {record.ModerationComment}
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

  // Обработка модального окна "Проставить ссылки"
  const handleSetLinks = () => {
    // Сброс пустых папок при открытии
    setEmptyFolders([]);
    setIsSetLinksModalVisible(true);
  };

  // Функция для получения ссылок из Google Drive с проверкой наличия файлов
  const getFolderLinks = async (parentFolderId) => {
    const driveUrl = 'https://www.googleapis.com/drive/v3/files';
    // Запрос на получение всех дочерних папок из родительской
    const paramsFolders = {
      q: `'${parentFolderId}' in parents and mimeType='application/vnd.google-apps.folder' and trashed = false`,
      includeItemsFromAllDrives: true,
      supportsAllDrives: true,
      fields: 'files(id, name)',
      key: GOOGLE_API_KEY,
    };

    const resFolders = await axios.get(driveUrl, { params: paramsFolders });
    const childFolders = resFolders.data.files || [];
    // Создаем маппинг: имя папки => id
    const folderMap = {};
    childFolders.forEach(folder => {
      folderMap[folder.name] = folder.id;
    });

    const folderLinks = {};
    const emptyFolderBarcodes = [];
    // Для каждой записи с IsSuitable === true ищем папку с именем = штрихкод
    const suitableItems = tableData.filter(item => item.IsSuitable === true);
    for (let item of suitableItems) {
      const barcode = item.product.barcode;
      if (folderMap[barcode]) {
        const childFolderId = folderMap[barcode];
        // Проверяем наличие файлов внутри найденной папки
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
      setEmptyFolders(emptyFolderBarcodes); // сохраняем для отображения в модальном окне

      // Формируем данные для обновления только для тех записей, для которых найдена ссылка
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
      // Не закрываем модальное окно, чтобы пользователь видел список пустых папок
      fetchRenderList();
    } catch (error) {
      message.error('Ошибка при обновлении ссылок');
    } finally {
      setSetLinksLoading(false);
    }
  };

  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16, minHeight: '100vh' }}>
        <h2>Правки по рендерам</h2>
        <div
          style={{
            marginBottom: 16,
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'right',
          }}
        >
          <div>
            <Button
              type="primary"
              onClick={handleSetLinks}
              style={{ marginRight: 8 }}
            >
              Проставить ссылки
            </Button>
          </div>
        </div>
        {/* Внешний пагинатор */}
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

        {/* Модальное окно "Проставить ссылки" */}
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

export default RetoucherRenderEdit;
