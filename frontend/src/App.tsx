import { BrowserRouter, Route, Routes } from 'react-router'
import Layout from './components/Layout'
import AuthDone from './pages/AuthDone'
import Login from './pages/Login'
import PRList from './pages/PRList'
import Repos from './pages/Repos'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/auth/done" element={<AuthDone />} />
        <Route element={<Layout />}>
          <Route path="/" element={<Repos />} />
          <Route path="/repos/:owner/:repo" element={<PRList />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
