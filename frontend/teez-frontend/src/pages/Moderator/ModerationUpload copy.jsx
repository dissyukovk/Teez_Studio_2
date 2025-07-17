import React, { useState, useEffect } from 'react';
import {
  Layout,
  Table,
  Button,
  Modal,
  message,
  Typography,
  Checkbox,
  Input,
  Select,
  Space
} from 'antd';
import { CopyOutlined, LinkOutlined, SaveOutlined, DownloadOutlined } from '@ant-design/icons';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';

const { Content } = Layout;
const { Title, Text } = Typography;
const { Option } = Select;

// Список причин отклонения с бэка
const rejectionReasonsOptions = [
  { id: 30, name: "Другое" },
  { id: 9, name: "Нет кадра с лицевой стороны" },
  { id: 8, name: "Техническая ошибка админки" },
  { id: 7, name: "Техническая ошибка ссылки (404 и др)" },
  { id: 6, name: "Фото соответствует регламенту" },
  { id: 5, name: "Некорректное соотношение/размер" },
  { id: 4, name: "Пустая папка" },
  { id: 2, name: "Фото не соответствует карточке" },
  { id: 1, name: "Плохое качество фото" }
];

const ModerationUpload = ({ darkMode, setDarkMode }) => {
  // Состояние для таблицы
  const [tableData, setTableData] = useState([]);
  const [tableLoading, setTableLoading] = useState(false);

  // Состояние для модального окна
  const [modalVisible, setModalVisible] = useState(false);
  const [modalData, setModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);

  // Состояние формы модального окна
  const [modalIsUploaded, setModalIsUploaded] = useState(null);
  const [modalReturnToRender, setModalReturnToRender] = useState(false);
  const [modalRejectedReasons, setModalRejectedReasons] = useState([]);
  const [modalRejectComment, setModalRejectComment] = useState('');

  const [isDownloading, setIsDownloading] = useState(false);

  const GOOGLE_DRIVE_API_KEY = 'AIzaSyBGBcR20R_hQP_yNrfA_L2oWl-0G75BR84';

  // Заголовок страницы
  useEffect(() => {
    document.title = 'Загрузка рендеров';
    fetchTableData();
  }, []);

  // Функция загрузки данных таблицы
  const fetchTableData = async () => {
    setTableLoading(true);
    try {
      const token = localStorage.getItem('accessToken');
      const response = await axios.get(`${API_BASE_URL}/rd/moderator_list_by_date/`, {
        headers: { Authorization: token ? `Bearer ${token}` : '' }
      });
      // Ожидается, что с сервера придёт объект { uploads, total_count, uploaded_count }
      setTableData(response.data.uploads);
    } catch (error) {
      message.error(error.response?.data?.error || 'Ошибка при загрузке данных');
    } finally {
      setTableLoading(false);
    }
  };

  // Функция обновления поля для строки таблицы
  const updateRowField = (record, field, value) => {
    setTableData(prevData =>
      prevData.map(item =>
        item.ModerationUploadId === record.ModerationUploadId
          ? { ...item, [field]: value }
          : item
      )
    );
  };

  // Функция сохранения данных строки таблицы
  const handleSave = async (record) => {
    const token = localStorage.getItem('accessToken');
    // Если "Загружено" поставлено в false, значит IsRejected=true
    const payload = {
      ModerationUploadId: record.ModerationUploadId,
      IsUploaded: record.IsUploaded,
      IsRejected: record.IsUploaded ? false : true,
      RejectComment: record.RejectComment || "",
      ReturnToRender: record.ReturnToRender || false,
      // Передаём массив id причин отклонения
      RejectedReason: record.RejectedReason ? record.RejectedReason.map(item => item.id) : []
    };

    try {
      await axios.post(`${API_BASE_URL}/rd/moderation_upload_edit/`, payload, {
        headers: { Authorization: token ? `Bearer ${token}` : '' }
      });
      message.success('Данные сохранены');
      // После сохранения можно перезагрузить таблицу
      fetchTableData();
    } catch (error) {
      message.error(error.response?.data?.error || 'Ошибка при сохранении данных');
    }
  };

  // Определяем колонки для таблицы
  const columns = [
    {
      title: 'ID',
      dataIndex: 'ModerationUploadId',
      key: 'ModerationUploadId'
    },
    {
      title: 'Штрихкод',
      dataIndex: 'Barcode',
      key: 'Barcode'
    },
    {
      title: 'Наименование',
      dataIndex: 'Name',
      key: 'Name'
    },
    {
      title: 'Ссылка на фото',
      dataIndex: 'RetouchPhotosLink',
      key: 'RetouchPhotosLink',
      render: (text) => (
        <a href={text} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      )
    },
    {
      title: 'Загружено',
      dataIndex: 'IsUploaded',
      key: 'IsUploaded',
      render: (text, record) => (
        <Checkbox
          checked={record.IsUploaded}
          onChange={(e) => {
            updateRowField(record, 'IsUploaded', e.target.checked);
            // Если снята галочка, то автоматически считаем IsRejected=true
            if (!e.target.checked) {
              updateRowField(record, 'IsRejected', true);
            } else {
              updateRowField(record, 'IsRejected', false);
            }
          }}
        />
      )
    },
    {
      title: 'Вернуть фотостудии',
      dataIndex: 'ReturnToRender',
      key: 'ReturnToRender',
      render: (text, record) => (
        <Checkbox
          checked={record.ReturnToRender}
          onChange={(e) => updateRowField(record, 'ReturnToRender', e.target.checked)}
        />
      )
    },
    {
      title: 'Причины отклонения',
      dataIndex: 'RejectedReason',
      key: 'RejectedReason',
      render: (reasons, record) => {
        // Инициализируем значения как массив id
        const initialValue = reasons ? reasons.map(r => r.id) : [];
        return (
          <Select
            mode="multiple"
            style={{ width: 200 }}
            placeholder="Выберите причины"
            value={initialValue}
            onChange={(value) => {
              // Для таблицы можно сохранить как массив объектов по id
              const selected = rejectionReasonsOptions.filter(item => value.includes(item.id));
              updateRowField(record, 'RejectedReason', selected);
            }}
          >
            {rejectionReasonsOptions.map(reason => (
              <Option key={reason.id} value={reason.id}>
                {reason.name}
              </Option>
            ))}
          </Select>
        );
      }
    },
    {
      title: 'Комментарий отклонения',
      dataIndex: 'RejectComment',
      key: 'RejectComment',
      render: (text, record) => (
        <Input
          value={record.RejectComment}
          onChange={(e) => updateRowField(record, 'RejectComment', e.target.value)}
          style={{ width: 200 }}
        />
      )
    },
    {
      title: 'Сохранить',
      key: 'save',
      render: (text, record) => (
        <Button
          icon={<SaveOutlined />}
          onClick={() => handleSave(record)}
        />
      )
    }
  ];

  // Функция открытия модального окна "Начать загрузку"
  const openModal = async () => {
    if (modalLoading) return;
    setModalLoading(true);
    const token = localStorage.getItem('accessToken');
    try {
      const response = await axios.post(`${API_BASE_URL}/rd/moderator-upload-start/`, {}, {
        headers: { Authorization: token ? `Bearer ${token}` : '' }
      });
      setModalData(response.data);
      // Устанавливаем начальные значения для формы
      setModalIsUploaded(null);
      setModalReturnToRender(false);
      setModalRejectedReasons([]);
      setModalRejectComment('');
      setModalVisible(true);
    } catch (error) {
      if (error.response && error.response.status === 404) {
        message.error(error.response.data.message || 'Рендеры на загрузку закончились');
      } else {
        message.error(error.response?.data?.error || 'Ошибка при запуске загрузки');
      }
    } finally {
      setModalLoading(false);
    }
  };

  // Функция обработки отправки данных в модальном окне
  const handleModalSubmit = async (mode) => {
    // Проверка: если загружено = false, то обязательно должны быть указаны причины отклонения
    if (!modalIsUploaded && modalRejectedReasons.length === 0) {
      message.error('При незагруженном статусе необходимо указать причины отклонения');
      return;
    }
    const token = localStorage.getItem('accessToken');
    const payload = {
      ModerationUploadId: modalData.ModerationUploadId,
      IsUploaded: modalIsUploaded,
      // Если загружено = false, то считаем, что IsRejected = true
      IsRejected: modalIsUploaded ? false : true,
      RejectComment: modalRejectComment,
      ReturnToRender: modalReturnToRender,
      RejectedReason: modalRejectedReasons
    };
    try {
      await axios.post(`${API_BASE_URL}/rd/moderation_upload_result/`, payload, {
        headers: { Authorization: token ? `Bearer ${token}` : '' }
      });
      message.success('Данные загружены успешно');
      if (mode === 'next') {
        // Для кнопки "Далее" запрашиваем следующий рендер
        openModal();
      } else {
        // Для кнопки "завершить" закрываем модалку и обновляем таблицу
        setModalVisible(false);
        fetchTableData();
      }
    } catch (error) {
      message.error(error.response?.data?.error || 'Ошибка при сохранении результатов');
    }
  };

  // Функция копирования штрихкода
  const handleCopyBarcode = (barcode) => {
    navigator.clipboard.writeText(barcode)
      .then(() => message.success('Штрихкод скопирован'))
      .catch(() => message.error('Ошибка копирования'));
  };

  // Функция для извлечения ID папки из URL (остается без изменений)
  const extractFolderId = (url) => {
    if (!url) return null;
    try {
      const match = url.match(/folders\/([a-zA-Z0-9_-]+)/);
      if (match && match[1]) {
        return match[1];
      }
      const urlParts = url.split('/');
      const folderId = urlParts[urlParts.length - 1].split('?')[0];
      if (folderId && folderId.length > 15) {
         return folderId;
      }
      return null;
    } catch (error) {
      console.error("Ошибка извлечения ID папки:", error);
      return null;
    }
  };

  // --- Обновленная функция скачивания БЕЗ ZIP ---
  const handleDownloadAllFilesIndividually = async (folderUrl) => {
    if (!folderUrl) {
      message.error('Ссылка на папку Google Drive отсутствует.');
      return;
    }

    const folderId = extractFolderId(folderUrl);
    if (!folderId) {
      message.error('Не удалось извлечь ID папки из ссылки. Проверьте формат ссылки.');
      return;
    }

    setIsDownloading(true);
    message.loading({ content: 'Получение списка файлов...', key: 'downloadStatus', duration: 0 }); // duration 0 для ручного закрытия

    try {
      // 1. Получаем список файлов (с поддержкой Shared Drives)
      const listUrl = `https://www.googleapis.com/drive/v3/files?q='${folderId}' in parents and trashed=false&fields=files(id, name, mimeType)&key=${GOOGLE_DRIVE_API_KEY}&includeItemsFromAllDrives=true&supportsAllDrives=true`; // <-- Добавлены параметры для Shared Drive
      const listResponse = await fetch(listUrl);

      if (!listResponse.ok) {
        const errorData = await listResponse.json();
        console.error("Ошибка API Google Drive (list):", errorData);
        throw new Error(`Ошибка получения списка файлов: ${errorData.error?.message || listResponse.statusText} (${listResponse.status})`);
      }

      const { files } = await listResponse.json();

      if (!files || files.length === 0) {
        message.warning({ content: 'Папка пуста или нет доступных файлов.', key: 'downloadStatus', duration: 3 });
        setIsDownloading(false);
        return;
      }

      message.info({ content: `Найдено файлов: ${files.length}. Начинаю скачивание по одному (может потребоваться подтверждение для каждого файла)...`, key: 'downloadStatus', duration: 5 });

      // 2. Скачиваем каждый файл отдельно
      let filesDownloadedCount = 0;
      let filesSkippedCount = 0;

      // Небольшая задержка между инициированием загрузок, чтобы не перегружать браузер
      const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

      for (const file of files) {
        // Пропускаем папки и файлы Google Workspace
        if (file.mimeType.startsWith('application/vnd.google-apps') || file.mimeType === 'application/vnd.google-apps.folder') {
            console.warn(`Пропущен файл/папка Google Workspace: ${file.name} (${file.mimeType})`);
            filesSkippedCount++;
            continue;
        }

        const downloadUrl = `https://www.googleapis.com/drive/v3/files/${file.id}?alt=media&key=${GOOGLE_DRIVE_API_KEY}&supportsAllDrives=true`; // <-- Добавлен supportsAllDrives
        try {
            message.loading({ content: `Скачиваю файл: ${file.name}...`, key: `download_${file.id}`, duration: 0 });
            const fileResponse = await fetch(downloadUrl);
            if (!fileResponse.ok) {
                console.error(`Ошибка скачивания файла ${file.name}: ${fileResponse.statusText} (${fileResponse.status})`);
                message.error({ content: `Ошибка скачивания ${file.name}: ${fileResponse.status}`, key: `download_${file.id}`, duration: 3 });
                filesSkippedCount++;
                continue; // Переходим к следующему файлу
            }
            const blob = await fileResponse.blob();

            // --- Метод для инициирования скачивания файла ---
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', file.name); // Устанавливаем имя файла
            document.body.appendChild(link); // Добавляем ссылку в DOM (важно для Firefox)
            link.click(); // Имитируем клик
            link.parentNode.removeChild(link); // Удаляем ссылку из DOM
            window.URL.revokeObjectURL(url); // Освобождаем память
            // --- Конец метода скачивания ---

            message.success({ content: `Файл ${file.name} начал загружаться.`, key: `download_${file.id}`, duration: 2 });
            filesDownloadedCount++;
            console.log(`Инициирована загрузка файла: ${file.name}`);

            // Добавляем небольшую задержку перед следующим файлом
            await delay(500); // 0.5 секунды задержки

        } catch (fileError) {
             console.error(`Критическая ошибка при скачивании файла ${file.name}:`, fileError);
             message.error({ content: `Ошибка сети при скачивании ${file.name}`, key: `download_${file.id}`, duration: 3 });
             filesSkippedCount++;
        }
      }

      // 3. Финальное сообщение
       message.destroy('downloadStatus'); // Убираем начальное сообщение о загрузке
       let finalMessage = '';
       if (filesDownloadedCount > 0) {
           finalMessage = `Инициирована загрузка ${filesDownloadedCount} файлов.`;
           if (filesSkippedCount > 0) {
               finalMessage += ` Пропущено: ${filesSkippedCount}.`;
           }
           message.success({ content: finalMessage, duration: 5 });
       } else if (filesSkippedCount > 0) {
           message.warning({ content: `Не удалось начать загрузку ни одного файла. Пропущено: ${filesSkippedCount}. Проверьте консоль.`, duration: 5 });
       } else {
           message.error({ content: 'Не удалось скачать файлы. Неизвестная ошибка.', duration: 5 });
       }

    } catch (error) {
      console.error('Полная ошибка при загрузке файлов:', error);
      message.error({ content: `Ошибка: ${error.message}. Подробности в консоли.`, key: 'downloadStatus', duration: 5 });
    } finally {
      setIsDownloading(false);
      // Убедимся, что все сообщения о загрузке отдельных файлов закрыты (на случай ошибок)
       setTimeout(() => message.destroy(), 1000); // Закрыть все сообщения через секунду
    }
  };


  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content
        style={{
          padding: 16,
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <Title level={2}>Загрузка рендеров</Title>
        <Button type="primary" onClick={openModal} style={{ marginBottom: 16 }} loading={modalLoading}>
          Начать загрузку
        </Button>
        <Table
          dataSource={tableData}
          columns={columns}
          rowKey="ModerationUploadId"
          loading={tableLoading}
        />
        {/* Модальное окно для загрузки рендеров */}
        <Modal
          visible={modalVisible}
          title="Загрузка рендеров"
          onCancel={() => { setModalVisible(false); fetchTableData(); }}
          footer={null}
          width="30%"
          style={{ height: '50vh' }}
          maskClosable={false}
        >
          {modalData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Поле штрихкода с иконками */}
              <Space>
                <Input
                  value={modalData.Barcode}
                  readOnly
                  style={{ width: 200 }}
                />
                <CopyOutlined onClick={() => handleCopyBarcode(modalData.Barcode)} style={{ cursor: 'pointer' }} />
                <LinkOutlined
                  onClick={() => window.open(`https://admin.teez.kz/ru/sku-photo-verification/shop/${modalData.ShopID}/product/${modalData.ProductID}/sku`, '_blank')}
                  style={{ cursor: 'pointer' }}
                />
              </Space>
              {/* Ссылка на фото */}
              <div>
                <Text strong>Ссылка на фото: </Text>
                {modalData.RetouchPhotosLink ? (
                  <>
                    <a href={modalData.RetouchPhotosLink} target="_blank" rel="noopener noreferrer">
                        {modalData.RetouchPhotosLink}
                    </a>
                    {/* Используем новую функцию handleDownloadAllFilesIndividually */}
                    <Button
                        type="primary"
                        icon={<DownloadOutlined />}
                        onClick={() => handleDownloadAllFilesIndividually(modalData.RetouchPhotosLink)} // <--- Вызываем новую функцию
                        loading={isDownloading}
                        disabled={isDownloading}
                        style={{ marginLeft: '10px' }}
                    >
                        Скачать все файлы
                    </Button>
                  </>
                ) : (
                    <Text type="secondary">Ссылка отсутствует</Text>
                )}
              </div>
              {/* Выбор "Загружено" */}
              <div>
                <Typography.Text strong>Загружено: </Typography.Text>
                <Select
                  value={modalIsUploaded}
                  onChange={(value) => setModalIsUploaded(value)}
                  style={{ width: 120 }}
                >
                  <Option value={true}>Да</Option>
                  <Option value={false}>Нет</Option>
                </Select>
              </div>
              {/* Если "Загружено" = Нет, отображаем доп. поля */}
              {!modalIsUploaded && (
                <>
                  <div>
                    <Typography.Text strong>Причины отклонения:</Typography.Text>
                    <Select
                      mode="multiple"
                      style={{ width: '100%' }}
                      placeholder="Выберите причины"
                      value={modalRejectedReasons}
                      onChange={(value) => setModalRejectedReasons(value)}
                    >
                      {rejectionReasonsOptions.map(reason => (
                        <Option key={reason.id} value={reason.id}>
                          {reason.name}
                        </Option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Typography.Text strong>Комментарий отклонения:</Typography.Text>
                    <Input
                      value={modalRejectComment}
                      onChange={(e) => setModalRejectComment(e.target.value)}
                    />
                  </div>
                </>
              )}
              {/* Кнопки */}
              <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
                <Button onClick={() => handleModalSubmit('finish')} type="default">
                  завершить
                </Button>
                <Button onClick={() => handleModalSubmit('next')} type="primary">
                  Далее
                </Button>
              </Space>
            </div>
          )}
        </Modal>
      </Content>
    </Layout>
  );
};

export default ModerationUpload;
