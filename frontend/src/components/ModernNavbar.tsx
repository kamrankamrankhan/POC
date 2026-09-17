import React from 'react';
import { Navbar, Nav, Container } from 'react-bootstrap';
import ThemeSwitcher from './ThemeSwitcher';

interface ModernNavbarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const ModernNavbar: React.FC<ModernNavbarProps> = ({ activeTab, onTabChange }) => {
  const navItems = [
    { id: 'upload', label: 'Upload', icon: 'fas fa-upload' },
    { id: 'status', label: 'Processing Status', icon: 'fas fa-cog' },
    { id: 'results', label: 'Analysis Results', icon: 'fas fa-chart-bar' },
    { id: 'history', label: 'Job History', icon: 'fas fa-history' }
  ];

  return (
    <Navbar expand="lg" className="modern-navbar">
      <Container fluid>
        <Navbar.Brand className="brand">
          <i className="fas fa-file-pdf me-2"></i>
          <span className="brand-text">PDF Quality Checker</span>
        </Navbar.Brand>
        
        <Navbar.Toggle aria-controls="basic-navbar-nav" />
        <Navbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto modern-nav">
            {navItems.map((item) => (
              <Nav.Link
                key={item.id}
                className={`modern-nav-link ${activeTab === item.id ? 'active' : ''}`}
                onClick={(e) => {
                  e.preventDefault();
                  onTabChange(item.id);
                }}
                href={`#${item.id}`}
              >
                <i className={`${item.icon} me-2`}></i>
                <span className="nav-label">{item.label}</span>
              </Nav.Link>
            ))}
          </Nav>
          
          <div className="navbar-actions">
            <ThemeSwitcher />
          </div>
        </Navbar.Collapse>
      </Container>
    </Navbar>
  );
};

export default ModernNavbar;

