import React, { useState, useEffect, useCallback } from 'react';
import { Layout, Table, Tabs, Pagination, message, Spin } from 'antd';
import axios from 'axios';
import Sidebar from '../../components/Layout/Sidebar'; // Убедитесь, что путь правильный
import { API_BASE_URL } from '../../utils/config'; // Убедитесь, что путь правильный

const { Content } = Layout;
const { TabPane } = Tabs;
const PAGE_SIZE = 100;

const ProblematicProductsPage = ({ darkMode, setDarkMode }) => {
    const [activeTab, setActiveTab] = useState('1');

    // --- Состояния для Таба 1 ---
    const [data1, setData1] = useState([]);
    const [loading1, setLoading1] = useState(false);
    const [pagination1, setPagination1] = useState({ current: 1, pageSize: PAGE_SIZE, total: 0 });
    const [sorter1, setSorter1] = useState({ field: 'income_date', order: 'ascend' });

    // --- Состояния для Таба 2 ---
    const [data2, setData2] = useState([]);
    const [loading2, setLoading2] = useState(false);
    const [pagination2, setPagination2] = useState({ current: 1, pageSize: PAGE_SIZE, total: 0 });
    const [sorter2, setSorter2] = useState({ field: 'barcode', order: 'ascend' });

    // --- Состояния для Таба 3 (Новая вкладка) ---
    const [data3, setData3] = useState([]);
    const [loading3, setLoading3] = useState(false);
    const [pagination3, setPagination3] = useState({ current: 1, pageSize: PAGE_SIZE, total: 0 });
    const [sorter3, setSorter3] = useState({ field: 'income_date', order: 'ascend' });


    useEffect(() => {
        document.title = 'Проблемные товары';
    }, []);

    const formatOrdering = (sorter) => {
        if (sorter && sorter.field && sorter.order) {
            return sorter.order === 'descend' ? `-${sorter.field}` : sorter.field;
        }
        return null;
    };

    useEffect(() => {
        let currentPage, currentSorter, setLoadingFunc, setDataFunc, setPaginationFunc, apiUrl, defaultOrderingField;

        if (activeTab === '1') {
            currentPage = pagination1.current;
            currentSorter = sorter1;
            setLoadingFunc = setLoading1;
            setDataFunc = setData1;
            setPaginationFunc = setPagination1;
            apiUrl = `${API_BASE_URL}/st/problematic-products-1/`;
            defaultOrderingField = 'income_date';
        } else if (activeTab === '2') {
            currentPage = pagination2.current;
            currentSorter = sorter2;
            setLoadingFunc = setLoading2;
            setDataFunc = setData2;
            setPaginationFunc = setPagination2;
            apiUrl = `${API_BASE_URL}/st/problematic-products-2/`;
            defaultOrderingField = 'barcode';
        } else if (activeTab === '3') { // Логика для новой вкладки
            currentPage = pagination3.current;
            currentSorter = sorter3;
            setLoadingFunc = setLoading3;
            setDataFunc = setData3;
            setPaginationFunc = setPagination3;
            apiUrl = `${API_BASE_URL}/st/problematic-products-3/`;
            defaultOrderingField = 'income_date';
        } else {
            return; // Если нет активной вкладки, ничего не делаем
        }

        const fetchDataForTab = async () => {
            console.log(`Fetching data for Tab: ${activeTab}, Page: ${currentPage}, Sorter:`, currentSorter);
            setLoadingFunc(true);

            let orderingParam = formatOrdering(currentSorter);
            if (!orderingParam) {
                orderingParam = defaultOrderingField;
            }

            const params = {
                page: currentPage,
                page_size: PAGE_SIZE,
                ordering: orderingParam,
            };

            try {
                const response = await axios.get(apiUrl, { params });
                const results = response.data.results || [];
                const totalCount = response.data.count || 0;

                setDataFunc(results.map(item => ({ ...item, key: item.barcode || `${item.name}-${item.strequest || ''}-${Math.random()}` })));

                setPaginationFunc(prev => {
                    if (prev.total !== totalCount || prev.current !== currentPage) {
                        return { ...prev, total: totalCount, current: currentPage };
                    }
                    return prev;
                });

            } catch (error) {
                console.error(`Ошибка загрузки данных для таба ${activeTab}:`, error);
                message.error(`Не удалось загрузить данные для таба ${activeTab}`);
                setDataFunc([]);
                setPaginationFunc(prev => ({ ...prev, total: 0, current: 1 }));
            } finally {
                setLoadingFunc(false);
            }
        };

        fetchDataForTab();

    }, [
        activeTab,
        pagination1.current, sorter1.field, sorter1.order,
        pagination2.current, sorter2.field, sorter2.order,
        pagination3.current, sorter3.field, sorter3.order, // Добавляем зависимости для 3-й вкладки
    ]);

    const handleTabChange = (key) => {
        setActiveTab(key);
    };

    const handlePageChange = (page, tabKey) => {
        if (tabKey === '1') {
            setPagination1(prev => ({ ...prev, current: page }));
        } else if (tabKey === '2') {
            setPagination2(prev => ({ ...prev, current: page }));
        } else if (tabKey === '3') { // Для новой вкладки
            setPagination3(prev => ({ ...prev, current: page }));
        }
    };

    const handleTableChange = (pagination, filters, sorter, tabKey) => {
        let defaultSortOrder = 'ascend';
        if (tabKey === '1') defaultSortOrder = 'ascend';
        else if (tabKey === '2') defaultSortOrder = 'ascend';
        else if (tabKey === '3') defaultSortOrder = 'ascend';


        const newSorter = {
            field: sorter.field,
            order: sorter.order || defaultSortOrder,
        };
        const newCurrentPage = 1;

        if (tabKey === '1') {
            setSorter1(newSorter);
            setPagination1(prev => ({ ...prev, current: newCurrentPage }));
        } else if (tabKey === '2') {
            setSorter2(newSorter);
            setPagination2(prev => ({ ...prev, current: newCurrentPage }));
        } else if (tabKey === '3') { // Для новой вкладки
            setSorter3(newSorter);
            setPagination3(prev => ({ ...prev, current: newCurrentPage }));
        }
    };

    const columns1 = [
        { title: 'Штрихкод', dataIndex: 'barcode', key: 'barcode', sorter: true },
        { title: 'Наименование', dataIndex: 'name', key: 'name', sorter: true },
        { title: 'Дата приемки', dataIndex: 'income_date', key: 'income_date', sorter: true },
        { title: 'Товаровед приемки', dataIndex: 'income_stockman', key: 'income_stockman', sorter: true, render: (text) => text || '-' },
        { title: 'Инфо', dataIndex: 'info', key: 'info', sorter: true, render: (text) => text || '-' },
        { title: 'При-т', dataIndex: 'priority', key: 'priority', sorter: true, render: (priority) => (priority ? 'Да' : '-') },
    ];

    const columns2 = [
        { title: 'Штрихкод', dataIndex: 'barcode', key: 'barcode', sorter: true },
        { title: 'Наименование', dataIndex: 'name', key: 'name', sorter: true },
        { title: 'Дата приемки', dataIndex: 'income_date', key: 'income_date', sorter: true },
        { title: 'Товаровед приемки', dataIndex: 'income_stockman', key: 'income_stockman', sorter: true, render: (text) => text || '-' },
        { title: 'Инфо', dataIndex: 'info', key: 'info', sorter: true, render: (text) => text || '-' },
        { title: 'При-т', dataIndex: 'priority', key: 'priority', sorter: true, render: (priority) => (priority ? 'Да' : '-') },
        {
            title: 'Заявки',
            dataIndex: 'strequestlist',
            key: 'strequestlist',
            sorter: false, // Обычно такие поля не сортируются на бэке напрямую
            render: (requests) => (Array.isArray(requests) && requests.length > 0 ? requests.join(', ') : '-'),
        },
    ];

    // Колонки для новой вкладки
    const columns3 = [
        { title: 'Штрихкод', dataIndex: 'barcode', key: 'barcode', sorter: true },
        { title: 'Наименование', dataIndex: 'name', key: 'name', sorter: true },
        { title: 'Статус', dataIndex: 'product_move_status_name', key: 'product_move_status_name', sorter: false },
        { title: 'Дата приемки', dataIndex: 'income_date', key: 'income_date', sorter: true },
        { title: 'Товаровед приемки', dataIndex: 'income_stockman', key: 'income_stockman', sorter: true, render: (text) => text || '-' },
        { title: 'Инфо', dataIndex: 'info', key: 'info', sorter: true, render: (text) => text || '-' },
        { title: 'При-т', dataIndex: 'priority', key: 'priority', sorter: true, render: (priority) => (priority ? 'Да' : '-') },
        { title: 'Заявка (статус 5)', dataIndex: 'strequest', key: 'strequest', sorter: false, render: (text) => text || '-' },
        { title: 'Дата съемки товара', dataIndex: 'st_request_product_photo_date', key: 'st_request_product_photo_date', sorter: true },
    ];

    return (
        <Layout style={{ minHeight: '100vh' }}>
            <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
            <Content style={{ padding: 16 }}>
                <h2>Проблемные товары</h2>
                <Tabs activeKey={activeTab} onChange={handleTabChange}>
                    <TabPane tab="Принятые без заявок" key="1">
                        <Pagination
                            current={pagination1.current}
                            pageSize={PAGE_SIZE}
                            total={pagination1.total}
                            onChange={(page) => handlePageChange(page, '1')}
                            showSizeChanger={false}
                            showTotal={(total) => `Всего ${total} записей`}
                            style={{ marginBottom: 16 }}
                        />
                        <Table
                            columns={columns1}
                            dataSource={data1}
                            loading={loading1}
                            onChange={(p, f, s) => handleTableChange(p, f, s, '1')}
                            pagination={false}
                            rowKey="key"
                            size="small"
                        />
                    </TabPane>
                    <TabPane tab="Дубликаты в заявках" key="2">
                        <Pagination
                            current={pagination2.current}
                            pageSize={PAGE_SIZE}
                            total={pagination2.total}
                            onChange={(page) => handlePageChange(page, '2')}
                            showSizeChanger={false}
                            showTotal={(total) => `Всего ${total} записей`}
                            style={{ marginBottom: 16 }}
                        />
                        <Table
                            columns={columns2}
                            dataSource={data2}
                            loading={loading2}
                            onChange={(p, f, s) => handleTableChange(p, f, s, '2')}
                            pagination={false}
                            rowKey="key"
                            size="small"
                        />
                    </TabPane>
                    {/* Новая вкладка */}
                    <TabPane tab="Отснято более суток назад" key="3">
                        <Pagination
                            current={pagination3.current}
                            pageSize={PAGE_SIZE}
                            total={pagination3.total}
                            onChange={(page) => handlePageChange(page, '3')}
                            showSizeChanger={false}
                            showTotal={(total) => `Всего ${total} записей`}
                            style={{ marginBottom: 16 }}
                        />
                        <Table
                            columns={columns3}
                            dataSource={data3}
                            loading={loading3}
                            onChange={(p, f, s) => handleTableChange(p, f, s, '3')}
                            pagination={false}
                            rowKey="key"
                            size="small"
                        />
                    </TabPane>
                </Tabs>
            </Content>
        </Layout>
    );
};

export default ProblematicProductsPage;