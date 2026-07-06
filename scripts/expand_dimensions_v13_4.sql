-- BioRAG v13.4: Expansión de dimensiones semánticas
-- 7 dimensiones, ~72 sub-values con descripciones completas
-- Fecha: 2026-07-06

-- ============================================================
-- 1. NUEVOS TIPOS DE DIMENSIÓN
-- ============================================================
INSERT OR IGNORE INTO tipos_dimension (id, nombre, description) VALUES
(6, 'intencion', '(El "Por Qué"): Propósito o razón por la que se guardó el nodo. Captura la intención del autor al momento de guardar.'),
(7, 'dominio', '(El "Dónde"): Área de vida o campo de aplicación del conocimiento. Captura dónde se aplica el contenido del nodo.');

-- ============================================================
-- 2. NUEVAS DIMENSIONES PARA TIPOS EXISTENTES
-- ============================================================

-- EMOCIÓN (tipo_id=1): agregar alivio, apatía, culpa, satisfacción
INSERT OR IGNORE INTO dimensiones_semanticas (id, name, description, tipo_id) VALUES
(88, 'alivio', 'Sensación de calma después de resolver algo o soltar tensión. Paz transitoria.', 1),
(89, 'apatia', 'Falta de interés, motivación o energía. Desgano, indiferencia, hastío.', 1),
(90, 'culpa', 'Sensación de haber hecho algo malo o de deber algo. Arrepentimiento.', 1),
(91, 'satisfaccion', 'Placer por completar algo, aprender algo nuevo o ver resultados positivos.', 1);

-- ENTIDAD (tipo_id=2): agregar concepto abstracto, institución, evento, vínculo
INSERT OR IGNORE INTO dimensiones_semanticas (id, name, description, tipo_id) VALUES
(92, 'identidad_concepto', 'Ideas, teorías, principios, modelos mentales. Sin forma física, existe como abstracción.', 2),
(93, 'identidad_institucion', 'Organizaciones, empresas, universidades, gobiernos. Estructuras formales con reglas.', 2),
(94, 'identidad_evento', 'Reuniones, conferencias, lanzamientos,Occurrences puntuales con fecha.', 2),
(95, 'identidad_vinculo', 'Personas con las que tengo vínculo emocional: familia, amigos, pareja, mentor.', 2);

-- ACCIÓN (tipo_id=3): agregar evaluación, observación, falla
INSERT OR IGNORE INTO dimensiones_semanticas (id, name, description, tipo_id) VALUES
(96, 'accion_evaluar', 'Analizar, juzgar, comparar o valorar algo. Proceso de decisión.', 3),
(97, 'accion_observar', 'Presenciar, notar o registrar algo sin actuar directamente. Atención pasiva.', 3),
(98, 'accion_fallar', 'Algo falló, se rompió o dejó de funcionar. Error, malfunction, crash.', 3);

-- CUALIDAD (tipo_id=4): agregar económica, urgencia, autenticidad
INSERT OR IGNORE INTO dimensiones_semanticas (id, name, description, tipo_id) VALUES
(99, 'cualidad_economica', 'Relacionado con dinero, costos, presupuesto, inversión o finanzas.', 4),
(100, 'cualidad_urgente', 'Requiere acción inmediata. Tiene fecha límite o consecuencias si se pospone.', 4),
(101, 'cualidad_autentica', 'Vivencia real, genuina. No teórico ni hipotético. Experiencia personal.', 4);

-- COORDENADA (tipo_id=5): agregar etapa vital, hito de vida
INSERT OR IGNORE INTO dimensiones_semanticas (id, name, description, tipo_id) VALUES
(102, 'coordenada_etapa', 'Corresponde a una etapa de vida: infancia, juventud, adultez, vejez.', 5),
(103, 'coordenada_hito', 'Marca un momento significativo: nacimiento, muerte, cambio de trabajo, mudanza.', 5);

-- ============================================================
-- 3. NUEVAS DIMENSIONES PARA TIPOS NUEVOS
-- ============================================================

-- INTENCIÓN (tipo_id=6): 8 valores
INSERT OR IGNORE INTO dimensiones_semanticas (id, name, description, tipo_id) VALUES
(104, 'intencion_aprender', 'Guardo para aprender o recordar algo que estoy estudiando.', 6),
(105, 'intencion_decidir', 'Guardo para tomar una decisión o tener contexto para decidir.', 6),
(106, 'intencion_reflexionar', 'Guardo para pensar sobre algo, meditar o sacar conclusiones.', 6),
(107, 'intencion_resolver', 'Guardo porque algo falló o hay un obstáculo que superar.', 6),
(108, 'intencion_solucionar', 'Guardo la solución a un problema que ya resolví. Referencia futura.', 6),
(109, 'intencion_documentar', 'Guardo para tener un registro formal o referencia duradera.', 6),
(110, 'intencion_desahogar', 'Guardo para expresar lo que siento, sin buscar solución.', 6),
(111, 'intencion_registrar', 'Guardo para marcar que algo pasó, sin juicio ni propósito específico.', 6);

-- DOMINIO (tipo_id=7): 10 valores
INSERT OR IGNORE INTO dimensiones_semanticas (id, name, description, tipo_id) VALUES
(112, 'dominio_tecnico', 'Programación, infraestructura, herramientas de desarrollo, software.', 7),
(113, 'dominio_personal', 'Vida privada, familia, relaciones personales, hogar.', 7),
(114, 'dominio_profesional', 'Trabajo, carrera, crecimiento profesional, oficina.', 7),
(115, 'dominio_academico', 'Estudios, cursos, investigación, aprendizaje formal, universidad.', 7),
(116, 'dominio_salud', 'Salud física, mental, bienestar, cuidado del cuerpo, medicina.', 7),
(117, 'dominio_finanzas', 'Dinero, inversiones, presupuesto, deudas, planificación financiera.', 7),
(118, 'dominio_ambiental', 'Naturaleza, clima, medio ambiente, ecología, sustentabilidad.', 7),
(119, 'dominio_social', 'Relaciones sociales, comunidad, política, sociedad, cultura.', 7),
(120, 'dominio_creativo', 'Arte, música, escritura, diseño, expresión creativa.', 7),
(121, 'dominio_espiritual', 'Valores, propósito, sentido de vida, creencias, filosofía.', 7);
