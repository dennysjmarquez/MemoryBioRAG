import type { Nodo, EgoNetwork, CortezaEstado, CortezaActividad, Dimension, BuscarResponse, EstadoReparacion, BuscadasFallidasResponse, NodosEnRiesgoResponse } from '../types'
import type { EgoGraphResponse, SinapsisCreate, SinapsisDelete, SinapsisResponse } from '../types/explorar'

const API_BASE = '/api'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  return response.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  return response.json() as Promise<T>
}

async function del<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  return response.json() as Promise<T>
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  return response.json() as Promise<T>
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new ApiError(response.status, response.statusText)
  return response.json() as Promise<T>
}

function encodeParam(value: string): string {
  return encodeURIComponent(value)
}

export function buscar(query: string): Promise<BuscarResponse> {
  return get(`/buscar?q=${encodeParam(query)}`)
}

export function getNodo(concepto: string): Promise<Nodo> {
  return get(`/nodo/${encodeParam(concepto)}`)
}

export function getEgo(concepto: string): Promise<EgoNetwork> {
  return get(`/nodo/${encodeParam(concepto)}/ego`)
}

export function getEgoGraph(concepto: string, limit: number = 50): Promise<EgoGraphResponse> {
  return get(`/nodo/${encodeParam(concepto)}/ego?limit=${limit}`)
}

export function getCortezaEstado(): Promise<CortezaEstado> {
  return get('/corteza/estado')
}

export function getCortezaActividad(dias: number = 7): Promise<CortezaActividad> {
  return get(`/corteza/actividad?dias=${dias}`)
}

export function getDimensiones(): Promise<Dimension[]> {
  return get('/dimensiones')
}

export function desvincular(a: string, b: string): Promise<{ ok: boolean }> {
  return del('/sinapsis', { a, b })
}

export function crearSinapsis(data: SinapsisCreate): Promise<SinapsisResponse> {
  return post('/sinapsis', data)
}

export function eliminarSinapsis(data: SinapsisDelete): Promise<SinapsisResponse> {
  return del('/sinapsis', data)
}

export function actualizarSinapsis(data: { origen: string; destino: string; peso?: number; tipo?: string }): Promise<SinapsisResponse> {
  return patch('/sinapsis', data)
}

export function dormirNodo(concepto: string): Promise<SinapsisResponse> {
  return post(`/nodo/${encodeParam(concepto)}/dormir`, {})
}

export function despertarNodo(concepto: string): Promise<SinapsisResponse> {
  return post(`/nodo/${encodeParam(concepto)}/despertar`, {})
}

export function eliminarNodo(concepto: string): Promise<SinapsisResponse> {
  return del(`/nodo/${encodeParam(concepto)}`, {})
}

export function consolidarCerebro(): Promise<{ status: string; mensaje: string; resultado: string }> {
  return post('/consolidar', {})
}

export function actualizarNodo(concepto: string, contenido: string): Promise<{ status: string }> {
  return put(`/nodo/${encodeParam(concepto)}`, { contenido })
}

export function fusionarNodos(origen: string, destinos: string[]): Promise<{ status: string; mensaje: string; fusionados: number; errores: string[] }> {
  return post('/nodo/fusionar', { origen, destinos })
}

export interface BuscarNodoResult {
  concepto: string
  contenido: string
  score: number
  estado: string
  categoria?: string
}

export function buscarNodos(query: string, limit: number = 15): Promise<{ resultados: BuscarNodoResult[]; total: number }> {
  return get(`/buscar?q=${encodeParam(query)}&limit=${limit}`)
}

export function getBuscadasFallidas(limit: number = 20): Promise<BuscadasFallidasResponse> {
  return get(`/corteza/buscadas-fallidas?limit=${limit}`)
}

export function getNodosEnRiesgo(limit: number = 20): Promise<NodosEnRiesgoResponse> {
  return get(`/corteza/nodos-en-riesgo?limit=${limit}`)
}

export function getEstadoReparacion(): Promise<EstadoReparacion> {
  return get('/corteza/estado-reparacion')
}

export function limpiarLogBusquedas(ttlDays: number = 7): Promise<{ status: string; ttl_days: number; eliminados: number }> {
  return post(`/corteza/limpiar-log?ttl_days=${ttlDays}`, {})
}