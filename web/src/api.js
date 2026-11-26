import axios from 'axios'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

export const getCompare = (params) =>
  http.get('/compare', { params }).then((response) => response.data)

export const getHistory = (params) =>
  http.get('/price/history', { params }).then((response) => response.data)

export const getAlerts = () =>
  http.get('/alerts').then((response) => response.data)

export const ackAlert = (id) =>
  http.patch(`/alerts/${id}/ack`).then((response) => response.data)

export const getRules = () =>
  http.get('/rules').then((response) => response.data)

export const createRule = (payload) =>
  http.post('/rules', payload).then((response) => response.data)

export const updateRule = (id, payload) =>
  http.put(`/rules/${id}`, payload).then((response) => response.data)

export const toggleRule = (id) =>
  http.patch(`/rules/${id}/toggle`).then((response) => response.data)
