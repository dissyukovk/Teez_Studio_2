import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Layout, Table, Descriptions, Typography, message, Spin, Button, Modal, Select, Space, Tooltip, Input } from 'antd';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar';
import { API_BASE_URL } from '../../utils/config';
import { CheckSquareOutlined, CameraOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { RETOUCH_STATUS_OPTIONS, SRETOUCH_STATUS_OPTIONS } from '../../utils/srtConstants';

const { Content } = Layout;
const { Title, Text } = Typography;
const { Option } = Select;

// CSS for row highlighting
const inlineTableStyles = `
  .ant-table-tbody > tr.highlight-row-green-underline > td {
    border-bottom: 2px solid green !important;
  }
`;

// Modal component for adding comments
const CommentModal = ({ visible, onOk, onCancel, initialComment, productBarcode }) => {
  const [internalCommentText, setInternalCommentText] = useState('');

  useEffect(() => {
    if (visible) {
      setInternalCommentText(initialComment || '');
    }
  }, [visible, initialComment]);

  const handleOk = () => onOk(internalCommentText);
  const handleCancel = () => {
    setInternalCommentText('');
    onCancel();
  };

  return (
    <Modal
      title={`Комментарий для правок (Товар: ${productBarcode || ''})`}
      open={visible}
      onOk={handleOk}
      onCancel={handleCancel}
      okText="Сохранить"
      cancelText="Отмена"
    >
      <Input.TextArea
        rows={4}
        value={internalCommentText}
        onChange={(e) => setInternalCommentText(e.target.value)}
        placeholder="Введите комментарий для правок"
      />
    </Modal>
  );
};


const RetouchRequestDetailPage = ({ darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const { requestNumber } = useParams();
  const [token] = useState(localStorage.getItem('accessToken'));
  
  const [detailData, setDetailData] = useState(null);
  const [requestHeader, setRequestHeader] = useState(null);
  const [loading, setLoading] = useState(true);
  
  const [photoCounts, setPhotoCounts] = useState({});
  const [isCounting, setIsCounting] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  // State for the comment modal
  const [isCommentModalVisible, setIsCommentModalVisible] = useState(false);
  const [currentEditingProduct, setCurrentEditingProduct] = useState(null);

  // State for retouchers
  const [availableRetouchers, setAvailableRetouchers] = useState([]); // Renamed for clarity


  useEffect(() => {
    document.title = `Детали заявки на ретушь ${requestNumber}`;
    if (!token) {
      Modal.error({ title: 'Ошибка доступа', content: 'Токен не найден.', onOk: () => navigate('/login') });
    }
  }, [navigate, token, requestNumber]);

  // Function to fetch available retouchers
  const fetchAvailableRetouchers = useCallback(async () => {
    if (!token) return;
    try {
      const response = await axios.get(`${API_BASE_URL}/srt/retouchers/on-work/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setAvailableRetouchers(Array.isArray(response.data.results) ? response.data.results : []); // Access results property
    } catch (error) {
      console.error('Ошибка загрузки ретушеров:', error);
      message.error('Ошибка загрузки списка ретушеров.');
      setAvailableRetouchers([]);
    }
  }, [token]);


  const fetchRequestDetails = useCallback(async () => {
    if (!token || !requestNumber) return;
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/srt/retouch-requests/${requestNumber}/details/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.data.results && response.data.results.length > 0) {
          setRequestHeader(response.data.results[0].retouch_request);
          setDetailData(response.data.results.map(p => ({...p, key: p.id})));
      } else {
          setDetailData([]);
          setRequestHeader(null);
      }
    } catch (error) {
      message.error('Ошибка загрузки деталей заявки');
    } finally {
      setLoading(false);
    }
  }, [token, requestNumber]);

  useEffect(() => {
    if (token) {
      fetchRequestDetails();
      fetchAvailableRetouchers(); // Call fetchAvailableRetouchers here
    }
  }, [token, fetchRequestDetails, fetchAvailableRetouchers]);

  const updateLocalProductState = useCallback((updatedProduct) => {
    setDetailData(prevData =>
      prevData.map(p => p.id === updatedProduct.id ? { ...updatedProduct, key: updatedProduct.id } : p)
    );
  }, []);

  // Generic status update for retouch_status
  const handleRetouchStatusChange = async (productId, statusId) => {
    try {
      const response = await axios.patch(
        `${API_BASE_URL}/srt/retouch-products/update-status/`,
        { retouch_request_product_id: productId, status_id: statusId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      updateLocalProductState(response.data);
      message.success(`Статус ретуши обновлен.`);
    } catch (error) {
      message.error('Ошибка обновления статуса ретуши.');
    }
  };
  
  // Specific handler for SRetouch status to trigger modal if needed
  const handleSRetouchStatusChange = (product, newStatusId) => {
    if (newStatusId === 2) { // "Правки" status
        setCurrentEditingProduct(product);
        setIsCommentModalVisible(true);
    } else { // For other statuses like "Проверено"
        submitSRetouchStatus(product.id, newStatusId);
    }
  };
  
  // The actual API call for SRetouch status
  const submitSRetouchStatus = async (productId, statusId, comment = null) => {
    const payload = {
        retouch_request_product_id: productId,
        status_id: statusId,
    };
    if (comment !== null) {
        payload.comment = comment;
    }

    try {
      const response = await axios.patch(
        `${API_BASE_URL}/srt/retouch-products/update-s-status/`,
        payload,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      updateLocalProductState(response.data);
      message.success(`Статус проверки обновлен.`);
    } catch (error) {
      message.error('Ошибка обновления статуса проверки.');
    }
  };

  const handleCommentModalOk = (commentText) => {
    if (currentEditingProduct) {
        submitSRetouchStatus(currentEditingProduct.id, 2, commentText); // statusId 2 is "Правки"
    }
    setIsCommentModalVisible(false);
    setCurrentEditingProduct(null);
  };
  
  const handleCommentModalCancel = () => {
    setIsCommentModalVisible(false);
    setCurrentEditingProduct(null);
  };

  const getFolderIdFromUrl = (url) => {
    if (!url) return null;
    const match = url.match(/folders\/([a-zA-Z0-9_-]+)/);
    return match ? match[1] : null;
  };
  
  const handleCountPhotos = useCallback(async () => {
    if (!detailData) return;

    // Filter for products to count
    const productsToCount = detailData.filter(p => p.retouch_status?.id === 2 && p.sretouch_status?.id !== 1);

    if (productsToCount.length === 0) {
        message.info('Нет товаров, подходящих для подсчета фото.');
        return;
    }

    setIsCounting(true);
    message.loading({ content: 'Получение ключа API...', key: 'count' });
    let apiKey;
    try {
      const keyResponse = await axios.get(`${API_BASE_URL}/api/get-next-google-key/`, { headers: { Authorization: `Bearer ${token}` }});
      apiKey = keyResponse.data.api_key;
      if (!apiKey) throw new Error("API ключ не получен");
    } catch (error) {
        message.error('Не удалось получить ключ Google API.');
        setIsCounting(false);
        message.destroy('count');
        return;
    }

    message.loading({ content: 'Подсчет фотографий...', key: 'count', duration: 0 });
    // Use the filtered list
    const countPromises = productsToCount.map(async (product) => {
        const folderId = getFolderIdFromUrl(product.retouch_link);
        if (!folderId) return { id: product.id, count: 'N/A' };
        try {
            const url = `https://www.googleapis.com/drive/v3/files?q='${folderId}' in parents and mimeType='image/jpeg' and trashed=false&key=${apiKey}&supportsAllDrives=true&includeItemsFromAllDrives=true&fields=files(id)`;
            const response = await axios.get(url);
            return { id: product.id, count: response.data.files ? response.data.files.length : 0 };
        } catch (error) {
            console.error(`Error counting photos for product ${product.id}:`, error);
            return { id: product.id, count: 'Ошибка' };
        }
    });

    const results = await Promise.all(countPromises);
    const newCounts = results.reduce((acc, result) => ({...acc, [result.id]: result.count }), {});
    
    setPhotoCounts(prev => ({ ...prev, ...newCounts }));
    message.success('Подсчет завершен.', 2);
    message.destroy('count');
    setIsCounting(false);
  }, [detailData, token]);
  
  const handleBulkCheck = async () => {
    if (!detailData) return;

    // Filter for products to check
    const productsToCheck = detailData.filter(p => p.retouch_status?.id === 2 && p.sretouch_status?.id !== 1);

    if (productsToCheck.length === 0) {
      message.info('Нет товаров, требующих проверки.');
      return;
    }
    setIsUpdating(true);
    message.loading({ content: `Проверка ${productsToCheck.length} товаров...`, key: 'bulk', duration: 0 });
    
    const checkPromises = productsToCheck.map(p => submitSRetouchStatus(p.id, 1));
    await Promise.all(checkPromises);

    message.success('Массовая проверка завершена.', 2);
    message.destroy('bulk');
    setIsUpdating(false);
    fetchRequestDetails();
  };

  const handleUpdateRequestStatus = async (newStatusId) => {
    setIsUpdating(true);
    try {
        await axios.patch(
            `${API_BASE_URL}/srt/retouch-requests/${requestNumber}/update-status/${newStatusId}/`,
            {},
            { headers: { Authorization: `Bearer ${token}` } }
        );
        message.success(`Статус заявки изменен.`);
        fetchRequestDetails();
    } catch (error) {
        const errorMsg = error.response?.data?.error || 'Ошибка изменения статуса заявки.';
        message.error(errorMsg);
    } finally {
        setIsUpdating(false);
    }
  };

  // Handler for retoucher reassignment for detail page
  const handleRetoucherReassign = async (newRetoucherId) => {
    if (!token || !requestHeader?.RequestNumber) return;
    try {
      await axios.patch(
        `${API_BASE_URL}/srt/reassign-retoucher/`,
        { request_number: requestHeader.RequestNumber, retoucher_id: newRetoucherId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      message.success(`Ретушер для заявки ${requestHeader.RequestNumber} переназначен.`);
      fetchRequestDetails(); // Re-fetch details to update the header and product list if needed
    } catch (error) {
      const errorMsg = error.response?.data?.error || `Ошибка переназначения ретушера для заявки ${requestHeader.RequestNumber}.`;
      message.error(errorMsg);
      console.error("Reassign retoucher error:", error.response?.data || error);
    }
  };


  const actionButtonsState = useMemo(() => {
    if (!detailData || !requestHeader || requestHeader.status?.id !== 3) {
      return { canSetReady: false, canSetCorrections: false };
    }
    const allVerified = detailData.every(p => p.sretouch_status?.id === 1);
    const hasCorrections = detailData.some(p => p.sretouch_status?.id === 2);
    
    return { canSetReady: allVerified, canSetCorrections: hasCorrections };
  }, [detailData, requestHeader]);

  const getRowClassName = (record) => {
    const shouldHighlight = record.retouch_status && !record.sretouch_status;
    return shouldHighlight ? 'highlight-row-green-underline' : '';
  };

  const renderTextLink = (link) => {
    if (!link) return '-';
    return (
        <a href={link} target="_blank" rel="noopener noreferrer">
            {link.length > 40 ? `${link.substring(0, 40)}...` : link}
        </a>
    );
  };

  const columns = [
    { title: 'Штрихкод', dataIndex: ['st_request_product', 'product', 'barcode'], key: 'barcode', width: 105 },
    { title: 'Наименование', dataIndex: ['st_request_product', 'product', 'name'], key: 'name', ellipsis: false, width: 190 },
    {
      title: 'Категория',
      key: 'category',
      width: 130,
      render: (_, record) => record.st_request_product.product.category ? `${record.st_request_product.product.category.id} - ${record.st_request_product.product.category.name}` : '-',
    },
    {
      title: 'Реф',
      key: 'reference',
      width: 50,
      align: 'center',
      render: (_, record) => {
          // Проверяем, что флаг IsReference === true и ссылка существует record.st_request_product.product.category?.reference_link
          const hasReference = record.st_request_product.product.category?.IsReference === true;
          const referenceLink = record.st_request_product.product.category?.reference_link;

          return hasReference && referenceLink ? (
              <Tooltip title="Открыть референс">
                  <Button 
                      icon={<EyeOutlined />} 
                      href={referenceLink} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      size="small" 
                      type="link"
                  />
              </Tooltip>
          ) : '';
      },
    },
    { title: 'Инфо', dataIndex: ['st_request_product', 'product', 'info'], key: 'info', ellipsis: false, width: 140 },
    { title: 'Комментарий фотографа', dataIndex: ['st_request_product', 'ph_to_rt_comment'], key: 'ph_to_rt_comment', ellipsis: false, width: 140 },
    { title: 'Исходники', dataIndex: ['st_request_product', 'photos_link'], key: 'source_link', ellipsis: true, render: renderTextLink, width: 70 },
    {
      title: 'Ссылка на фото',
      dataIndex: 'retouch_link',
      key: 'retouch_link',
      render: renderTextLink,
      ellipsis: true,
      width: 70
    },
    {
      title: 'Кол-во',
      key: 'photo_count',
      align: 'center',
      width: 50,
      render: (_, record) => <strong>{photoCounts[record.id] ?? '-'}</strong>,
    },
    {
      title: 'Статус',
      dataIndex: 'retouch_status',
      key: 'retouch_status',
      width: 105,
      render: (status, record) => (
        <Select
          style={{ width: '102%' }}
          value={status?.id}
          onChange={(value) => handleRetouchStatusChange(record.id, value)}
          placeholder="Статус"
        >
          {RETOUCH_STATUS_OPTIONS.map(opt => <Option key={opt.id} value={opt.id}>{opt.name}</Option>)}
        </Select>
      ),
    },
    {
      title: 'Проверка',
      dataIndex: 'sretouch_status',
      key: 'sretouch_status',
      width: 100,
      render: (status, record) => (
        <Select
          style={{ width: '102%' }}
          value={status?.id}
          onChange={(value) => handleSRetouchStatusChange(record, value)}
          placeholder="Статус"
        >
          {SRETOUCH_STATUS_OPTIONS.map(opt => <Option key={opt.id} value={opt.id}>{opt.name}</Option>)}
        </Select>
      ),
    },
    { title: 'Комментарий', dataIndex: 'comment', key: 'comment', ellipsis: false, width: 180 },
  ];

  if (loading || !detailData) return <Layout><Content style={{padding: '50px', textAlign: 'center'}}><Spin size="large" /></Content></Layout>;

  return (
    <>
      <style>{inlineTableStyles}</style>
      <Layout style={{ minHeight: '100vh' }}>
        <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
        <Layout>
          <Content style={{ padding: '24px', background: darkMode ? '#001529' : '#fff' }}>
            <Title level={2} style={{ color: darkMode ? 'white' : 'black' }}>Детали заявки: {requestNumber}</Title>
            {requestHeader && (
                <Descriptions bordered column={3} size="small" style={{ marginBottom: 24 }}>
                    <Descriptions.Item label="Номер">{requestHeader.RequestNumber}</Descriptions.Item>
                    <Descriptions.Item label="Ретушер">
                      <Space>
                        <Select
                          style={{ width: 180 }}
                          placeholder="Выберите ретушера"
                          value={requestHeader.retoucher?.id}
                          onChange={(value) => handleRetoucherReassign(value)}
                          allowClear
                          showSearch
                          optionFilterProp="children"
                          filterOption={(input, option) =>
                            option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
                          }
                        >
                          {/* Ensure availableRetouchers is an array before mapping */}
                          {(Array.isArray(availableRetouchers) ? availableRetouchers : []).map(r => (
                            <Option key={r.id} value={r.id}>
                              {r.full_name}
                            </Option>
                          ))}
                        </Select>
                      </Space>
                    </Descriptions.Item>
                    <Descriptions.Item label="Статус заявки">{requestHeader.status?.name || '-'}</Descriptions.Item>
                    <Descriptions.Item label="Дата создания">{dayjs(requestHeader.creation_date).format('DD.MM.YYYY HH:mm')}</Descriptions.Item>
                    <Descriptions.Item label="Дата ретуши">{requestHeader.retouch_date ? dayjs(requestHeader.retouch_date).format('DD.MM.YYYY HH:mm') : '-'}</Descriptions.Item>
                    <Descriptions.Item label="На проверку">{requestHeader.unchecked_product}</Descriptions.Item>
                </Descriptions>
            )}

            <Space style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
                <Space>
                    <Button icon={<CameraOutlined />} onClick={handleCountPhotos} loading={isCounting}>Количество фото</Button>
                    <Button 
                        icon={<CheckSquareOutlined />} 
                        onClick={handleBulkCheck} 
                        loading={isUpdating}
                        disabled={isUpdating || requestHeader?.status?.id !== 3}
                    >
                        Проверить все
                    </Button>
                </Space>
                {requestHeader?.status?.id === 3 && (
                     <Space>
                        <Button type="primary" onClick={() => handleUpdateRequestStatus(5)} disabled={!actionButtonsState.canSetReady || isUpdating}>Готово</Button>
                        <Button type="default" danger onClick={() => handleUpdateRequestStatus(4)} disabled={!actionButtonsState.canSetCorrections || isUpdating}>Правки</Button>
                     </Space>
                )}
            </Space>

            <Table
              columns={columns}
              dataSource={detailData}
              pagination={false}
              scroll={{ x: 1400 }}
              bordered
              size="small"
              rowClassName={getRowClassName}
            />
             <CommentModal
              visible={isCommentModalVisible}
              onOk={handleCommentModalOk}
              onCancel={handleCommentModalCancel}
              initialComment={currentEditingProduct?.comment}
              productBarcode={currentEditingProduct?.st_request_product.product.barcode}
            />
          </Content>
        </Layout>
      </Layout>
    </>
  );
};

export default RetouchRequestDetailPage;