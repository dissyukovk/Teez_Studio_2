import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Table, Pagination, Button, Space, message, Typography, Tooltip, Modal } from 'antd';
import { LinkOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar'; // Путь к вашему Sidebar
import { API_BASE_URL } from '../../utils/config'; // Путь к вашему файлу конфигурации

const { Content } = Layout;
const { Title, Text, Link } = Typography;

const ModerationRejects = ({ darkMode, setDarkMode }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState({}); // { [recordId]: 'actionType' }
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 600, // Соответствует пагинации Django
    total: 0,
  });

  // --- Функция для загрузки данных ---
  const fetchData = useCallback(async (page = 1) => {
    setLoading(true);
    const token = localStorage.getItem('accessToken');
    if (!token) {
      message.error('Ошибка аутентификации: Токен не найден.');
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`${API_BASE_URL}/rd/moderation/rejects-to-retouch/`, {
        headers: { Authorization: `Bearer ${token}` },
        params: {
          page: page,
          page_size: pagination.pageSize, // Отправляем размер страницы
        },
      });
      // Добавляем key для строк таблицы Antd
      const processedData = response.data.results.map(item => ({
        ...item,
        key: item.id, // Используем moderation upload id как ключ строки
      }));
      setData(processedData);
      setPagination(prev => ({
        ...prev,
        current: page,
        total: response.data.count,
      }));
    } catch (error) {
      console.error('Ошибка при загрузке данных:', error);
      message.error(
        error.response?.data?.detail || 'Не удалось загрузить список отклоненных загрузок.'
      );
    } finally {
      setLoading(false);
    }
  }, [pagination.pageSize]); // Зависимость от pageSize, если он может меняться

  // --- Загрузка данных при монтировании компонента ---
  useEffect(() => {
    document.title = 'Отклоненные загрузки';
    fetchData(pagination.current);
  }, [fetchData]); // Используем useCallback и передаем fetchData в зависимости

  // --- Функция для выполнения действий ---
  const handleAction = async (recordId, actionType, confirmationMessage = null) => {
    const actionEndpoints = {
      sendForEdits: `/rd/moderation-uploads/${recordId}/send-for-edits/`,
      returnToRenderQueue: `/rd/moderation-uploads/${recordId}/return-to-render-queue/`,
      markFixed: `/rd/moderation-uploads/${recordId}/mark-fixed-return-to-upload/`,
      sendForReshoot: `/rd/moderation-uploads/${recordId}/send-for-reshoot/`,
    };

    const endpoint = actionEndpoints[actionType];
    if (!endpoint) {
      message.error('Неизвестное действие');
      return;
    }

    const performAction = async () => {
      setActionLoading(prev => ({ ...prev, [recordId]: actionType }));
      const token = localStorage.getItem('accessToken');
      if (!token) {
        message.error('Ошибка аутентификации: Токен не найден.');
        setActionLoading(prev => ({ ...prev, [recordId]: null }));
        return;
      }

      try {
        const response = await axios.post(
          `${API_BASE_URL}${endpoint}`,
          {}, // POST запросы здесь без тела, id в URL
          { headers: { Authorization: `Bearer ${token}` } }
        );
        message.success(response.data?.status || 'Действие выполнено успешно.');
        // Обновляем данные после успешного действия (текущая страница)
        fetchData(pagination.current);
      } catch (error) {
        console.error(`Ошибка при выполнении действия ${actionType}:`, error);
        // Отображаем специфичную ошибку от бэкенда, если есть
        const errorMessage = error.response?.data?.detail || error.response?.data?.message || `Не удалось выполнить действие: ${actionType}`;
        message.error(errorMessage, 5); // Показываем ошибку дольше
      } finally {
        setActionLoading(prev => ({ ...prev, [recordId]: null }));
      }
    };

    if (confirmationMessage) {
        Modal.confirm({
            title: 'Подтверждение действия',
            icon: <QuestionCircleOutlined />,
            content: confirmationMessage,
            okText: 'Да',
            cancelText: 'Отмена',
            onOk: performAction,
        });
    } else {
        await performAction();
    }
  };


  // --- Колонки таблицы ---
  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: 'Штрихкод',
      dataIndex: 'Barcode',
      key: 'barcode',
      width: 150,
      render: (text, record) => (
        <Space>
          <span>{text}</span>
          <Tooltip title="Перейти к товару в админке">
            <a
              href={`https://admin.teez.kz/ru/product-verification/shop/${record.ShopID}/product/${record.ProductID}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <LinkOutlined />
            </a>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: 'Причины отклонения',
      dataIndex: 'RejectedReason',
      key: 'rejectedReason',
      render: (reasons) => (
         // Проверка, что reasons - это массив и он не пустой
        Array.isArray(reasons) && reasons.length > 0
          ? reasons.map(reason => reason.name).join(', ')
          : '-' // Отображаем прочерк, если причин нет
      ),
    },
    {
        title: 'Коммент модератора',
        dataIndex: 'RejectComment',
        key: 'RejectComment',
        width: 180,
       render: (text) => text || '-' // Показываем прочерк, если имя пустое
    },
    {
      title: 'Ретушер',
      dataIndex: 'Retoucher',
      key: 'retoucher',
      width: 180,
       render: (text) => text || '-' // Показываем прочерк, если имя пустое
    },
    {
      title: 'Ссылка на фото',
      dataIndex: 'RetouchPhotosLink',
      key: 'retouchPhotosLink',
      render: (link) => (
        link ? (
          <Link href={link} target="_blank" rel="noopener noreferrer" ellipsis>
            {link}
          </Link>
        ) : '-'
      ),
    },
    {
      title: 'Дата рендера', // Используем CheckTimeEnd из сериализатора
      dataIndex: 'RetouchTimeEnd', // Поле из вашего сериализатора
      key: 'RetouchTimeEnd',
      width: 160,
      render: (text) => text || '-' // Бэкенд уже форматирует дату
    },
    {
      title: 'Действия',
      key: 'actions',
      width: 200,
      fixed: 'right', // Закрепляем колонку справа
      render: (text, record) => {
        const isLoading = actionLoading[record.id];
        return (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Button
              type="primary"
              size="small"
              style={{ width: '100%' }}
              loading={isLoading === 'sendForEdits'}
              disabled={!!isLoading} // Блокируем все кнопки, если любая для этой строки грузится
              onClick={() => handleAction(record.id, 'sendForEdits')}
            >
              Отправить на правки
            </Button>
            <Button
              type="primary"
              size="small"
              style={{ width: '100%' }}
              loading={isLoading === 'returnToRenderQueue'}
              disabled={!!isLoading}
              onClick={() => handleAction(record.id, 'returnToRenderQueue', 'Вы уверены, что хотите вернуть товар в очередь рендера? Комментарий будет скопирован.')}
            >
              Вернуть в очередь рендера
            </Button>
            <Button
              type="primary"
              size="small"
              style={{ width: '100%' }}
              loading={isLoading === 'markFixed'}
              disabled={!!isLoading}
              onClick={() => handleAction(record.id, 'markFixed')}
            >
              Исправили - вернуть
            </Button>
            <Button
              danger
              size="small"
              style={{ width: '100%' }}
              loading={isLoading === 'sendForReshoot'}
              disabled={!!isLoading}
              onClick={() => handleAction(record.id, 'sendForReshoot', 'Вы уверены, что хотите отправить товар на съемку?')}
            >
              На съемку
            </Button>
          </Space>
        );
      },
    },
  ];

  // --- Обработчик изменения страницы ---
  const handlePageChange = (page) => {
    fetchData(page);
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content style={{ padding: 24, margin: 0, minHeight: 280, background: darkMode ? '#1a1a1a' : '#fff' }}>
          <Title level={2} style={{ marginBottom: 24, color: darkMode ? '#fff' : 'inherit' }}>
            Отклоненные модерацией загрузки
          </Title>

          <Pagination
            style={{ marginBottom: 16 }}
            current={pagination.current}
            pageSize={pagination.pageSize}
            total={pagination.total}
            onChange={handlePageChange}
            showSizeChanger={false} // Убираем возможность менять размер страницы, т.к. он фиксирован на бэке
            showTotal={(total, range) => `${range[0]}-${range[1]} из ${total} записей`}
          />

          <Table
            columns={columns}
            dataSource={data}
            loading={loading}
            pagination={false} // Используем кастомную пагинацию выше
            rowKey="key" // Используем key, который мы добавили = id
            scroll={{ x: 1200 }} // Горизонтальный скролл при необходимости
            bordered // Добавим рамки для лучшей читаемости
            size="small" // Уменьшим размер ячеек
          />

          <Pagination
            style={{ marginTop: 16 }}
            current={pagination.current}
            pageSize={pagination.pageSize}
            total={pagination.total}
            onChange={handlePageChange}
            showSizeChanger={false}
            showTotal={(total, range) => `${range[0]}-${range[1]} из ${total} записей`}
          />
        </Content>
      </Layout>
    </Layout>
  );
};

export default ModerationRejects;