// src/components/Sidebar.jsx
import React, { useState, useEffect, useMemo } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Layout, Menu, Switch, Button, message, Typography, Spin, Space } from 'antd';
import {
  LoginOutlined,
  LogoutOutlined,
  DownOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  CameraOutlined,
  SwapOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';

// УДАЛИТЕ ЭТОТ ИМПОРТ, если API_BASE_URL не используется напрямую в этом файле
// import { API_BASE_URL } from '../../utils/config'; 
import axiosInstance from '../../utils/axiosInstance'; // <-- ИМПОРТ ОБНОВЛЕННОГО AXIOS INSTANCE

const { Sider } = Layout;
const { Title, Text } = Typography;

const WORK_STATUS_RELEVANT_GROUPS = ['Фотограф', 'Старший фотограф', 'Ретушер', 'Старший ретушер'];

const Sidebar = ({ darkMode, setDarkMode }) => {
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [user, setUser] = useState(null);
  const location = useLocation();

  const [onWorkStatus, setOnWorkStatus] = useState(null);
  const [isFetchingWorkStatus, setIsFetchingWorkStatus] = useState(false);
  const [isTogglingWorkStatus, setIsTogglingWorkStatus] = useState(false);
  const [currentOpenKeys, setCurrentOpenKeys] = useState([]);

  // ... (определения menuItems остаются без изменений) ...
  const guestMenuItems = [
    { key: 'newreadyphotos2', label: <Link to="/ready-photos-2">Готовые фото 2.0</Link> },
    { key: 'readyphotos', label: <Link to="/readyphotos">Готовые фото 1.0</Link> },
    { key: 'nofoto', label: <Link to="/nofoto">Товары без фото</Link> },
    { key: 'defect', label: <Link to="/defect">Браки</Link> },
    { key: 'barcode-history', label: <Link to="/barcode-history">История операций</Link> },
    { key: 'public-current-products', label: <Link to="/public-current-products">Текущие товары на ФС</Link> },
    { key: 'public-orders', label: <Link to="/public-orders">Заказы ФС</Link> },
    { key: 'public-invoice-list', label: <Link to="/public-invoice-list">Накладные ФС (Отправка)</Link> },
    { key: 'BarcodeCheckPage', label: <Link to="/BarcodeCheckPage">Проверить ШК</Link> },
    { key: 'BarcodeCheckSeqPage', label: <Link to="/BarcodeCheckSeqPage">Менеджер по ассортименту</Link> },
  ];

  const tovarovedMenuItems = [
    { key: 'stockman-orders', label: <Link to="/stockman-orders">Заказы (Приемка)</Link> },
    { key: 'stockman-strequest-list', label: <Link to="/stockman-strequest-list">Заявки</Link> },
    { key: 'stockman-mark-defect', label: <Link to="/stockman-mark-defect">Пометить брак/вскрыто</Link> },
    { key: 'stockman-invoice-list', label: <Link to="/stockman-invoice-list">Накладные (отправка)</Link> },
    { key: 'stockman-print-barcode', label: <Link to="/stockman-print-barcode">Печать штрихкода</Link> },
  ];

  const SeniorStockmanMenuItems = [
    { key: 'ProblematicProductsPage', label: <Link to="/ProblematicProductsPage">Проблемные товары</Link> }
  ];

  const okzMenuItems = [
    { key: 'okz-orders', label: <Link to="/okz_list">Заказы ФС</Link> },
    { key: 'OrderStats', label: <Link to="/OrderStats">Статистика заказов</Link> }
  ];

  const ManagerMenuItems = [
    { key: 'manager-bulk-update-info', label: <Link to="/manager-bulk-update-info">Обновить ИНФО</Link> },
    { key: 'manager-allstats', label: <Link to="/manager-allstats">Общая статистика</Link> },
    { key: 'ManagerSTRequestList', label: <Link to="/ManagerSTRequestList">Заявки на съемку</Link> },
    { key: 'ManagerRetouchRequestList', label: <Link to="/ManagerRetouchRequestList">Заявки на ретушь</Link> },
    { key: 'AverageProcessingTimePage', label: <Link to="/AverageProcessingTimePage">Среднее время обработки</Link> }
  ];

  const RGTMenuItems = [
    { key: 'RejectedPhotosList', label: <Link to="/RejectedPhotosList">Забрать отклоненные</Link> },
    { key: 'manager-create-order', label: <Link to="/manager-create-order">Создание заказа</Link> },
    { key: 'manager-bulk-upload', label: <Link to="/manager-bulk-upload">Загрузить Штрихкоды</Link> },
    { key: 'ProblematicProductsPage', label: <Link to="/ProblematicProductsPage">Проблемные товары</Link> },
    { key: 'ManagerStockmanStats', label: <Link to="/ManagerStockmanStats">Статистика товароведов</Link> },
    { key: 'AcceptanceDashboardPage', label: <Link to="/AcceptanceDashboardPage">Дэш по приемке</Link> },
  ];

  const RetoucherMenuItems = [
    { key: 'RetoucherRequestsListPage2', label: <Link to="/rt/RetoucherRequestsListPage/2">Заявки в ретуши</Link> },
    { key: 'RetoucherRequestsListPage4', label: <Link to="/rt/RetoucherRequestsListPage/4">Заявки на правках</Link> },
    { type: 'divider', style: {borderTopWidth: '5px', marginTop: '5px', marginBottom: '5px' }, },
    { key: 'RetoucherRenderCheck', label: <Link to="/RetoucherRenderCheck">Отбор и рендеры</Link> },
    { key: 'RetoucherRenderEdit', label: <Link to="/RetoucherRenderEdit">Правки по рендерам</Link> },
  ];

  const SeniorRetoucherMenuItems = [
    { key: 'srt-create-requests', label: <Link to="/srt/CreateRetouchRequestsPage">🆕Создание заявок</Link> },
    { key: 'srt-list-1', label: <Link to="/srt/RetouchRequestsListPage/1">🆕Созданные заявки</Link> },
    { key: 'srt-list-2', label: <Link to="/srt/RetouchRequestsListPage/2">🔄Заявки в ретуши</Link> },
    { key: 'srt-list-3', label: <Link to="/srt/RetouchRequestsListPage/3">▶️Заявки на проверку</Link> },
    { key: 'srt-list-4', label: <Link to="/srt/RetouchRequestsListPage/4">🔄Заявки на правках</Link> },
    { key: 'srt-list-5', label: <Link to="/srt/RetouchRequestsListPage/5">Готовые заявки</Link> },
    { key: 'srt-stats', label: <Link to="/srt/RetoucherStatsPage">Статистика</Link> },
    { type: 'divider', style: {borderTopWidth: '5px', marginTop: '5px', marginBottom: '5px' }, },
    { key: 'SeniorRetoucherCheck', label: <Link to="/SeniorRetoucherCheck">Проверка рендеров</Link> },
    { key: 'SeniorRetoucherStats', label: <Link to="/SeniorRetoucherStats">Статистика рендеров</Link> },
    { key: 'ModerationRejects', label: <Link to="/ModerationRejects">Отклоненные рендеры</Link> }
  ];

  const RGOIMenuItems = [
    { key: 'SeniorRetoucherStats', label: <Link to="/SeniorRetoucherStats">Статистика рендеров</Link> },
    { key: 'ModerationRejects', label: <Link to="/ModerationRejects">Отклоненные рендеры</Link> },
    { key: 'AllRenders', label: <Link to="/AllRenders">Все рендеры</Link> },
  ];

  const ModeratorMenuItems = [
    { key: 'ModerationUpload', label: <Link to="/ModerationUpload">Загрузка рендеров</Link> },
    { key: 'ModerationStudioUpload', label: <Link to="/ModerationStudioUpload">Загрузка фото от ФС</Link> },
    { key: 'MyUploadStats', label: <Link to="/MyUploadStats">Моя статистика</Link> },
  ];

  const SeniorModeratorMenuItems = [
    { key: 'ModerationStats', label: <Link to="/ModerationStats">Статистика по загрузкам</Link> }
  ];

  const seniorphotographerMenuItems = [
    { key: 'sph-created-st-requests', label: <Link to="/sph/created-st-requests">Созданные заявки</Link> },
    { key: 'sph-inprogress-st-requests', label: <Link to="/sph/inprogress-st-requests">Заявки на съемке</Link> },
    { key: 'sph-filmed-st-requests', label: <Link to="/sph/filmed-st-requests">Отснятые заявки</Link> },
    { key: 'sph-NoPhotoPage', label: <Link to="/sph/NoPhotoPage">Без фото</Link> },
    { key: 'sph-DailyStatsPage', label: <Link to="/sph/DailyStatsPage">Статистика</Link> }
  ];


  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      setUser(JSON.parse(storedUser));
    } else {
      // Не устанавливаем гостя по умолчанию здесь, если пользователь не найден.
      // Логика редиректа или отображения состояния "не авторизован" должна быть централизована
      // или управляться через защищенные роуты.
      // Если пользователь не найден в localStorage, и это не страница логина,
      // axiosInstance при попытке сделать защищенный запрос сам перенаправит на /login, если токена нет.
    }
  }, []);

  // Удаляем getAccessToken, так как axiosInstance управляет токенами
  // const getAccessToken = () => localStorage.getItem('accessToken');

  useEffect(() => {
    const fetchInitialWorkStatus = async () => {
      // Проверяем, действительно ли пользователь загружен и принадлежит к релевантной группе
      const localUser = localStorage.getItem('user');
      if (!localUser || !JSON.parse(localUser).groups || !JSON.parse(localUser).groups.some(group => WORK_STATUS_RELEVANT_GROUPS.includes(group))) {
        setOnWorkStatus(null);
        return;
      }
      // Нет необходимости проверять токен здесь, interceptor это сделает

      setIsFetchingWorkStatus(true);
      try {
        // Используем axiosInstance. Заголовки Authorization будут добавлены автоматически.
        const response = await axiosInstance.get(`/user/work-status/`);
        setOnWorkStatus(response.data.on_work);
      } catch (error) {
        // Interceptor уже должен был обработать 401 (обновить токен или редиректнуть на /login)
        // Здесь обрабатываем другие возможные ошибки от API
        if (error.response && error.response.status !== 401) {
          message.error(error.response?.data?.detail || error.message || 'Не удалось загрузить статус "На смене".');
        } else if (!error.response) { // Ошибки сети или другие не-HTTP ошибки
            message.error('Сетевая ошибка или не удалось загрузить статус "На смене".');
        }
        // Если ошибка 401 обработана интерсептором (например, редирект), этот блок может не выполниться
        // или выполнится после неудачной попытки обновления.
        setOnWorkStatus(null);
      } finally {
        setIsFetchingWorkStatus(false);
      }
    };

    // Вызываем fetchInitialWorkStatus только если user из localStorage указывает на действительного пользователя
    const storedUser = localStorage.getItem('user');
    if (storedUser && JSON.parse(storedUser).id) { // Проверяем наличие id, чтобы отличить от "гостя по умолчанию"
        fetchInitialWorkStatus();
    } else if (!storedUser && location.pathname !== '/login') {
      // Если нет пользователя и мы не на странице логина, возможно, стоит инициировать проверку,
      // или положиться на то, что защищенные роуты или первый запрос API через axiosInstance сделают редирект.
    }
  }, [location.pathname]); // Добавляем location.pathname в зависимости, чтобы перепроверять при смене роута, если user в localStorage изменился

  const handleToggleWorkStatus = async () => {
    // Нет необходимости проверять токен здесь
    setIsTogglingWorkStatus(true);
    try {
      // Используем axiosInstance. Заголовки и обновление токена управляются автоматически.
      const response = await axiosInstance.post(`/user/toggle-work-status/`);
      setOnWorkStatus(response.data.on_work);
      message.success(response.data.message || 'Статус "На смене" успешно обновлен!');
    } catch (error) {
      if (error.response && error.response.status !== 401) {
         message.error(error.response?.data?.detail || error.message || 'Не удалось переключить статус.');
      } else if (!error.response) {
         message.error('Сетевая ошибка или не удалось переключить статус.');
      }
      // Если 401, interceptor уже должен был сработать.
    } finally {
      setIsTogglingWorkStatus(false);
    }
  };

  const toggleTheme = (checked) => {
    setDarkMode(checked);
    localStorage.setItem('appTheme', checked ? 'dark' : 'light'); // Сохраняем тему
  };
  
  // Загрузка темы при инициализации
  useEffect(() => {
    const savedTheme = localStorage.getItem('appTheme');
    if (savedTheme) {
      setDarkMode(savedTheme === 'dark');
    }
  }, [setDarkMode]);


  const handleLoginLogout = () => {
    const localUserString = localStorage.getItem('user');
    const localUser = localUserString ? JSON.parse(localUserString) : null;
    const isGuest = !localUser || !localUser.id || (localUser.groups && localUser.groups.includes('Гость'));

    if (!isGuest) {
      // Опционально: отправить запрос на бэкенд для инвалидации refresh токена
      // const currentRefreshToken = localStorage.getItem('refreshToken');
      // if (currentRefreshToken) {
      //   axiosInstance.post('/api/logout/', { refresh: currentRefreshToken }) // Пример эндпоинта
      //     .catch(err => console.error("Failed to logout on backend", err));
      // }

      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      localStorage.removeItem('user');
      setUser(null); // Сброс состояния пользователя в компоненте
      setOnWorkStatus(null);
      setCurrentOpenKeys([]); 
      message.success('Вы вышли из системы');
      window.location.href = '/login'; // Перенаправление на страницу входа
    } else {
      window.location.href = '/login';
    }
  };

  const menuItems = useMemo(() => {
    const currentLocalUser = localStorage.getItem('user');
    const userForMenu = currentLocalUser ? JSON.parse(currentLocalUser) : { groups: ['Гость'] };

    const items = [
      { key: 'main', icon: <UserOutlined />, label: <Link to="/">Главная</Link> },
      { key: 'guestDropdownBase', icon: <DownOutlined />, label: 'Гость', children: guestMenuItems },
      { key: 'okzDropdownLimited', icon: <DownOutlined />, label: 'ОКЗ (Только для ОКЗ)', children: okzMenuItems }
    ];
    if (userForMenu && userForMenu.groups) {
      if (userForMenu.groups.includes('Товаровед')) { items.push({ key: 'tovDropdown', icon: <DownOutlined />, label: 'Товаровед', children: tovarovedMenuItems }); }
      if (userForMenu.groups.includes('Старший товаровед')) { items.push({ key: 'SeniorStockmanDropdown', icon: <DownOutlined />, label: 'Старший товаровед', children: SeniorStockmanMenuItems }); }
      if (userForMenu.groups.includes('Менеджер')) { items.push({ key: 'managerDropdown', icon: <DownOutlined />, label: 'Менеджер', children: ManagerMenuItems }); }
      if (userForMenu.groups.includes('РГТ')) { items.push({ key: 'RGTDropdown', icon: <DownOutlined />, label: 'РГТ', children: RGTMenuItems }); }
      if (userForMenu.groups.includes('Ретушер')) { items.push({ key: 'RetoucherDropdown', icon: <DownOutlined />, label: 'Ретушер', children: RetoucherMenuItems }); }
      if (userForMenu.groups.includes('Старший ретушер')) { items.push({ key: 'SeniorRetoucherDropdown', icon: <DownOutlined />, label: 'Старший ретушер', children: SeniorRetoucherMenuItems }); }
      if (userForMenu.groups.includes('Moderator')) { items.push({ key: 'ModeratorDropdown', icon: <DownOutlined />, label: 'Модератор', children: ModeratorMenuItems }); }
      if (userForMenu.groups.includes('SeniorModerator')) { items.push({ key: 'SeniorModeratorDropdown', icon: <DownOutlined />, label: 'Старший модератор', children: SeniorModeratorMenuItems }); }
      if (userForMenu.groups.includes('РГОИ')) { items.push({ key: 'RGOIDropdown', icon: <DownOutlined />, label: 'РГОИ', children: RGOIMenuItems }); }
      if (userForMenu.groups.includes('Старший фотограф')) { items.push({ key: 'seniorphotographerDropdown', icon: <CameraOutlined />, label: 'Старший фотограф', children: seniorphotographerMenuItems }); }
    }
    return items;
  }, [location.pathname]); // Обновляем меню при смене user или pathname (косвенно через selectedKey -> determineOpenKeys)


  // Обновляем user state из localStorage, чтобы UI реагировал на изменения (например, после логина/логаута)
  useEffect(() => {
    const handleStorageChange = () => {
      const storedUser = localStorage.getItem('user');
      setUser(storedUser ? JSON.parse(storedUser) : null);
    };

    window.addEventListener('storage', handleStorageChange); // Слушаем изменения в localStorage из других вкладок
    handleStorageChange(); // Первичная установка

    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);


  const selectedKey = useMemo(() => {
    let key = 'main';
    const pathname = location.pathname;
    if (pathname.startsWith('/ready-photos-2')) { key = 'newreadyphotos2'; }
    else if (pathname.startsWith('/srt/CreateRetouchRequestsPage')) { key = 'srt-create-requests'; }
    else if (pathname.startsWith('/srt/RetouchRequestsListPage/1')) { key = 'srt-list-1'; }
    else if (pathname.startsWith('/srt/RetouchRequestsListPage/2')) { key = 'srt-list-2'; }
    else if (pathname.startsWith('/srt/RetouchRequestsListPage/3')) { key = 'srt-list-3'; }
    else if (pathname.startsWith('/srt/RetouchRequestsListPage/4')) { key = 'srt-list-4'; }
    else if (pathname.startsWith('/srt/RetouchRequestsListPage/5')) { key = 'srt-list-5'; }
    else if (pathname.startsWith('/srt/RetoucherStatsPage')) { key = 'srt-stats'; }
    else if (pathname.startsWith('/rt/RetoucherRequestsListPage/2') || pathname.startsWith('/rt/RetoucherRequestDetailPage')) { key = 'RetoucherRequestsListPage2'; }
    else if (pathname.startsWith('/rt/RetoucherRequestsListPage/4')) { key = 'RetoucherRequestsListPage4'; }
    else if (pathname.startsWith('/srt/RetouchRequestDetailPage')) { key = 'srt-list-2'; }
    else if (pathname.startsWith('/readyphotos')) { key = 'readyphotos'; }
    else if (pathname.startsWith('/nofoto')) { key = 'nofoto'; }
    else if (pathname.startsWith('/defect')) { key = 'defect'; }
    else if (pathname.startsWith('/barcode-history')) { key = 'barcode-history'; }
    else if (pathname.startsWith('/public-orders')) { key = 'public-orders'; }
    else if (pathname.startsWith('/public-order-detail')) { key = 'public-orders'; }
    else if (pathname.startsWith('/public-current-products')) { key = 'public-current-products'; }
    else if (pathname.startsWith('/BarcodeCheckPage')) { key = 'BarcodeCheckPage'; }
    else if (pathname.startsWith('/BarcodeCheckSeqPage')) { key = 'BarcodeCheckSeqPage'; }
    else if (pathname.startsWith('/stockman-orders')) { key = 'stockman-orders'; }
    else if (pathname.startsWith('/stockman-order-detail/')) { key = 'stockman-orders'; }
    else if (pathname.startsWith('/stockman-strequest-list')) { key = 'stockman-strequest-list'; }
    else if (pathname.startsWith('/stockman-strequest-detail')) { key = 'stockman-strequest-list'; }
    else if (pathname.startsWith('/stockman-invoice-list')) { key = 'stockman-invoice-list'; }
    else if (pathname.startsWith('/stockman-invoice-detail')) { key = 'stockman-invoice-list'; }
    else if (pathname.startsWith('/stockman-mark-defect')) { key = 'stockman-mark-defect'; }
    else if (pathname.startsWith('/stockman-print-barcode')) { key = 'stockman-print-barcode'; }
    else if (pathname.startsWith('/okz_list') || pathname.startsWith('/okz_orders')) { key = 'okz-orders'; }
    else if (pathname.startsWith('/OrderStats') || pathname.startsWith('/OrderStats')) { key = 'OrderStats'; }
    else if (pathname.startsWith('/public-invoice-list') || pathname.startsWith('/public-invoice-detail')) { key = 'public-invoice-list'; }
    else if (pathname.startsWith('/ProblematicProductsPage')) { key = 'ProblematicProductsPage'; }
    else if (pathname.startsWith('/manager-create-order')) { key = 'manager-create-order'; }
    else if (pathname.startsWith('/manager-bulk-upload')) { key = 'manager-bulk-upload'; }
    else if (pathname.startsWith('/manager-bulk-update-info')) { key = 'manager-bulk-update-info'; }
    else if (pathname.startsWith('/RejectedPhotosList')) { key = 'RejectedPhotosList'; }
    else if (pathname.startsWith('/manager-allstats')) { key = 'manager-allstats'; }
    else if (pathname.startsWith('/ManagerSTRequestList') || pathname.startsWith('/ManagerSTRequestDetail')) { key = 'ManagerSTRequestList'; }
    else if (pathname.startsWith('/ManagerRetouchRequestList') || pathname.startsWith('/ManagerRetouchRequestDetail')) { key = 'ManagerRetouchRequestList'; }
    else if (pathname.startsWith('/ManagerStockmanStats')) { key = 'ManagerStockmanStats'; }
    else if (pathname.startsWith('/AverageProcessingTimePage')) { key = 'AverageProcessingTimePage'; }
    else if (pathname.startsWith('/AllRenders')) { key = 'AllRenders'; }
    else if (pathname.startsWith('/AcceptanceDashboardPage')) { key = 'AcceptanceDashboardPage'; }
    else if (pathname.startsWith('/RetoucherRenderCheck')) { key = 'RetoucherRenderCheck'; }
    else if (pathname.startsWith('/RetoucherRenderEdit')) { key = 'RetoucherRenderEdit'; }
    else if (pathname.startsWith('/SeniorRetoucherCheck')) { key = 'SeniorRetoucherCheck'; }
    else if (pathname.startsWith('/SeniorRetoucherStats')) { key = 'SeniorRetoucherStats'; }
    else if (pathname.startsWith('/ModerationRejects')) { key = 'ModerationRejects'; }
    else if (pathname.startsWith('/ModerationUpload')) { key = 'ModerationUpload'; }
    else if (pathname.startsWith('/ModerationStudioUpload')) { key = 'ModerationStudioUpload'; }
    else if (pathname.startsWith('/MyUploadStats')) { key = 'MyUploadStats'; }
    else if (pathname.startsWith('/ModerationStats')) { key = 'ModerationStats'; }
    else if (pathname.startsWith('/sph/created-st-requests') || pathname.startsWith('/sph/st-request-detail/')) { key = 'sph-created-st-requests'; }
    else if (pathname.startsWith('/sph/inprogress-st-requests')) { key = 'sph-inprogress-st-requests'; }
    else if (pathname.startsWith('/sph/filmed-st-requests')) { key = 'sph-filmed-st-requests'; }
    else if (pathname.startsWith('/sph/NoPhotoPage')) { key = 'sph-NoPhotoPage'; }
    else if (pathname.startsWith('/sph/DailyStatsPage')) { key = 'sph-DailyStatsPage'; }
    return key;
  }, [location.pathname]);

  useEffect(() => {
    const currentLocalUser = localStorage.getItem('user');
    const userForMenu = currentLocalUser ? JSON.parse(currentLocalUser) : { groups: ['Гость'] };

    const determineOpenKeys = () => {
      const keysToOpen = [];
      if (selectedKey && selectedKey !== 'main' && menuItems && menuItems.length > 0) {
        for (const menuItem of menuItems) { // Используем menuItems, которые уже зависят от userForMenu
          if (menuItem.children && menuItem.children.some(child => child.key === selectedKey)) {
            if (!keysToOpen.includes(menuItem.key)) {
              keysToOpen.push(menuItem.key);
            }
          }
        }
        // Логика для ProblematicProductsPage и других общих ключей
        if (selectedKey === 'ProblematicProductsPage' && userForMenu && userForMenu.groups) {
          if (userForMenu.groups.includes('Старший товаровед') && menuItems.find(m => m.key === 'SeniorStockmanDropdown')) {
            if (!keysToOpen.includes('SeniorStockmanDropdown')) keysToOpen.push('SeniorStockmanDropdown');
          }
          if (userForMenu.groups.includes('РГТ') && menuItems.find(m => m.key === 'RGTDropdown')) {
            if (!keysToOpen.includes('RGTDropdown')) keysToOpen.push('RGTDropdown');
          }
        }
        if (selectedKey === 'SeniorRetoucherStats' && userForMenu && userForMenu.groups) {
           if (userForMenu.groups.includes('Старший ретушер') && menuItems.find(m => m.key === 'SeniorRetoucherDropdown')) {
              if (!keysToOpen.includes('SeniorRetoucherDropdown')) keysToOpen.push('SeniorRetoucherDropdown');
          }
          if (userForMenu.groups.includes('РГОИ') && menuItems.find(m => m.key === 'RGOIDropdown')) {
              if (!keysToOpen.includes('RGOIDropdown')) keysToOpen.push('RGOIDropdown');
          }
        }
        if (selectedKey === 'ModerationRejects' && userForMenu && userForMenu.groups) {
           if (userForMenu.groups.includes('Старший ретушер') && menuItems.find(m => m.key === 'SeniorRetoucherDropdown')) {
              if (!keysToOpen.includes('SeniorRetoucherDropdown')) keysToOpen.push('SeniorRetoucherDropdown');
          }
          if (userForMenu.groups.includes('РГОИ') && menuItems.find(m => m.key === 'RGOIDropdown')) {
              if (!keysToOpen.includes('RGOIDropdown')) keysToOpen.push('RGOIDropdown');
          }
        }
      }
      setCurrentOpenKeys(keysToOpen.length > 0 ? [...new Set(keysToOpen)] : []);
    };
    determineOpenKeys();
  }, [selectedKey, menuItems]); // menuItems уже содержит зависимость от user (косвенно от localStorage)

  const showWorkStatusSection = user && user.groups && user.groups.some(group => WORK_STATUS_RELEVANT_GROUPS.includes(group));
  const isUserTrulyLoggedIn = user && user.id && user.groups && !user.groups.includes('Гость');


  return (
    <>
      {sidebarVisible && (
        <Sider
          width={250}
          style={{ minHeight: '100vh', backgroundColor: darkMode ? '#001529' : '#fff', display: 'flex', flexDirection: 'column' }}
          breakpoint="lg" // Добавлено для автоматического скрытия на малых экранах
          collapsedWidth="0" // Полностью скрывать при схлопывании
          onBreakpoint={broken => { // Можно использовать для управления состоянием видимости
             if (broken) setSidebarVisible(false);
          }}
          trigger={null} // Убираем стандартный триггер, так как у нас своя кнопка
          collapsible
          collapsed={!sidebarVisible} // Управляем состоянием collapsed
        >
          <div style={{ flexShrink: 0 }}> {/* Шапка сайдбара */}
            <div style={{ textAlign: 'center', margin: '16px 0' }}>
              <Title level={2} style={{ margin: 0, color: '#90ee90' }}>Teez Studio 3.0</Title>
            </div>
            <div style={{ textAlign: 'center', marginBottom: 16, padding: '0 16px' }}>
              <Switch
                checked={darkMode}
                onChange={toggleTheme}
                checkedChildren="Dark"
                unCheckedChildren="Light"
                style={{ width: 'auto' }}
              />
            </div>
            {showWorkStatusSection && (
              <div style={{ padding: '0 16px 16px 16px', borderBottom: `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.12)' : '#f0f0f0'}`, marginBottom: 8 }}>
                <Title level={5} style={{ marginBottom: 8, color: darkMode ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.85)' }}>
                  Статус смены
                </Title>
                {isFetchingWorkStatus ? (
                  <div style={{ textAlign: 'center' }}> <Spin size="small" /> <Text type="secondary"> Загрузка...</Text> </div>
                ) : onWorkStatus !== null ? (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text style={{ color: darkMode ? 'rgba(255,255,255,0.75)' : 'rgba(0,0,0,0.75)' }}>
                      <InfoCircleOutlined style={{ marginRight: 8, color: onWorkStatus ? '#52c41a' : '#faad14' }} />
                      {onWorkStatus ? 'На смене' : 'Не на смене'}
                    </Text>
                    <Button
                      type="default"
                      icon={<SwapOutlined />}
                      block
                      onClick={handleToggleWorkStatus}
                      loading={isTogglingWorkStatus}
                      size="small"
                    >
                      Переключить
                    </Button>
                  </Space>
                ) : (
                  <Text type="secondary" style={{ display: 'block', textAlign: 'center' }}>Не удалось загрузить статус</Text>
                )}
              </div>
            )}
          </div>
          
          <div style={{ flexGrow: 1, overflowY: 'auto', overflowX: 'hidden' }}> {/* Основное меню */}
            <Menu
              selectedKeys={[selectedKey]}
              openKeys={currentOpenKeys}
              onOpenChange={setCurrentOpenKeys}
              mode="inline"
              theme={darkMode ? 'dark' : 'light'}
              items={menuItems} // menuItems теперь обновляется через useEffect -> handleStorageChange -> setUser -> useMemo
              style={{ borderRight: 0 }}
            />
          </div>

          <div style={{ padding: 16, borderTop: `1px solid ${darkMode ? 'rgba(255, 255, 255, 0.12)' : '#f0f0f0'}`, flexShrink: 0 }}> {/* Футер сайдбара */}
            {user && user.id ? ( // Проверяем user.id для отображения имени и кнопки выхода
              <>
                <div style={{ marginBottom: 8, color: darkMode ? '#fff' : '#000', textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user.first_name} {user.last_name}
                </div>
                <Button
                  type="primary"
                  danger={isUserTrulyLoggedIn} // Кнопка красная если пользователь действительно вошел (не гость)
                  block
                  onClick={handleLoginLogout}
                  icon={isUserTrulyLoggedIn ? <LogoutOutlined /> : <LoginOutlined />}
                >
                  {isUserTrulyLoggedIn ? 'Выйти' : 'Войти'}
                </Button>
              </>
            ) : ( 
              <Button type="primary" block onClick={handleLoginLogout} icon={<LoginOutlined />}>
                Войти
              </Button>
            )}
          </div>
        </Sider>
      )}
      <Button
        onClick={() => setSidebarVisible(!sidebarVisible)}
        style={{
          position: 'fixed',
          bottom: 20,
          left: sidebarVisible ? 250 + 10 : 10, // Небольшой отступ от края сайдбара или экрана
          zIndex: 1000, // Убедитесь, что zIndex выше других элементов, если есть проблемы с перекрытием
          transition: 'left 0.2s ease-in-out',
        }}
        type="primary"
        shape="circle"
        icon={sidebarVisible ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
        size="large"
      />
    </>
  );
};

export default Sidebar;