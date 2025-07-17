// src/App.jsx
import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider, theme as antdTheme } from 'antd';
import Home from './pages/Home';
import Login from './pages/Login';

import ReadyPhotos2 from './pages/guest/ReadyPhotos2';
import ReadyPhotos from './pages/guest/ReadyPhotos';
import NofotoPage from './pages/guest/nofoto';
import DefectOperationsPage from './pages/guest/DefectOperationsPage';
import ProductOperationsPage from './pages/guest/ProductOperationsPage';
import PublicOrdersPage from './pages/guest/PublicOrders';
import PublicOrderDetailPage from './pages/guest/PublicOrderDetail';
import GuestInvoiceDetail from './pages/guest/GuestInvoiceDetail';
import GuestInvoiceList from './pages/guest/GuestInvoiceList';
import PublicCurrentProductsPage from './pages/guest/PublicCurrentProductsPage';

import StockmanOrders from './pages/stockman/stockmanorders';
import StockmanOrderDetailPage from './pages/stockman/stockmanorderdetail';
import StockmanSTRequest from './pages/stockman/StockmanSTRequest';
import StockmanSTRequestDetailPage from './pages/stockman/StockmanSTRequestDetail';
import StockmanInvoiceList from './pages/stockman/StockmanInvoiceList';
import StockmanInvoiceDetail from './pages/stockman/StockmanInvoiceDetail';
import StockmanMarkDefect from './pages/stockman/StockmanMarkDefect';
import StockmanPrintBarcode from './pages/stockman/StockmanPrintBarcode';

import ProblematicProductsPage from './pages/SeniorStockman/ProblematicProductsPage';

import OkzOrders from './pages/okz/OkzOrdersList';
import OkzOrderDetail from './pages/okz/OkzOrderDetail';
import OrderStatsPage from './pages/okz/OrderStatsPage';

import ManagerCreateOrder from './pages/manager/ManagerCreateOrder';
import ManagerBulkUploadProducts from './pages/manager/ManagerBulkUploadProducts';
import ManagerBulkUpdateInfo from './pages/manager/ManagerBulkUpdateInfo';
import ManagerStatsPage from './pages/manager/ManagerStatsPage';
import ManagerSTRequestList from './pages/manager/ManagerSTRequestList';
import ManagerSTRequestDetail from './pages/manager/ManagerSTRequestDetail';
import ManagerRetouchRequestList from './pages/manager/ManagerRetouchRequestList';
import ManagerRetouchRequestDetail from './pages/manager/ManagerRetouchRequestDetail';
import ManagerStockmanStats from './pages/manager/ManagerStockmanStats';
import RejectedPhotosList from './pages/manager/RejectedPhotosList';
import RetouchBlockPage from './pages/manager/RetouchBlockPage';
import AllRendersListPage from './pages/manager/ManagerAllRendersListPage';
import AverageProcessingTimePage from './pages/manager/AverageProcessingTimePage';
import BarcodeCheckPage from './pages/manager/BarcodeCheckPage';
import BarcodeSequentialCheckAndExportPage from './pages/manager/BarcodeSequentialCheckAndExportPage';
import AcceptanceDashboardPage from './pages/manager/AcceptanceDashboardPage';

import RetoucherRenderCheck from './pages/Retoucher/RetoucherRenderCheck';
import RetoucherRenderEdit from './pages/Retoucher/RetoucherRenderEdit';
import RetoucherRequestsListPage from './pages/Retoucher/RetoucherRequestsListPage';
import RetoucherRequestDetailPage from './pages/Retoucher/RetoucherRequestDetailPage';

import SeniorRetoucherCheck from './pages/SeniorRetoucher/SeniorRetoucherCheck';
import SeniorRetoucherStats from './pages/SeniorRetoucher/SeniorRetoucherStats';
import ModerationRejects from './pages/SeniorRetoucher/ModerationRejects';
import CreateRetouchRequestsPage from './pages/SeniorRetoucher/CreateRetouchRequestsPage';
import RetouchRequestsListPage from './pages/SeniorRetoucher/RetouchRequestsListPage';
import RetouchRequestDetailPage from './pages/SeniorRetoucher/RetouchRequestDetailPage';
import RetoucherStatsPage from './pages/SeniorRetoucher/RetoucherStatsPage';

