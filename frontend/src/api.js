import axios from 'axios'

const API = axios.create({ baseURL: '' }) // proxied via vite

export const getHealth         = ()       => API.get('/health')
export const listIncidents     = ()       => API.get('/api/incidents')
export const createIncident    = (data)   => API.post('/api/incidents', data)
export const getIncident       = (pk)     => API.get(`/api/incidents/${pk}`)
export const runWorkflow       = (pk, mode) => API.post(`/api/incidents/${pk}/run`, { scenario_mode: mode })
export const resetIncident     = (pk)     => API.delete(`/api/incidents/${pk}/reset`)
export const getActivity       = (pk)     => API.get(`/api/incidents/${pk}/activity`)
export const getPatches        = (pk)     => API.get(`/api/incidents/${pk}/patches`)
export const getTransitions    = (pk)     => API.get(`/api/incidents/${pk}/transitions`)
export const getEvidence       = (pk)     => API.get(`/api/incidents/${pk}/evidence`)
export const verifyEvidence    = (pk)     => API.post(`/api/incidents/${pk}/evidence/verify`)
export const getScenarios      = ()       => API.get('/api/scenarios')
export const getTaxonomy       = ()       => API.get('/api/taxonomy')
export const getDataIncidents  = ()       => API.get('/api/data/incidents')
export const createCustomIncident = (data) => API.post('/api/incidents/custom', data)