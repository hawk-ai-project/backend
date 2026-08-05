// src/Navbar.jsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

function Navbar({ position, setPosition }) {
  const [menuList, setMenuList] = useState([]);
  const isTop = position === 'top';

  // DB에서 메뉴 목록을 받아오는 useEffect
  useEffect(() => {
    axios.get(`${API_BASE_URL}/api/menu/list`)
      .then((res) => {
        setMenuList(res.data);
      })
      .catch((err) => {
        console.error('메뉴 목록 로드 실패:', err);
        // API 실패 시 기본 메뉴로 폴백(Fallback)
        setMenuList([
          { id: 1, name: '메인 홈', path: '/', icon: '🏠' },
          { id: 2, name: '질문 목록', path: '/question/list', icon: '📋' }
        ]);
      });
  }, []);

  // 스타일 설정
  const navStyle = isTop
    ? {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '15px 30px',
        backgroundColor: '#1f2937',
        color: '#fff',
        borderBottom: '1px solid #374151',
      }
    : {
        width: '220px',
        height: '100vh',
        backgroundColor: '#1f2937',
        color: '#fff',
        padding: '20px 15px',
        display: 'flex',
        flexDirection: 'column',
        boxSizing: 'border-box',
        position: 'fixed',
        left: 0,
        top: 0,
      };

  const linkContainerStyle = isTop
    ? { display: 'flex', gap: '20px', alignItems: 'center' }
    : { display: 'flex', flexDirection: 'column', gap: '15px', marginTop: '30px' };

  const linkStyle = {
    color: '#e5e7eb',
    textDecoration: 'none',
    fontWeight: '500',
    fontSize: '15px',
  };

  return (
    <nav style={navStyle}>
      <div style={{ fontWeight: 'bold', fontSize: '18px', marginBottom: isTop ? '0' : '20px' }}>
        🚀 Dashboard
      </div>

      {/* DB에서 조회해온 메뉴 데이터를 dynamic rendering */}
      <div style={linkContainerStyle}>
        {menuList.map((menu) => (
          <Link key={menu.id} to={menu.path} style={linkStyle}>
            {menu.icon} {menu.name}
          </Link>
        ))}
      </div>

      <button
        onClick={() => setPosition(isTop ? 'left' : 'top')}
        style={{
          marginTop: isTop ? '0' : 'auto',
          marginLeft: isTop ? 'auto' : '0',
          padding: '8px 12px',
          backgroundColor: '#3b82f6',
          color: '#fff',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontSize: '13px',
        }}
      >
        {isTop ? '⬅️ 좌측바' : '⬆️ 상단바'}
      </button>
    </nav>
  );
}

export default Navbar;