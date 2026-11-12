-- APS-9 / APS-10: modelagem e criação do banco (MySQL 8.0.16+)
CREATE DATABASE IF NOT EXISTS cofre_biometrico CHARACTER SET utf8mb4;
USE cofre_biometrico;

CREATE TABLE IF NOT EXISTS divisoes (
  id    INT AUTO_INCREMENT PRIMARY KEY,
  nome  VARCHAR(80) NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  nome       VARCHAR(120) NOT NULL,
  matricula  VARCHAR(20) UNIQUE NOT NULL,
  cargo      VARCHAR(80),
  divisao_id INT NULL,
  nivel      TINYINT NOT NULL,
  pin_hash   VARCHAR(128) NULL,           -- PBKDF2-HMAC-SHA256 com sal (ver core/seguranca.py), só nível 3
  ativo      BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT ck_nivel CHECK (nivel BETWEEN 1 AND 3),
  CONSTRAINT fk_usuario_divisao FOREIGN KEY (divisao_id) REFERENCES divisoes(id)
);

CREATE TABLE IF NOT EXISTS biometrias (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  usuario_id INT NOT NULL,
  vetor      BLOB NOT NULL,               -- 512 float32 = 2048 bytes
  qualidade  FLOAT,                       -- score de detecção no cadastro
  criado_em  DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_bio_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recursos (
  id           INT AUTO_INCREMENT PRIMARY KEY,
  nome         VARCHAR(80) NOT NULL,
  nivel_minimo TINYINT NOT NULL,
  divisao_id   INT NULL,                  -- NULL = qualquer divisão
  CONSTRAINT fk_recurso_divisao FOREIGN KEY (divisao_id) REFERENCES divisoes(id)
);

CREATE TABLE IF NOT EXISTS acessos (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  usuario_id  INT NULL,                   -- NULL quando não reconhecido
  recurso_id  INT NULL,
  resultado   ENUM('concedido','negado_nivel','negado_divisao','negado_horario',
                   'nao_reconhecido','falha_liveness','pin_invalido','pin_bloqueado') NOT NULL,
  score       FLOAT,
  evidencia   VARCHAR(200),               -- caminho do quadro salvo
  alerta      BOOLEAN NOT NULL DEFAULT FALSE,   -- negativa em recurso nível 3
  ocorrido_em DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_acessos_data (ocorrido_em),
  INDEX idx_acessos_usuario (usuario_id, resultado),
  CONSTRAINT fk_acesso_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL,
  CONSTRAINT fk_acesso_recurso FOREIGN KEY (recurso_id) REFERENCES recursos(id) ON DELETE SET NULL
);
