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
  Spin // Добавим Spin на случай, если он потребуется где-то еще
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
  // --- Состояния компонента ---
  const [tableData, setTableData] = useState([]);
  const [tableLoading, setTableLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [modalData, setModalData] = useState(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalIsUploaded, setModalIsUploaded] = useState(null);
  const [modalReturnToRender, setModalReturnToRender] = useState(false);
  const [modalRejectedReasons, setModalRejectedReasons] = useState([]);
  const [modalRejectComment, setModalRejectComment] = useState('');
  const [isDownloading, setIsDownloading] = useState(false); // Состояние для кнопки скачивания

  // --- !!! УДАЛЕНО: Жестко закодированный ключ больше не нужен !!! ---
  // const GOOGLE_DRIVE_API_KEY = 'AIzaSyBGBcR20R_hQP_yNrfA_L2oWl-0G75BR84';

  useEffect(() => {
    document.title = 'Загрузка рендеров';
    fetchTableData();
  }, []);

  // --- Функции для работы с таблицей и модальным окном (без изменений) ---
  const fetchTableData = async () => {
    setTableLoading(true);
    try {
      const token = localStorage.getItem('accessToken');
      const response = await axios.get(`${API_BASE_URL}/rd/moderator_list_by_date/`, {
        headers: { Authorization: token ? `Bearer ${token}` : '' }
      });
      setTableData(response.data.uploads || []); // Убедимся, что это массив
    } catch (error) {
      message.error(error.response?.data?.error || 'Ошибка при загрузке данных');
      setTableData([]); // Устанавливаем пустой массив при ошибке
    } finally {
      setTableLoading(false);
    }
  };

  const updateRowField = (record, field, value) => {
    setTableData(prevData =>
      prevData.map(item =>
        item.ModerationUploadId === record.ModerationUploadId
          ? { ...item, [field]: value }
          : item
      )
    );
  };

  const handleSave = async (record) => {
     const token = localStorage.getItem('accessToken');
     const payload = {
       ModerationUploadId: record.ModerationUploadId,
       IsUploaded: record.IsUploaded,
       IsRejected: record.IsUploaded ? false : true,
       RejectComment: record.RejectComment || "",
       ReturnToRender: record.ReturnToRender || false,
       RejectedReason: record.RejectedReason ? record.RejectedReason.map(item => item.id) : []
     };
     try {
       await axios.post(`${API_BASE_URL}/rd/moderation_upload_edit/`, payload, {
         headers: { Authorization: token ? `Bearer ${token}` : '' }
       });
       message.success('Данные сохранены');
       fetchTableData();
     } catch (error) {
       message.error(error.response?.data?.error || 'Ошибка при сохранении данных');
     }
  };

   const openModal = async () => {
       if (modalLoading) return;
       setModalLoading(true);
       const token = localStorage.getItem('accessToken');
       try {
         const response = await axios.post(`${API_BASE_URL}/rd/moderator-upload-start/`, {}, {
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
         setModalData(null); // Сброс данных при ошибке
       } finally {
         setModalLoading(false);
       }
   };

   const handleModalSubmit = async (mode) => {
        if (!modalIsUploaded && modalRejectedReasons.length === 0) { message.error('При незагруженном статусе необходимо указать причины отклонения'); return; }
        const token = localStorage.getItem('accessToken');
        const payload = {
          ModerationUploadId: modalData.ModerationUploadId,
          IsUploaded: modalIsUploaded,
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
            openModal(); // Запросить следующий
          } else {
            setModalVisible(false); // Закрыть окно
            fetchTableData(); // Обновить таблицу
          }
        } catch (error) {
          message.error(error.response?.data?.error || 'Ошибка при сохранении результатов');
        }
   };

  const handleCopyBarcode = (barcode) => {
    navigator.clipboard.writeText(barcode)
      .then(() => message.success('Штрихкод скопирован'))
      .catch(() => message.error('Ошибка копирования'));
  };

  const extractFolderId = (url) => {
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

   // --- Колонки таблицы (без изменений) ---
   const columns = [
     { title: 'ID', dataIndex: 'ModerationUploadId', key: 'ModerationUploadId' },
     { title: 'Штрихкод', dataIndex: 'Barcode', key: 'Barcode' },
     { title: 'Наименование', dataIndex: 'Name', key: 'Name' },
     { title: 'Ссылка на фото', dataIndex: 'RetouchPhotosLink', key: 'RetouchPhotosLink', render: (text) => (<a href={text} target="_blank" rel="noopener noreferrer">{text}</a>) },
     { title: 'Загружено', dataIndex: 'IsUploaded', key: 'IsUploaded', render: (text, record) => (<Checkbox checked={record.IsUploaded} onChange={(e) => { updateRowField(record, 'IsUploaded', e.target.checked); updateRowField(record, 'IsRejected', !e.target.checked); }}/>) },
     { title: 'Вернуть фотостудии', dataIndex: 'ReturnToRender', key: 'ReturnToRender', render: (text, record) => (<Checkbox checked={record.ReturnToRender} onChange={(e) => updateRowField(record, 'ReturnToRender', e.target.checked)} />) },
     { title: 'Причины отклонения', dataIndex: 'RejectedReason', key: 'RejectedReason', render: (reasons, record) => { const initialValue = reasons ? reasons.map(r => r.id) : []; return (<Select mode="multiple" style={{ width: 200 }} placeholder="Выберите причины" value={initialValue} onChange={(value) => { const selected = rejectionReasonsOptions.filter(item => value.includes(item.id)); updateRowField(record, 'RejectedReason', selected); }}>{rejectionReasonsOptions.map(reason => (<Option key={reason.id} value={reason.id}>{reason.name}</Option>))}</Select>); } },
     { title: 'Комментарий отклонения', dataIndex: 'RejectComment', key: 'RejectComment', render: (text, record) => (<Input value={record.RejectComment} onChange={(e) => updateRowField(record, 'RejectComment', e.target.value)} style={{ width: 200 }}/>) },
     { title: 'Сохранить', key: 'save', render: (text, record) => (<Button icon={<SaveOutlined />} onClick={() => handleSave(record)} />) }
   ];


  // --- НОВОЕ: Функция для получения ключа с бэкенда (такая же, как в предыдущем компоненте) ---
  const fetchGoogleApiKey = async () => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
      message.error('Ошибка аутентификации: Токен не найден.');
      throw new Error('Authentication token not found');
    }
    try {
      console.log(`Запрос ключа на ${API_BASE_URL}/api/get-next-google-key/`);
      const response = await axios.get(`${API_BASE_URL}/api/get-next-google-key/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data && response.data.api_key) {
        console.log("Ключ Google API успешно получен.");
        return response.data.api_key;
      } else {
        message.error('Не удалось получить ключ Google API с сервера (неверный формат ответа).');
        throw new Error('Failed to retrieve Google API key from server (invalid response format)');
      }
    } catch (error) {
      console.error("Ошибка при получении ключа Google API:", error.response || error);
      const errorMsg = error.response?.data?.detail ||
                       error.response?.data?.error ||
                       'Ошибка сети или сервера при получении ключа Google API';
      message.error(errorMsg);
      throw error;
    }
  };


  // --- ОБНОВЛЕННАЯ Функция скачивания файлов (такая же логика, как в предыдущем компоненте) ---
  const handleDownloadAllFilesIndividually = async (folderUrl) => {
    // 1. Проверки входных данных
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

    let fetchedApiKey = null;
    let files = [];

    try {
      // 2. Получаем ключ Google API с бэкенда
      fetchedApiKey = await fetchGoogleApiKey();

      // 3. Получаем список файлов
      message.loading({ content: 'Получение списка файлов...', key: 'downloadStatus', duration: 0 });
      const listUrl = `https://www.googleapis.com/drive/v3/files?q='${folderId}' in parents and trashed=false&fields=files(id, name, mimeType)&key=${fetchedApiKey}&includeItemsFromAllDrives=true&supportsAllDrives=true`;
      const listResponse = await fetch(listUrl);

      if (!listResponse.ok) {
         const errorData = await listResponse.json().catch(() => ({}));
         console.error("Ошибка Google Drive API (list):", errorData);
         let errMsg = `Ошибка получения списка файлов: ${listResponse.statusText} (${listResponse.status})`;
         if (errorData.error?.message) {errMsg += `. ${errorData.error.message}`;}
         else if (errorData.error?.errors?.length > 0){ errMsg += `. ${errorData.error.errors[0].reason}: ${errorData.error.errors[0].message}`; }
         if(listResponse.status === 403 || listResponse.status === 401) {errMsg += " Возможно, проблема с полученным API ключом или правами доступа.";}
         throw new Error(errMsg);
      }

      ({ files } = await listResponse.json());

      if (!files || files.length === 0) {
        message.warning({ content: 'Папка пуста или нет доступных файлов.', key: 'downloadStatus', duration: 3 });
        setIsDownloading(false); // <<< Сброс состояния
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
        const fileMessageKey = `download_${file.id}`;

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
          await delay(500);

        } catch (fileError) {
           console.error(`Критическая ошибка при скачивании файла ${file.name}:`, fileError);
           message.error({ content: `Ошибка сети при скачивании ${file.name}`, key: fileMessageKey, duration: 3 });
           filesSkippedCount++;
        }
      } // Конец цикла for

      // 5. Финальное сообщение
      message.destroy('downloadStatus');
      let finalMessage = '';
      if (filesDownloadedCount > 0) {
         finalMessage = `Инициирована загрузка ${filesDownloadedCount} файлов.`;
         if (filesSkippedCount > 0) { finalMessage += ` Пропущено: ${filesSkippedCount}.`; }
         message.success({ content: finalMessage, duration: 5 });
      } else if (filesSkippedCount > 0) {
         message.warning({ content: `Не удалось начать загрузку ни одного файла. Пропущено: ${filesSkippedCount}. Проверьте консоль.`, duration: 5 });
      } else {
          message.error({ content: 'Не удалось скачать файлы. Неизвестная ошибка.', duration: 5 });
      }

    } catch (error) {
      console.error('Ошибка во время процесса подготовки или получения списка файлов:', error);
      message.error({ content: `${error.message || 'Неизвестная ошибка при скачивании.'}`, key: 'downloadStatus', duration: 5 });

    } finally {
      setIsDownloading(false);
       setTimeout(() => {
            message.destroy('downloadStatus');
            if (files && files.length > 0) { files.forEach(file => message.destroy(`download_${file.id}`)); }
       }, 1500);
    }
  };


  // --- JSX рендер компонента ---
  return (
    <Layout>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Content style={{ padding: 16, minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <Title level={2}>Загрузка рендеров</Title>
        <Button type="primary" onClick={openModal} style={{ marginBottom: 16 }} loading={modalLoading}>
          Начать загрузку
        </Button>
        <Table
          dataSource={tableData}
          columns={columns}
          rowKey="ModerationUploadId"
          loading={tableLoading}
          scroll={{ x: 1200 }} // Добавлено для адаптивности таблицы
        />
        {/* Модальное окно */}
        <Modal
          visible={modalVisible}
          title="Загрузка рендеров"
          // Обновляем таблицу при закрытии окна (на случай если пользователь взял рендер и закрыл)
          onCancel={() => { setModalVisible(false); fetchTableData(); }}
          footer={null}
          width="40%" // Сделаем пошире как в другом компоненте
          maskClosable={false}
        >
          {modalData ? ( // Используем Spin если modalData еще не загрузились (хотя openModal ставит его перед показом)
            <div key={modalData.ModerationUploadId} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* ШК */}
              <Space wrap>
                 <Text strong>ШК:</Text>
                 <Input value={modalData.Barcode} readOnly style={{ width: 150 }} />
                 <Button icon={<CopyOutlined />} onClick={() => handleCopyBarcode(modalData.Barcode)} title="Копировать ШК" style={{ cursor: 'pointer' }} />
                 <Button icon={<LinkOutlined />} onClick={() => window.open(`https://admin.teez.kz/ru/sku-photo-verification/shop/${modalData.ShopID}/product/${modalData.ProductID}/sku`, '_blank')} title="Перейти в админку" style={{ cursor: 'pointer' }} />
              </Space>
              {/* Наименование - если оно есть в modalData */}
              {modalData.Name && (
                  <div><Text strong>Наименование: </Text><Text>{modalData.Name}</Text></div>
              )}
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
                 <Select placeholder="Выберите..." value={modalIsUploaded} onChange={(value) => setModalIsUploaded(value)} style={{ width: 120 }} allowClear >
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
                    <Input.TextArea // Используем TextArea как в другом компоненте
                        value={modalRejectComment}
                        onChange={(e) => setModalRejectComment(e.target.value)}
                        rows={3}
                     />
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

export default ModerationUpload;