import ModerationUpload from './pages/Moderator/ModerationUpload';
import ModerationStats from './pages/Moderator/ModerationStats';
import ModerationStudioUpload from './pages/Moderator/ModerationStudioUpload';
import MyUploadStats from './pages/Moderator/MyUploadStats';

import CreatedSTRequestsPage from './pages/SeniorPhotographer/CreatedSTRequestsPage';
import InProgressSTRequestsPage from './pages/SeniorPhotographer/InProgressSTRequestsPage';
import FilmedSTRequestsPage from './pages/SeniorPhotographer/FilmedSTRequestsPage';
import PhotographerSTRequestDetailPage from './pages/SeniorPhotographer/SPhotographerSTRequestDetailPage';
import ProcessNoPhotoPage from './pages/SeniorPhotographer/ProcessNoPhotoPage';
import DailyStatsPage from './pages/SeniorPhotographer/PhotographersStatsPage';

// СУПЕРАДМИН
import AddBlockedBarcodes from './pages/closed/FS_Manager_AddBlockedBarcodes';
import RetouchRequestProductPage from './pages/superadmin/RetouchRequestProductPage';

function App() {
  const [darkMode, setDarkMode] = useState(
    localStorage.getItem('appTheme') === 'dark'
  );

  useEffect(() => {
    localStorage.setItem('appTheme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  const algorithm = darkMode
    ? antdTheme.darkAlgorithm
    : antdTheme.defaultAlgorithm;

  return (
    <ConfigProvider
      theme={{
        algorithm,
        token: {
          // Меняем глобальный шрифт
          fontFamily: 'Arial, sans-serif',
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          {/* Главная */}
          <Route
            path="/"
            element={<Home darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          {/* Страница "Готовые фото 2.0" */}
          <Route
            path="/ready-photos-2"
            element={<ReadyPhotos2 darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          {/* Страница "Готовые фото 1.0" */}
          <Route
            path="/readyphotos"
            element={<ReadyPhotos darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          {/* Страница "Без фото" */}
          <Route
            path="/nofoto"
            element={<NofotoPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          {/* Страница "Браки" */}
          <Route
            path="/defect"
            element={<DefectOperationsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          {/* Страница "История по штрихкоду" */}
          <Route
            path="/barcode-history"
            element={<ProductOperationsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/public-orders"
            element={<PublicOrdersPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/public-order-detail/:order_number"
            element={<PublicOrderDetailPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/public-invoice-list"
            element={<GuestInvoiceList darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/public-invoice-detail/:invoceNumber"
            element={<GuestInvoiceDetail darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/public-current-products"
            element={<PublicCurrentProductsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />

          {/* ТОВАРОВЕД */}
          
          <Route
            path="/stockman-orders"
            element={<StockmanOrders darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/stockman-order-detail/:order_number"
            element={<StockmanOrderDetailPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/stockman-strequest-list"
            element={<StockmanSTRequest darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/stockman-strequest-detail/:STRequestNumber"
            element={<StockmanSTRequestDetailPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/stockman-invoice-list"
            element={<StockmanInvoiceList darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/stockman-invoice-detail/:invoceNumber"
            element={<StockmanInvoiceDetail darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/stockman-mark-defect"
            element={<StockmanMarkDefect darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/stockman-print-barcode"
            element={<StockmanPrintBarcode darkMode={darkMode} setDarkMode={setDarkMode} />}
          />

          {/* Старший товаровед */}

          <Route
            path="/ProblematicProductsPage"
            element={<ProblematicProductsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />

          {/* OKZ */}

          <Route
            path="/okz_list"
            element={<OkzOrders darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/okz_orders/:order_number"
            element={<OkzOrderDetail darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/OrderStats"
            element={<OrderStatsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />

          {/* Менеджер */}

          <Route
            path="/manager-create-order"
            element={<ManagerCreateOrder darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/manager-bulk-upload"
            element={<ManagerBulkUploadProducts darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/manager-bulk-update-info"
            element={<ManagerBulkUpdateInfo darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/manager-allstats"
            element={<ManagerStatsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/ManagerSTRequestList"
            element={<ManagerSTRequestList darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/ManagerSTRequestDetail/:requestnumber"
            element={<ManagerSTRequestDetail darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/ManagerRetouchRequestList"
            element={<ManagerRetouchRequestList darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/ManagerRetouchRequestDetail/:RequestNumber"
            element={<ManagerRetouchRequestDetail darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/ManagerStockmanStats"
            element={<ManagerStockmanStats darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/RejectedPhotosList"
            element={<RejectedPhotosList darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/RetouchBlockPage"
            element={<RetouchBlockPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/AllRenders"
            element={<AllRendersListPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/AverageProcessingTimePage"
            element={<AverageProcessingTimePage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/BarcodeCheckPage"
            element={<BarcodeCheckPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/BarcodeCheckSeqPage"
            element={<BarcodeSequentialCheckAndExportPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/AcceptanceDashboardPage"
            element={<AcceptanceDashboardPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />

          {/* Ретушер */}

          <Route
            path="/RetoucherRenderCheck"
            element={<RetoucherRenderCheck darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/RetoucherRenderEdit"
            element={<RetoucherRenderEdit darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/rt/RetoucherRequestsListPage/2"
            element={<RetoucherRequestsListPage statusId={2} pageTitle="Заявки в ретуши" darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/rt/RetoucherRequestsListPage/4"
            element={<RetoucherRequestsListPage statusId={4} pageTitle="Заявки на правках" darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/rt/RetoucherRequestDetailPage/:requestNumber"
            element={<RetoucherRequestDetailPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />

          {/* Старший ретушер */}

          <Route
            path="/SeniorRetoucherCheck"
            element={<SeniorRetoucherCheck darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/SeniorRetoucherStats"
            element={<SeniorRetoucherStats darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/ModerationRejects"
            element={<ModerationRejects darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/srt/CreateRetouchRequestsPage"
            element={<CreateRetouchRequestsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/srt/RetouchRequestsListPage/1"
            element={<RetouchRequestsListPage statusId={1} pageTitle="Созданные заявки" darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/srt/RetouchRequestsListPage/2"
            element={<RetouchRequestsListPage statusId={2} pageTitle="Заявки в ретуши" darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/srt/RetouchRequestsListPage/3"
            element={<RetouchRequestsListPage statusId={3} pageTitle="Заявки на проверку" darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/srt/RetouchRequestsListPage/4"
            element={<RetouchRequestsListPage statusId={4} pageTitle="Заявки на правках" darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/srt/RetouchRequestsListPage/5"
            element={<RetouchRequestsListPage statusId={5} pageTitle="Готовые заявки" darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/srt/RetouchRequestDetailPage/:requestNumber"
            element={<RetouchRequestDetailPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/srt/RetoucherStatsPage"
            element={<RetoucherStatsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />


          {/* Модератор */}

          <Route
            path="/ModerationUpload"
            element={<ModerationUpload darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/ModerationStats"
            element={<ModerationStats darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/ModerationStudioUpload"
            element={<ModerationStudioUpload darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/MyUploadStats"
            element={<MyUploadStats darkMode={darkMode} setDarkMode={setDarkMode} />}
          />


          {/* Старший фотограф */}
          <Route
            path="/sph/created-st-requests"
            element={<CreatedSTRequestsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/sph/inprogress-st-requests"
            element={<InProgressSTRequestsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/sph/filmed-st-requests"
            element={<FilmedSTRequestsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/sph/st-request-detail/:requestNumber" // Make sure param name matches useParams()
            element={<PhotographerSTRequestDetailPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/sph/NoPhotoPage" // Make sure param name matches useParams()
            element={<ProcessNoPhotoPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />
          <Route
            path="/sph/DailyStatsPage" // Make sure param name matches useParams()
            element={<DailyStatsPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />

          {/* closed СУПЕРАДМИН */}

          <Route
            path="/AddBlockedBarcodes"
            element={<AddBlockedBarcodes />}
          />
          <Route
            path="/RetouchRequestProductPage"
            element={<RetouchRequestProductPage darkMode={darkMode} setDarkMode={setDarkMode} />}
          />


        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;