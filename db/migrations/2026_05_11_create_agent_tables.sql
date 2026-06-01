-- ============================================================
-- Multiagente IA – tablas de soporte
-- Base de datos: u349183440_crm_orbes
-- Fecha: 2026-05-11
-- Ejecutar en orden; las FK hacia `usuarios` son opcionales
-- (se definen como índices sin FK estricta para evitar
--  problemas si la tabla de usuarios usa motor diferente).
-- ============================================================

-- 1. Memoria de conversaciones --------------------------------
CREATE TABLE IF NOT EXISTS agent_memory (
    id            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    usuario_id    INT             NOT NULL,          -- FK lógica a usuarios.id
    session_id    VARCHAR(64)     NOT NULL,          -- UUID de sesión de chat
    role          ENUM('user','assistant') NOT NULL,
    content       TEXT            NOT NULL,
    intent        VARCHAR(64)     NULL,              -- database | marketing | llm
    agent_used    VARCHAR(64)     NULL,              -- db_agent | marketing_agent | llm_agent
    tokens_used   SMALLINT UNSIGNED NULL,
    feedback      TINYINT         NULL,              -- 1-5 estrellas (NULL = sin calificar)
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_am_usuario    (usuario_id),
    INDEX idx_am_session    (session_id),
    INDEX idx_am_created    (created_at),
    INDEX idx_am_intent     (intent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 2. Catálogo de habilidades ----------------------------------
CREATE TABLE IF NOT EXISTS agent_skills (
    id            SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    skill_name    VARCHAR(80)     NOT NULL UNIQUE,   -- slug interno
    display_name  VARCHAR(120)    NOT NULL,
    description   TEXT            NULL,
    agent_type    VARCHAR(64)     NOT NULL,          -- db_agent | marketing_agent | llm_agent
    keywords      TEXT            NULL,              -- palabras clave separadas por coma
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_as_agent_type (agent_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 3. Correcciones aprendidas ----------------------------------
CREATE TABLE IF NOT EXISTS agent_corrections (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    pregunta_orig   TEXT            NOT NULL,        -- pregunta original del usuario
    respuesta_mala  TEXT            NULL,            -- respuesta incorrecta del agente
    respuesta_buena TEXT            NOT NULL,        -- corrección proporcionada
    intent          VARCHAR(64)     NULL,
    reportado_por   INT             NULL,            -- usuario_id
    aplicado        TINYINT(1)      NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_ac_intent (intent)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- 4. Estadísticas de uso por agente ---------------------------
CREATE TABLE IF NOT EXISTS agent_stats (
    id            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    fecha         DATE            NOT NULL,
    agent_type    VARCHAR(64)     NOT NULL,
    total_calls   INT UNSIGNED    NOT NULL DEFAULT 0,
    total_errors  INT UNSIGNED    NOT NULL DEFAULT 0,
    avg_feedback  DECIMAL(3,2)    NULL,              -- promedio estrellas del día
    tokens_total  INT UNSIGNED    NOT NULL DEFAULT 0,
    updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_as_fecha_agent (fecha, agent_type),
    INDEX idx_as_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- Datos iniciales: habilidades de ejemplo
-- ============================================================
INSERT IGNORE INTO agent_skills (skill_name, display_name, description, agent_type, keywords) VALUES
('consultar_leads',
 'Consultar leads',
 'Responde preguntas sobre leads: total, por estado, por canal, recientes.',
 'db_agent',
 'leads,cuantos leads,nuevos leads,leads del mes,lead por estado,lead por canal,pipeline'),

('reporte_ventas',
 'Reporte de ventas',
 'Calcula ventas cerradas, montos, comparativas por periodo.',
 'db_agent',
 'ventas,cuanto vendemos,ingreso,monto vendido,cierre,cerradas,revenue'),

('estado_campanas',
 'Estado de campañas',
 'Informa sobre campañas de marketing: activas, leads generados, inversión.',
 'marketing_agent',
 'campañas,campaña,campaign,marketing,leads campana,inversion,cpc,impresiones,alcance'),

('inventario_mercaderia',
 'Inventario de mercadería',
 'Consulta stock de productos/tractores en inventario de marketing.',
 'marketing_agent',
 'inventario,stock,mercaderia,tractores disponibles,unidades'),

('consejo_general',
 'Consejo / pregunta general',
 'Responde preguntas generales de negocio, ventas y estrategia usando LLM.',
 'llm_agent',
 'consejo,cómo mejorar,estrategia,qué hago,recomienda,ayuda');
