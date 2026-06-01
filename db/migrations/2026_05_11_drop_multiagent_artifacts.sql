-- Limpieza total de artefactos multiagente.
-- Ejecutar una sola vez en el schema CRM antes de reiniciar el desarrollo desde cero.

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS enterprise_agent_messages;
DROP TABLE IF EXISTS enterprise_agent_sessions;
DROP TABLE IF EXISTS agent_chat_messages;
DROP TABLE IF EXISTS agent_chat_sessions;
DROP TABLE IF EXISTS agent_chat_memory;
DROP TABLE IF EXISTS ai_error_memory;
DROP TABLE IF EXISTS ai_event_log;
DROP TABLE IF EXISTS ai_shared_memory;
DROP TABLE IF EXISTS agent_execution_traces;

SET FOREIGN_KEY_CHECKS = 1;
