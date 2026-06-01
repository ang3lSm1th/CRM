import os
import MySQLdb.cursors
from extensions import mysql


class AgentMemory:
    _schema_ready = False
    _max_messages_per_session = int(os.getenv("AGENT_MAX_MESSAGES_PER_SESSION", "200"))
    _max_messages_per_user = int(os.getenv("AGENT_MAX_MESSAGES_PER_USER", "2000"))

    @staticmethod
    def _column_exists(table_name, column_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                """,
                (table_name, column_name),
            )
            row = cur.fetchone() or {}
            return int(row.get("total", 0)) > 0
        finally:
            cur.close()

    @staticmethod
    def ensure_schema():
        """Crea tablas base multiagente si no existen."""
        if AgentMemory._schema_ready:
            return True

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                    usuario_id INT NOT NULL,
                    session_id VARCHAR(64) NOT NULL,
                    role ENUM('user','assistant') NOT NULL,
                    content TEXT NOT NULL,
                    intent VARCHAR(64) NULL,
                    agent_used VARCHAR(64) NULL,
                    tokens_used SMALLINT UNSIGNED NULL,
                    feedback TINYINT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    INDEX idx_am_usuario (usuario_id),
                    INDEX idx_am_session (session_id),
                    INDEX idx_am_created (created_at),
                    INDEX idx_am_intent (intent)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_stats (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                    fecha DATE NOT NULL,
                    agent_type VARCHAR(64) NOT NULL,
                    total_calls INT UNSIGNED NOT NULL DEFAULT 0,
                    total_errors INT UNSIGNED NOT NULL DEFAULT 0,
                    avg_feedback DECIMAL(3,2) NULL,
                    tokens_total INT UNSIGNED NOT NULL DEFAULT 0,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_as_fecha_agent (fecha, agent_type),
                    INDEX idx_as_fecha (fecha)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_corrections (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                    usuario_id INT NOT NULL,
                    session_id VARCHAR(64) NOT NULL,
                    pregunta_orig TEXT NOT NULL,
                    respuesta_mala TEXT NULL,
                    respuesta_buena TEXT NOT NULL,
                    intent VARCHAR(64) NULL,
                    agent_used VARCHAR(64) NULL,
                    reportado_por INT NULL,
                    aplicado TINYINT(1) NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    INDEX idx_ac_usuario (usuario_id),
                    INDEX idx_ac_session (session_id),
                    INDEX idx_ac_intent (intent)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_skills (
                    id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    skill_name VARCHAR(80) NOT NULL UNIQUE,
                    display_name VARCHAR(120) NOT NULL,
                    description TEXT NULL,
                    agent_type VARCHAR(64) NOT NULL,
                    keywords TEXT NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    INDEX idx_as_agent_type (agent_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)

            if not AgentMemory._column_exists("agent_corrections", "usuario_id"):
                cur.execute(
                    "ALTER TABLE agent_corrections ADD COLUMN usuario_id INT NOT NULL DEFAULT 0 AFTER id"
                )
            if not AgentMemory._column_exists("agent_corrections", "session_id"):
                cur.execute(
                    "ALTER TABLE agent_corrections ADD COLUMN session_id VARCHAR(64) NOT NULL DEFAULT '' AFTER usuario_id"
                )
            if not AgentMemory._column_exists("agent_corrections", "agent_used"):
                cur.execute(
                    "ALTER TABLE agent_corrections ADD COLUMN agent_used VARCHAR(64) NULL AFTER intent"
                )
            if not AgentMemory._column_exists("agent_corrections", "aplicado"):
                cur.execute(
                    "ALTER TABLE agent_corrections ADD COLUMN aplicado TINYINT(1) NOT NULL DEFAULT 0 AFTER reportado_por"
                )

            mysql.connection.commit()
            AgentMemory._schema_ready = True
            return True
        finally:
            cur.close()

    @staticmethod
    def save_interaction(
        usuario_id,
        session_id,
        role,
        content,
        intent=None,
        agent_used=None,
        tokens_used=None,
    ):
        """Guarda un mensaje de usuario o asistente en agent_memory."""
        AgentMemory.ensure_schema()
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            sql = """
                INSERT INTO agent_memory
                (usuario_id, session_id, role, content, intent, agent_used, tokens_used)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(
                sql,
                (
                    usuario_id,
                    session_id,
                    role,
                    content,
                    intent,
                    agent_used,
                    tokens_used,
                ),
            )
            mysql.connection.commit()
            AgentMemory._prune_session_history(
                usuario_id=usuario_id, session_id=session_id
            )
            AgentMemory._prune_user_history(usuario_id=usuario_id)
            return cur.lastrowid
        finally:
            cur.close()

    @staticmethod
    def _prune_session_history(usuario_id, session_id):
        max_rows = max(10, int(AgentMemory._max_messages_per_session or 200))
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            sql = """
                DELETE FROM agent_memory
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id
                        FROM agent_memory
                        WHERE usuario_id = %s
                          AND session_id = %s
                        ORDER BY id DESC
                        LIMIT %s, 1000000
                    ) AS old_rows
                )
            """
            cur.execute(sql, (usuario_id, session_id, max_rows))
            mysql.connection.commit()
            return True
        finally:
            cur.close()

    @staticmethod
    def _prune_user_history(usuario_id):
        max_rows = max(50, int(AgentMemory._max_messages_per_user or 2000))
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            sql = """
                DELETE FROM agent_memory
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id
                        FROM agent_memory
                        WHERE usuario_id = %s
                        ORDER BY id DESC
                        LIMIT %s, 1000000
                    ) AS old_rows
                )
            """
            cur.execute(sql, (usuario_id, max_rows))
            mysql.connection.commit()
            return True
        finally:
            cur.close()

    @staticmethod
    def delete_history(usuario_id, session_id=None):
        """Elimina historial del usuario: por sesion o completo."""
        AgentMemory.ensure_schema()
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            if session_id:
                cur.execute(
                    "DELETE FROM agent_memory WHERE usuario_id = %s AND session_id = %s",
                    (usuario_id, session_id),
                )
            else:
                cur.execute(
                    "DELETE FROM agent_memory WHERE usuario_id = %s", (usuario_id,)
                )
            deleted = int(cur.rowcount or 0)
            mysql.connection.commit()
            return deleted
        finally:
            cur.close()

    @staticmethod
    def get_similar_questions(usuario_id, question_text, limit=5):
        """
        Busca preguntas similares del usuario usando LIKE simple.
        Esto es una primera versión sin embeddings.
        """
        AgentMemory.ensure_schema()
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            like_q = f"%{question_text.strip()}%"
            sql = """
                SELECT id, session_id, content, intent, agent_used, feedback, created_at
                FROM agent_memory
                WHERE usuario_id = %s
                  AND role = 'user'
                  AND content LIKE %s
                ORDER BY created_at DESC
                LIMIT %s
            """
            cur.execute(sql, (usuario_id, like_q, int(limit)))
            return cur.fetchall()
        finally:
            cur.close()

    @staticmethod
    def update_feedback(memory_id, stars):
        """Actualiza feedback (1-5) sobre una interacción en agent_memory."""
        AgentMemory.ensure_schema()
        stars = int(stars)
        if stars < 1:
            stars = 1
        if stars > 5:
            stars = 5

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            sql = """
                UPDATE agent_memory
                SET feedback = %s
                WHERE id = %s
            """
            cur.execute(sql, (stars, memory_id))
            mysql.connection.commit()
            return cur.rowcount > 0
        finally:
            cur.close()

    @staticmethod
    def get_last_assistant_message(usuario_id, session_id):
        AgentMemory.ensure_schema()
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT id, content, intent, agent_used, created_at
                FROM agent_memory
                WHERE usuario_id = %s
                  AND session_id = %s
                  AND role = 'assistant'
                ORDER BY id DESC
                LIMIT 1
                """,
                (usuario_id, session_id),
            )
            return cur.fetchone()
        finally:
            cur.close()

    @staticmethod
    def save_correction(
        usuario_id,
        session_id,
        pregunta_orig,
        respuesta_buena,
        respuesta_mala=None,
        intent=None,
        agent_used=None,
        reportado_por=None,
    ):
        AgentMemory.ensure_schema()
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                INSERT INTO agent_corrections
                (usuario_id, session_id, pregunta_orig, respuesta_mala, respuesta_buena, intent, agent_used, reportado_por, aplicado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
                """,
                (
                    usuario_id,
                    session_id,
                    pregunta_orig,
                    respuesta_mala,
                    respuesta_buena,
                    intent,
                    agent_used,
                    reportado_por,
                ),
            )
            mysql.connection.commit()
            return cur.lastrowid
        finally:
            cur.close()


class AgentStats:
    @staticmethod
    def update_stats(agent_type, error=False, feedback=None, tokens=0):
        """
        Actualiza estadísticas diarias por tipo de agente en agent_stats.
        Usa upsert por (fecha, agent_type).
        """
        AgentMemory.ensure_schema()
        safe_tokens = int(tokens or 0)
        is_error = 1 if error else 0

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            upsert_sql = """
                INSERT INTO agent_stats
                (fecha, agent_type, total_calls, total_errors, avg_feedback, tokens_total)
                VALUES (CURDATE(), %s, 1, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    total_calls = total_calls + 1,
                    total_errors = total_errors + VALUES(total_errors),
                    tokens_total = tokens_total + VALUES(tokens_total),
                    avg_feedback = CASE
                        WHEN VALUES(avg_feedback) IS NULL THEN avg_feedback
                        WHEN avg_feedback IS NULL THEN VALUES(avg_feedback)
                        ELSE ROUND(((avg_feedback * (total_calls - 1)) + VALUES(avg_feedback)) / total_calls, 2)
                    END
            """
            cur.execute(upsert_sql, (agent_type, is_error, feedback, safe_tokens))
            mysql.connection.commit()
            return True
        finally:
            cur.close()
