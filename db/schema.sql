CREATE DATABASE IF NOT EXISTS crm_orbes CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE crm_orbes;

-- ROLES
CREATE TABLE IF NOT EXISTS roles (
  id TINYINT PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(50) UNIQUE NOT NULL
);

-- USUARIOS
CREATE TABLE IF NOT EXISTS usuarios (
  id INT PRIMARY KEY AUTO_INCREMENT,
  usuario VARCHAR(50) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  rol_id TINYINT NOT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (rol_id) REFERENCES roles(id)
);

-- CANALES
CREATE TABLE IF NOT EXISTS canales_recepcion (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(80) UNIQUE NOT NULL
);

-- BIENES / SERVICIOS
CREATE TABLE IF NOT EXISTS bienes_servicios (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(120) UNIQUE NOT NULL
);

-- LEADS
CREATE TABLE IF NOT EXISTS leads (
  id INT PRIMARY KEY AUTO_INCREMENT,
  codigo VARCHAR(30) UNIQUE NOT NULL,
  fecha DATE NOT NULL,
  nombre VARCHAR(120) NOT NULL,
  telefono VARCHAR(30),
  ruc_dni VARCHAR(20),
  email VARCHAR(120),
  direccion VARCHAR(200),
  departamento VARCHAR(80),
  provincia VARCHAR(80),
  distrito VARCHAR(80),
  canal_id INT,
  bien_servicio_id INT,
  asignado_a INT,
  comentario TEXT,
  FOREIGN KEY (canal_id) REFERENCES canales_recepcion(id),
  FOREIGN KEY (bien_servicio_id) REFERENCES bienes_servicios(id),
  FOREIGN KEY (asignado_a) REFERENCES usuarios(id)
);

-- SEGUIMIENTOS
CREATE TABLE IF NOT EXISTS seguimientos (
  id INT PRIMARY KEY AUTO_INCREMENT,
  lead_id INT NOT NULL,
  usuario_id INT NOT NULL,
  fecha_seguimiento DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  proceso VARCHAR(60) NOT NULL,
  motivo_no_venta VARCHAR(200),
  cotizacion TINYINT(1) DEFAULT 0,
  monto DECIMAL(12,2),
  moneda VARCHAR(10),
  comentario TEXT,
  canal_emision VARCHAR(40),
  FOREIGN KEY (lead_id) REFERENCES leads(id),
  FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

-- Semillas
INSERT IGNORE INTO roles (id, nombre) VALUES
 (1,'Administrador'),(2,'Gerente'),(3,'RRHH'),(4,'Asesor');

INSERT IGNORE INTO canales_recepcion (id, nombre) VALUES
 (1,'Web'),(2,'Teléfono'),(3,'WhatsApp');

INSERT IGNORE INTO bienes_servicios (id, nombre) VALUES
 (1,'Consultoría'),(2,'Software CRM');
