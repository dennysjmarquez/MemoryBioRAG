export interface EgoNode {
  id: number
  concepto: string
  contenido: string
  peso: number
  estado: 'activo' | 'dormido'
  sinonimos: string
  ultimo_acceso: number
  creado_en: number
  categoria: string
  num_conexiones: number
  dimensiones: Record<string, string[]>
  grupos: { nombre: string; fuente: string }[]
}

export interface EgoConnection {
  direccion: 'saliente' | 'entrante' | 'bidireccional'
  destino_concepto: string
  peso: number
  tipo: string
  creado_en: number
  ultimo_uso: number
  destino_categoria: string
  destino_peso: number
  destino_estado: 'activo' | 'dormido'
  destino_preview: string
}

export interface EgoLatent {
  destino_concepto: string
  peso: number
  saltos: number
  destino_categoria: string
  destino_preview: string
}

export interface EgoGraphResponse {
  center: EgoNode
  connections: EgoConnection[]
  latentes: EgoLatent[]
  stats: {
    total_conexiones: number
    total_latentes: number
    salientes: number
    entrantes: number
    mostrando_conexiones: number
    mostrando_latentes: number
    offset_conexiones: number
    offset_latentes: number
  }
}

export interface SinapsisCreate {
  origen: string
  destino: string
  peso: number
  tipo: string
}

export interface SinapsisDelete {
  origen: string
  destino: string
}

export interface SinapsisResponse {
  status: string
  mensaje: string
  eliminados?: number
}

export interface ConnectionFilter {
  tipo: string
  orden: 'peso' | 'ultimo_uso' | 'alfabeto'
}

export interface ConnectionCardProps {
  connection: EgoConnection
  currentNode: string
  onNavigate: (concepto: string) => void
  onUnlink: (a: string, b: string) => void
}