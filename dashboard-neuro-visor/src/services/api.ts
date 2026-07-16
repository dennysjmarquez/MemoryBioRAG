import type { Nodo, EgoNetwork, CortezaEstado, CortezaActividad, Dimension, BuscarResponse } from '../types'

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

async function del<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
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
