"""Configuração central: limiar, câmera, credenciais do banco."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv é opcional
    pass

BASE_DIR = Path(__file__).resolve().parent
DIR_CADASTRO = BASE_DIR / "dados" / "cadastro"
DIR_EVIDENCIAS = BASE_DIR / "dados" / "evidencias"
DIR_FIGURAS = BASE_DIR / "docs" / "figuras"

DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "cofre_biometrico"),
}

# --- reconhecimento (fase 5) ---
LIMIAR = float(os.getenv("LIMIAR", "0.40"))   # similaridade do cosseno mínima
MARGEM_IDENTIFICACAO = 0.05   # o 1º colocado precisa vencer a 2ª PESSOA por pelo menos isso (evita confusão entre parecidos)
CADASTRO_FOTOS_MIN, CADASTRO_FOTOS_MAX = 3, 5
MODELO = "buffalo_l"                          # SCRFD + ArcFace
DET_SIZE = (640, 640)
CTX_ID = int(os.getenv("CTX_ID", "-1"))       # -1 CPU, 0 GPU

# --- qualidade da imagem ---
LUMINOSIDADE_MIN = 40        # média do canal L abaixo disso = escura demais
LARGURA_ROSTO_MIN = 80       # px; menor que isso = rosto muito longe
DET_SCORE_MIN = 0.50

# --- prova de vida (piscada: EAR com MediaPipe FaceMesh) ---
# A piscada é a queda do EAR em relação ao EAR "aberto" da própria pessoa (mediana da rajada),
# e não um valor fixo: o EAR de olhos abertos varia de rosto para rosto (0,22 a 0,35).
EAR_ABERTO_MIN = 0.10        # mediana abaixo disso = olhos fechados o tempo todo (olhos puxados/sorrindo ficam ~0,15)
PISCADA_QUEDA = 0.70         # olho "fechado" = EAR <= 70% do EAR aberto
PISCADA_REABERTURA = 0.85    # olho "aberto" = EAR >= 85% do EAR aberto
PISCADA_MIN_QUADROS = 5      # quadros com rosto necessários para julgar
PISCADAS_EXIGIDAS = 1        # piscadas completas (aberto -> fechado -> aberto) na rajada

# --- segurança ---
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin")
PIN_PEPPER = os.getenv("PIN_PEPPER", "pepper-dev")
USANDO_SEGREDOS_PADRAO = (ADMIN_TOKEN in {"admin", "troque-este-token"}
                          or PIN_PEPPER in {"pepper-dev", "troque-este-pepper"})
HORARIO_EXPEDIENTE = (8, 18)     # nível 2 só dentro desse intervalo, e só nos acervos (recurso nível 2+)
NEGATIVAS_PARA_BLOQUEIO = 3      # quantas negativas seguidas travam o terminal...
JANELA_NEGATIVAS_SEGUNDOS = 60   # ...se ocorrerem dentro desta janela
BLOQUEIO_SEGUNDOS = 60           # tempo de bloqueio, contado a partir da última negativa
QUADROS_CONFERIDOS_NIVEL3 = 3    # quadros da rajada cujo rosto deve ser da mesma pessoa
JANELA_ALERTA_MIN = 5            # alertas do nível 3 exibidos no admin
PIN_TENTATIVAS_MAX = 3           # PINs errados da MESMA pessoa (desde o último acesso concedido)...
PIN_JANELA_MIN = 15              # ...nesta janela bloqueiam o PIN dela por este tempo
PIN_ITERACOES = 200_000          # PBKDF2-HMAC-SHA256 (custo do hash do PIN)
ADMIN_FALHAS_MAX = 5             # tokens de admin errados por IP...
ADMIN_FALHAS_JANELA_SEG = 300    # ...nesta janela -> HTTP 429 até a janela passar
MAX_IMAGENS_POR_ENVIO = 20       # proteção contra envio abusivo
MAX_BYTES_POR_IMAGEM = 5 * 1024 * 1024
