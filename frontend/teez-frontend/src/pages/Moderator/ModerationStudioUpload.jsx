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
  Space,
  Spin
} from 'antd';
import { CopyOutlined, LinkOutlined, SaveOutlined, DownloadOutlined } from '@ant-design/icons';
import axios from 'axios'; // Убедитесь, что axios импортирован
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config'; // Убедитесь, что API_BASE_URL импортирован

const { Content } = Layout;
const { Title, Text } = Typography;
const { Option } = Select;

// Список причин отклонения с бэка (остается без изменений)
const rejectionReasonsOptions = [
    // ... (ваш список причин)
     { id: 30, name: "Другое" },
     { id: 8, name: "Техническая ошибка админки" },
     { id: 7, name: "Техническая ошибка ссылки (404 и др)" },
     { id: 6, name: "Фото соответствует регламенту" },
     { id: 5, name: "Некорректное соотношение/размер" },
     { id: 4, name: "Пустая папка" },
     { id: 1, name: "Брак по фото" }
];

const ModerationStudioUpload = ({ darkMode, setDarkMode }) => {
  // --- Состояния компонента (остаются без изменений) ---
  const [tableData, setTableData] = useState([]);
  const [tableLoading, setTableLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(null);
  const [uploadedCount, setUploadedCount] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [modalData, setModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalIsUploaded, setModalIsUploaded] = useState(null);
  const [modalReturnToRender, setModalReturnToRender] = useState(false);
  const [modalRejectedReasons, setModalRejectedReasons] = useState([]);
  const [modalRejectComment, setModalRejectComment] = useState('');
  const [isDownloading, setIsDownloading] = useState(false);

  // --- !!! УДАЛЕНО: Жестко закодированный ключ больше не нужен !!! ---
  // const GOOGLE_DRIVE_API_KEY = 'AIzaSyBGBcR20R_hQP_yNrfA_L2oWl-0G75BR84';

  useEffect(() => {
    document.title = 'Загрузка рендеров';
    fetchTableData();
  }, []);

  // --- Функции fetchTableData, updateRowField, handleSave (остаются без изменений) ---
   const fetchTableData = async () => { /* ... ваш код ... */
       setTableLoading(true);
       setStatsLoading(true);
       setTotalCount(null);
       setUploadedCount(null);
       try {
         const token = localStorage.getItem('accessToken');
         const response = await axios.get(`${API_BASE_URL}/rd/moderator_studio_list/`, {
           headers: { Authorization: token ? `Bearer ${token}` : '' }
         });
         if (response.data) {
           setTableData(response.data.uploads || []);
           setTotalCount(response.data.total_count !== undefined ? response.data.total_count : null);
           setUploadedCount(response.data.uploaded_count !== undefined ? response.data.uploaded_count : null);
         } else {
           setTableData([]);
           setTotalCount(null);
           setUploadedCount(null);
           message.warning('Получены некорректные данные с сервера.');
         }
       } catch (error) {
         message.error(error.response?.data?.error || 'Ошибка при загрузке данных');
          setTableData([]);
          setTotalCount(null);
          setUploadedCount(null);
       } finally {
         setTableLoading(false);
         setStatsLoading(false);
       }
   };
   const updateRowField = (record, field, value) => { /* ... ваш код ... */
       setTableData(prevData =>
         prevData.map(item =>
           item.ModerationStudioUploadId === record.ModerationStudioUploadId
             ? { ...item, [field]: value }
             : item
         )
       );
   };
   const handleSave = async (record) => { /* ... ваш код ... */
      const token = localStorage.getItem('accessToken');
      const payload = {
        ModerationStudioUploadId: record.ModerationStudioUploadId,
        IsUploaded: record.IsUploaded,
        IsRejected: record.IsUploaded ? false : true,
        RejectComment: record.RejectComment || "",
        ReturnToRender: record.ReturnToRender || false,
        RejectedReason: record.RejectedReason ? record.RejectedReason.map(item => item.id) : []
      };
      try {
        await axios.post(`${API_BASE_URL}/rd/moderation_studio_upload_edit/`, payload, {
          headers: { Authorization: token ? `Bearer ${token}` : '' }
        });
        message.success('Данные сохранены');
        fetchTableData();
      } catch (error) {
        message.error(error.response?.data?.error || 'Ошибка при сохранении данных');
      }
   };

  // --- Колонки таблицы (остаются без изменений) ---
  const columns = [ /* ... ваш код ... */
    { title: 'ID', dataIndex: 'ModerationStudioUploadId', key: 'ModerationStudioUploadId' },
    { title: 'Штрихкод', dataIndex: 'Barcode', key: 'Barcode' },
    { title: 'Наименование', dataIndex: 'Name', key: 'Name' },
    { title: 'Ссылка на фото', dataIndex: 'RetouchPhotosLink', key: 'RetouchPhotosLink', render: (text) => (<a href={text} target="_blank" rel="noopener noreferrer">{text}</a>) },
    { title: 'Загружено', dataIndex: 'IsUploaded', key: 'IsUploaded', render: (text, record) => (<Checkbox checked={record.IsUploaded} onChange={(e) => { updateRowField(record, 'IsUploaded', e.target.checked); updateRowField(record, 'IsRejected', !e.target.checked); }}/>) },
    { title: 'Причины отклонения', dataIndex: 'RejectedReason', key: 'RejectedReason', render: (reasons, record) => { const initialValue = reasons ? reasons.map(r => r.id) : []; return (<Select mode="multiple" style={{ width: 200 }} placeholder="Выберите причины" value={initialValue} disabled={record.IsUploaded} onChange={(value) => { const selected = rejectionReasonsOptions.filter(item => value.includes(item.id)); updateRowField(record, 'RejectedReason', selected); }}>{rejectionReasonsOptions.map(reason => (<Option key={reason.id} value={reason.id}>{reason.name}</Option>))}</Select>); } },
    { title: 'Комментарий отклонения', dataIndex: 'RejectComment', key: 'RejectComment', render: (text, record) => (<Input value={record.RejectComment} disabled={record.IsUploaded} onChange={(e) => updateRowField(record, 'RejectComment', e.target.value)} style={{ width: 200 }}/>) },
    { title: 'Сохранить', key: 'save', render: (text, record) => (<Button icon={<SaveOutlined />} onClick={() => handleSave(record)} />) }
  ];

  // --- Функции модального окна (openModal, handleModalSubmit, handleCopyBarcode, handleModalCancel) ---
   const openModal = async () => { /* ... ваш код ... */
       if (modalLoading) return;
       setModalLoading(true);
       const token = localStorage.getItem('accessToken');
       try {
         const response = await axios.post(`${API_BASE_URL}/rd/moderator-studio-upload-start/`, {}, {
           headers: { Authorization: token ? `Bearer ${token}` : '' }
         });
         setModalData(response.data);
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
          setModalData(null);
       } finally {
         setModalLoading(false);
       }
   };
   const handleModalSubmit = async (mode) => { /* ... ваш код ... */
       if (!modalIsUploaded && modalRejectedReasons.length === 0) { message.error('При незагруженном статусе необходимо указать причины отклонения'); return; }
       if (modalIsUploaded && modalRejectedReasons.length > 0) { message.error('При статусе "Загружено" не должны быть указаны причины отклонения'); return; }
       const token = localStorage.getItem('accessToken');
       const payload = {
         ModerationStudioUploadId: modalData.ModerationStudioUploadId,
         IsUploaded: modalIsUploaded,
         IsRejected: !modalIsUploaded,
         RejectComment: modalIsUploaded ? "" : modalRejectComment,
         ReturnToRender: modalReturnToRender,
         RejectedReason: modalIsUploaded ? [] : modalRejectedReasons
       };
       try {
         await axios.post(`${API_BASE_URL}/rd/moderation_studio_upload_result/`, payload, {
           headers: { Authorization: token ? `Bearer ${token}` : '' }
         });
         message.success('Данные загружены успешно');
         if (mode === 'next') {
           openModal();
         } else {
           setModalVisible(false);
           fetchTableData();
         }
       } catch (error) {
         message.error(error.response?.data?.error || 'Ошибка при сохранении результатов');
       }
   };
   const handleCopyBarcode = (barcode) => { /* ... ваш код ... */
        navigator.clipboard.writeText(barcode)
          .then(() => message.success('Штрихкод скопирован'))
          .catch(() => message.error('Ошибка копирования'));
   };
   const handleModalCancel = () => { /* ... ваш код ... */
        setModalVisible(false);
        fetchTableData();
   };
   const extractFolderId = (url) => { /* ... ваш код ... */
        if (!url) return null;
        try {
          const match = url.match(/folders\/([a-zA-Z0-9_-]+)/);
          if (match && match[1]) { return match[1]; }
          const urlParts = url.split('/');
          const folderId = urlParts[urlParts.length - 1].split('?')[0];
          if (folderId && folderId.length > 15) { return folderId; }
          return null;
        } catch (error) {
          console.error("Ошибка извлечения ID папки:", error);
          return null;
        }
   };

  // --- НОВОЕ: Функция для получения ключа с бэкенда ---
  const fetchGoogleApiKey = async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
      message.error('Ошибка аутентификации: Токен не найден.');
      // Генерируем ошибку, чтобы прервать выполнение в handleDownloadAllFilesIndividually
      throw new Error('Authentication token not found');
    }
    try {
      console.log(`Запрос ключа на ${API_BASE_URL}/api/get-next-google-key/`); // Логгирование URL
      const response = await axios.get(`${API_BASE_URL}/api/get-next-google-key/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data && response.data.api_key) {
        console.log("Ключ Google API успешно получен."); // Логгирование успеха
        return response.data.api_key; // Возвращаем сам ключ
      } else {
        // Если бэкенд вернул 200 ОК, но без ключа
        message.error('Не удалось получить ключ Google API с сервера (неверный формат ответа).');
        throw new Error('Failed to retrieve Google API key from server (invalid response format)');
      }
    } catch (error) {
      console.error("Ошибка при получении ключа Google API:", error.response || error); // Логгирование ошибки
      // Пытаемся показать ошибку с бэкенда, если есть, иначе стандартную
      const errorMsg = error.response?.data?.detail || // Часто simplejwt возвращает ошибку в detail
                       error.response?.data?.error ||
                       'Ошибка сети или сервера при получении ключа Google API';
      message.error(errorMsg);
      throw error; // Перебрасываем ошибку дальше, чтобы ее поймал вызывающий catch
    }
  };


  // --- ОБНОВЛЕННАЯ Функция скачивания файлов ---
  const handleDownloadAllFilesIndividually = async (folderUrl) => {
    // 1. Проверки входных данных (URL, ID папки)
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
    message.loading({ content: 'Подготовка к скачиванию (получение ключа)...', key: 'downloadStatus', duration: 0 });

    let fetchedApiKey = null; // Переменная для хранения полученного ключа
    let files = []; // Объявляем files здесь для доступа в finally/catch

    try {
      // 2. Получаем ключ Google API с бэкенда
      fetchedApiKey = await fetchGoogleApiKey();
      // Если fetchGoogleApiKey выбросит ошибку, выполнение перейдет в catch

      // 3. Получаем список файлов (уже с полученным ключом)
      message.loading({ content: 'Получение списка файлов...', key: 'downloadStatus', duration: 0 });
      const listUrl = `https://www.googleapis.com/drive/v3/files?q='${folderId}' in parents and trashed=false&fields=files(id, name, mimeType)&key=${fetchedApiKey}&includeItemsFromAllDrives=true&supportsAllDrives=true`;
      const listResponse = await fetch(listUrl); // Используем fetch для запроса к Google

      if (!listResponse.ok) {
        // Обработка ошибок от Google API (например, неверный ключ, нет доступа и т.д.)
        const errorData = await listResponse.json().catch(() => ({})); // Пытаемся получить JSON ошибки
        console.error("Ошибка Google Drive API (list):", errorData);
        // Формируем сообщение об ошибке
        let errMsg = `Ошибка получения списка файлов: ${listResponse.statusText} (${listResponse.status})`;
        if (errorData.error?.message) {
            errMsg += `. ${errorData.error.message}`;
        } else if (errorData.error?.errors?.length > 0){
             errMsg += `. ${errorData.error.errors[0].reason}: ${errorData.error.errors[0].message}`;
        }
        // Если статус 403 или 401, возможно, проблема в полученном API ключе
        if(listResponse.status === 403 || listResponse.status === 401) {
            errMsg += " Возможно, проблема с полученным API ключом или правами доступа.";
        }
        throw new Error(errMsg);
      }

      // Используем files из внешнего scope
      ({ files } = await listResponse.json()); // Деструктуризация

      if (!files || files.length === 0) {
        message.warning({ content: 'Папка пуста или нет доступных файлов.', key: 'downloadStatus', duration: 3 });
        setIsDownloading(false); // Важно сбросить флаг загрузки
        return;
      }

      message.info({ content: `Найдено файлов: ${files.length}. Начинаю скачивание по одному...`, key: 'downloadStatus', duration: 5 });

      // 4. Скачиваем каждый файл отдельно
      let filesDownloadedCount = 0;
      let filesSkippedCount = 0;
      const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

      for (const file of files) {
        if (file.mimeType.startsWith('application/vnd.google-apps') || file.mimeType === 'application/vnd.google-apps.folder') {
          console.warn(`Пропущен файл/папка Google Workspace: ${file.name} (${file.mimeType})`);
          filesSkippedCount++;
          continue;
        }

        const downloadUrl = `https://www.googleapis.com/drive/v3/files/${file.id}?alt=media&key=${fetchedApiKey}&supportsAllDrives=true`;
        const fileMessageKey = `download_${file.id}`; // Ключ для сообщения этого файла

        try {
          message.loading({ content: `Скачиваю файл: ${file.name}...`, key: fileMessageKey, duration: 0 });
          const fileResponse = await fetch(downloadUrl);
          if (!fileResponse.ok) {
            console.error(`Ошибка скачивания файла ${file.name}: ${fileResponse.statusText} (${fileResponse.status})`);
            message.error({ content: `Ошибка скачивания ${file.name}: ${fileResponse.status}`, key: fileMessageKey, duration: 3 });
            filesSkippedCount++;
            continue;
          }
          const blob = await fileResponse.blob();

          // Инициируем скачивание файла
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', file.name);
          document.body.appendChild(link);
          link.click();
          link.parentNode.removeChild(link);
          window.URL.revokeObjectURL(url);

          message.success({ content: `Файл ${file.name} начал загружаться.`, key: fileMessageKey, duration: 2 });
          filesDownloadedCount++;
          console.log(`Инициирована загрузка файла: ${file.name}`);
          await delay(500); // Задержка

        } catch (fileError) {
           console.error(`Критическая ошибка при скачивании файла ${file.name}:`, fileError);
           message.error({ content: `Ошибка сети при скачивании ${file.name}`, key: fileMessageKey, duration: 3 });
           filesSkippedCount++;
        }
      } // Конец цикла for

      // 5. Финальное сообщение (после цикла)
      message.destroy('downloadStatus'); // Убираем сообщение "Получение списка..." или "Начинаю скачивание..."
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
          // Сюда мы не должны попасть, если папка была пуста (проверка выше)
          message.error({ content: 'Не удалось скачать файлы. Неизвестная ошибка.', duration: 5 });
      }

    } catch (error) {
      // Этот catch ловит ошибки из:
      // - fetchGoogleApiKey()
      // - fetch() для списка файлов
      // - Обработки ответа списка файлов (например, throw new Error)
      // Ошибки скачивания *отдельных* файлов обрабатываются внутри цикла for
      console.error('Ошибка во время процесса подготовки или получения списка файлов:', error);
       // Показываем сообщение об ошибке, если оно не было показано ранее (например, в fetchGoogleApiKey)
       // Используем error.message, т.к. мы формируем его при throw
      message.error({ content: `${error.message || 'Неизвестная ошибка при скачивании.'}`, key: 'downloadStatus', duration: 5 });

    } finally {
      // Выполняется всегда: после успешного выполнения или после ошибки
      setIsDownloading(false);
      // Убираем все оставшиеся сообщения о загрузке (на случай ошибок)
       setTimeout(() => {
            message.destroy('downloadStatus'); // Убедимся, что основное сообщение закрыто
            if (files && files.length > 0) { // Если список файлов был получен
                files.forEach(file => message.destroy(`download_${file.id}`)); // Закрываем сообщения по каждому файлу
            }
       }, 1500); // Немного подождем перед очисткой
    }
  };


  // --- JSX рендер компонента (без изменений в структуре, только вызов handleDownload...) ---
  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16, minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Title level={2}>Загрузка фото от студии</Title>

        {/* Статистика */}
        <Space direction="vertical" style={{ marginBottom: 16 }}>
          {statsLoading ? <Spin size="small" /> : (
            <>
              {totalCount !== null && (<Text strong>Всего отработано: {totalCount}</Text>)}
              {uploadedCount !== null && (<Text strong>Загружено: {uploadedCount}</Text>)}
              {totalCount === null && uploadedCount === null && !statsLoading && (<Text type="secondary">Статистика не загружена</Text>)}
            </>
          )}
        </Space>

        <Button type="primary" onClick={openModal} style={{ marginBottom: 16 }} loading={modalLoading}>
          Начать загрузку
        </Button>

        <Table
          dataSource={tableData}
          columns={columns}
          rowKey="ModerationStudioUploadId"
          loading={tableLoading}
          scroll={{ x: 1200 }}
        />

        {/* Модальное окно */}
        <Modal
          visible={modalVisible}
          title="Загрузка фото от ФС"
          onCancel={handleModalCancel}
          footer={null}
          width="40%"
          maskClosable={false}
        >
          {modalData ? (
            <div key={modalData.ModerationStudioUploadId} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* ШК */}
              <Space wrap>
                <Text strong>ШК:</Text>
                <Input value={modalData.Barcode} readOnly style={{ width: 150 }} />
                <Button icon={<CopyOutlined />} onClick={() => handleCopyBarcode(modalData.Barcode)} title="Копировать ШК" />
                <Button icon={<LinkOutlined />} onClick={() => window.open(`https://admin.teez.kz/ru/sku-photo-verification/shop/${modalData.ShopID}/product/${modalData.ProductID}/sku`, '_blank')} title="Перейти в админку" />
              </Space>
              {/* Наименование */}
              <div><Text strong>Наименование: </Text><Text>{modalData.Name}</Text></div>
              {/* Ссылка и кнопка Скачать */}
              <div>
                <Text strong>Ссылка на фото: </Text>
                {modalData.RetouchPhotosLink ? (
                  <>
                    <a href={modalData.RetouchPhotosLink} target="_blank" rel="noopener noreferrer">{modalData.RetouchPhotosLink}</a>
                    <Button
                      type="primary"
                      icon={<DownloadOutlined />}
                      onClick={() => handleDownloadAllFilesIndividually(modalData.RetouchPhotosLink)} // Вызов обновленной функции
                      loading={isDownloading}
                      disabled={isDownloading}
                      style={{ marginLeft: '10px' }}
                    >
                      Скачать все из папки
                    </Button>
                  </>
                ) : (<Text type="secondary">Ссылка отсутствует</Text>)}
              </div>
              {/* Загружено */}
              <div>
                 <Text strong>Загружено: </Text>
                 <Select placeholder="Выберите..." value={modalIsUploaded} onChange={(value) => { setModalIsUploaded(value); if (value) { setModalRejectedReasons([]); setModalRejectComment(''); } }} style={{ width: 120 }} allowClear >
                   <Option value={true}>Да</Option>
                   <Option value={false}>Нет</Option>
                 </Select>
               </div>
              {/* Причины и коммент (если не загружено) */}
              {!modalIsUploaded && (
                <>
                  <div>
                    <Text strong>Причины отклонения:</Text>
                    <Select mode="multiple" style={{ width: '100%' }} placeholder="Выберите причины" value={modalRejectedReasons} onChange={(value) => setModalRejectedReasons(value)}>
                      {rejectionReasonsOptions.map(reason => (<Option key={reason.id} value={reason.id}>{reason.name}</Option>))}
                    </Select>
                  </div>
                  <div>
                    <Text strong>Комментарий отклонения:</Text>
                    <Input.TextArea value={modalRejectComment} onChange={(e) => setModalRejectComment(e.target.value)} rows={3} />
                  </div>
                </>
              )}
              {/* Кнопки модалки */}
              <Space style={{ justifyContent: 'flex-end', width: '100%', marginTop: 16 }}>
                <Button onClick={() => handleModalSubmit('finish')} type="default">Завершить</Button>
                <Button onClick={() => handleModalSubmit('next')} type="primary">Далее</Button>
              </Space>
            </div>
          ) : (
             <div style={{ textAlign: 'center', padding: '20px' }}><Spin /><p>Загрузка данных для модерации...</p></div>
          )}
        </Modal>
      </Content>
    </Layout>
  );
};

export default ModerationStudioUpload;