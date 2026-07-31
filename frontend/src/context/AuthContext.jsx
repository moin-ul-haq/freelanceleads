import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api, getTokens, setTokens, setLogoutHandler } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    setTokens(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setLogoutHandler(() => setUser(null))
    if (!getTokens()) { setLoading(false); return }
    api.get('/auth/me/')
      .then(setUser)
      .catch(() => setTokens(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const data = await api.post('/auth/login/', { email, password }, { auth: false })
    setTokens(data.tokens)
    const me = await api.get('/auth/me/')
    setUser(me)
    return me
  }, [])

  const register = useCallback(async (username, email, password, password2) => {
    const data = await api.post('/auth/register/', { username, email, password, password2 }, { auth: false })
    setTokens(data.tokens)
    const me = await api.get('/auth/me/')
    setUser(me)
    return me
  }, [])

  const refreshUser = useCallback(async () => {
    const me = await api.get('/auth/me/')
    setUser(me)
    return me
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
