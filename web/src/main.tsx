import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components'
import NotFound from './pages/NotFound'
import Player from './pages/Player'
import Scout from './pages/Scout'
import Shortlist from './pages/Shortlist'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Scout />} />
          <Route path="/player/:id" element={<Player />} />
          <Route path="/shortlist" element={<Shortlist />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  </StrictMode>,
)
