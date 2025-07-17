import React, { useEffect } from 'react';
import { Layout, Row, Col, Typography, Divider, Grid } from 'antd';
import Sidebar from '../components/Layout/Sidebar';

const { Content } = Layout;
const { Title } = Typography;
const { useBreakpoint } = Grid;

const Home = ({ darkMode, setDarkMode }) => {
  useEffect(() => {
    document.title = 'Teez Studio';
  }, []);

  // Определяем, md-ширина или меньше
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar darkMode={darkMode} setDarkMode={setDarkMode} />
      <Layout>
        <Content
          style={{
            margin: '24px',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            height: 'calc(100vh - 96px)', // корректируем высоту с учетом margin/padding
          }}
        >
          <Row gutter={16} style={{ flex: 1 }}>
            <Col
              xs={24}
              md={16}
              style={{ display: 'flex', flexDirection: 'column' }}
            >
              <Title level={3}>Новости и объявления</Title>
              <Divider />
              <div style={{ flex: 1, overflow: 'auto' }}>
                <p>в разработке</p>
              </div>
            </Col>
            {!isMobile && (
              <Col
                xs={0}
                md={1}
                style={{ display: 'flex', justifyContent: 'center' }}
              >
                <Divider type="vertical" style={{ height: '100%' }} />
              </Col>
            )}
            <Col
              xs={24}
              md={7}
              style={{ display: 'flex', flexDirection: 'column' }}
            >
              <Title level={3}>Дни рождения</Title>
              <Divider />
              <div style={{ flex: 1, overflow: 'auto' }}>
                <p>в разработке</p>
              </div>
            </Col>
          </Row>
        </Content>
      </Layout>
    </Layout>
  );
};

export default Home;
