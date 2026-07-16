export interface Nodo {
  concepto: string
  contenido: string
  peso_sinaptico: number
  estado: 'activo' | 'dormido'
  score_hibrido: number
  asociaciones: string[]
  dimensiones_semanticas: Record<string, string[]>
}

export interface Conexion {
  concepto: string
  peso: number
  tipo: string
  created_at?: number
}

export interface EgoNetwork {
  center: Nodo
  connections: Conexion[]
  latentes: Nodo[]
  stats: {
    directas: number
    latentes: number
    score_promedio: number
  }
}

export interface CortezaEstado {
  activos: number
  dormidos: number
  directas: number
  latentes: number
  energia: number
  energia_max: number
  energia_pct: number
  ultimo_sueno: string
  latencia_ms: number
  categorias: CategoriaCount[]
  dimensiones_top: DimensionTop[]
  total_dim_mappings: number
  version: string
}

export interface CategoriaCount {
  nombre: string
  count: number
}

export interface DimensionTop {
  eje: string
  valor: string
  count: number
}

export interface CortezaActividad {
  ciclos: CicloActividad[]
  energia_historial: EnergiaHistorial[]
}

export interface CicloActividad {
  timestamp: number
  fecha: string
  consolidados: number
  dormidos: number
  sinapsis_creadas: number
  sinapsis_podadas: number
  categoria_dominante: string
  ratio: number
}

export interface EnergiaHistorial {
  timestamp: number
  energia: number
  total_nodos: number
  dormidos: number
  activos: number
  latencia_ms: number
  conceptos: Array<{ concepto: string; contenido: string }>
}

export interface ActividadResponse {
  heatmap: HeatmapDay[]
  energia_historial: EnergiaPunto[]
}

export interface HeatmapDay {
  date: string
  count: number
}

export interface EnergiaPunto {
  timestamp: number
  energia: number
  total_nodos: number
  dormidos: number
  activos: number
  latencia_ms: number
  conceptos: Array<{ concepto: string; contenido: string }>
}

export interface Dimension {
  eje: string
  valor: string
  count: number
}

export interface BuscarResponse {
  total: number
  resultados: Nodo[]
}
