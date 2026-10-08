import { useEffect } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './components/AuthContext'
import { BagProvider } from './components/BagContext'
import { ChatProvider } from './components/ChatContext'
import ChatWidget from './components/ChatWidget'
import Footer from './components/Footer'
import Header from './components/Header'
import ResultsShelf from './components/ResultsShelf'
import { SizeProvider } from './components/SizeContext'
import About from './pages/About'
import { Login, Signup } from './pages/AuthPages'
import Bag from './pages/Bag'
import Home from './pages/Home'
import ProductDetail from './pages/ProductDetail'
import Products from './pages/Products'

function NotFound() {
  return (
    <div className="page">
      <div className="empty">
        <h1 className="display display--sm">This page wandered off campus</h1>
        <Link to="/" className="btn btn--primary">Go home</Link>
      </div>
    </div>
  )
}

/** New page = start at the top (filters that only change ?query keep the scroll position). */
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <SizeProvider>
          <BagProvider>
            <ChatProvider>
              <ScrollToTop />
              <Header />
              <main className="main">
                <ResultsShelf />
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/products" element={<Products />} />
                  <Route path="/products/:productId" element={<ProductDetail />} />
                  <Route path="/about" element={<About />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/signup" element={<Signup />} />
                  <Route path="/bag" element={<Bag />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </main>
              <Footer />
              <ChatWidget />
            </ChatProvider>
          </BagProvider>
        </SizeProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
