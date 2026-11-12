"""API do cofre biométrico (APS-12).  Subir com:  uvicorn api.app:app --reload

Públicas (terminal):  GET /api/recursos, POST /api/reconhecer, GET /api/saude
Admin (X-Admin-Token): usuários, cadastro, qualidade de foto, logs, resumo, exportação, alertas, evidências
"""
import hmac
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import config
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core import fluxo, galeria, matcher, relatorios, seguranca
from db import repositorio
from db.conexao import banco_disponivel
from visao import detector, embedding, liveness
from visao.captura import ErroVisao, decodificar

import mysql.connector

log = logging.getLogger("cofre.api")


# ---------- inicialização ----------
def _pre_carregar_modelos():
    """Carrega os modelos em segundo plano: o primeiro acesso não espera (nem estoura por) o download."""
    try:
        detector.modelo()
    except Exception:
        log.exception("Não foi possível carregar o modelo de reconhecimento facial")
    try:
        liveness.preparar()
    except Exception:
        log.exception("Não foi possível preparar a prova de vida (o cofre principal ficará negado)")


@asynccontextmanager
async def ciclo_de_vida(_):
    threading.Thread(target=_pre_carregar_modelos, daemon=True).start()
    if config.USANDO_SEGREDOS_PADRAO:
        log.warning("ADMIN_TOKEN/PIN_PEPPER não definidos no .env: usando valores PADRÃO "
                    "(inseguro). Copie .env.example para .env e troque os dois.")
    if banco_disponivel():
        galeria.recarregar()
    yield


app = FastAPI(title="Cofre Biométrico", lifespan=ciclo_de_vida)

_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' blob: data:; media-src 'self' blob: mediastream:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, chamar):
    resposta = await chamar(request)
    h = resposta.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    h.setdefault("Content-Security-Policy", _CSP)
    if request.url.path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")   # dados pessoais e fotos não ficam em cache
    return resposta


# ---------- erros ----------
@app.exception_handler(ErroVisao)
async def erro_visao(_, exc: ErroVisao):
    return JSONResponse(status_code=422, content={"erro": exc.codigo, "mensagem": exc.mensagem, **exc.extra})


@app.exception_handler(mysql.connector.Error)
async def erro_banco(_, exc):
    return JSONResponse(status_code=503, content={
        "erro": "banco_indisponivel",
        "mensagem": "Banco de dados indisponível. Verifique se o MySQL está no ar e avise o administrador.",
    })


# ---------- autenticação do administrador ----------
_falhas_admin: dict = defaultdict(deque)   # IP -> instantes das tentativas com token errado
_trava_falhas = threading.Lock()


def _token_ok(token: str) -> bool:
    return hmac.compare_digest(token.encode(), config.ADMIN_TOKEN.encode())


def admin(request: Request, x_admin_token: str = Header(default="")):
    """Exige o token no cabeçalho X-Admin-Token. Muitos erros seguidos do mesmo IP -> 429."""
    ip = request.client.host if request.client else "?"
    agora = time.monotonic()
    with _trava_falhas:
        falhas = _falhas_admin[ip]
        while falhas and agora - falhas[0] > config.ADMIN_FALHAS_JANELA_SEG:
            falhas.popleft()
        if len(falhas) >= config.ADMIN_FALHAS_MAX:
            raise HTTPException(429, "Muitas tentativas com token inválido. Aguarde alguns minutos.")
        if _token_ok(x_admin_token):
            falhas.clear()
            return
        falhas.append(agora)
    raise HTTPException(401, "Token de administrador inválido.")


@app.get("/api/admin/verificar", dependencies=[Depends(admin)])
def verificar_admin():
    """Usado pela tela de login das páginas de administração."""
    return {"ok": True}


# ---------- utilidades de upload ----------
async def _ler(arquivos: list[UploadFile], minimo: int = 1, maximo: int = None) -> list[bytes]:
    """Lê os arquivos enviados respeitando quantidade e tamanho máximos."""
    maximo = maximo or config.MAX_IMAGENS_POR_ENVIO
    if not minimo <= len(arquivos) <= maximo:
        raise HTTPException(422, f"Envie de {minimo} a {maximo} imagens.")
    conteudos = []
    for i, f in enumerate(arquivos, start=1):
        dados = await f.read(config.MAX_BYTES_POR_IMAGEM + 1)
        if len(dados) > config.MAX_BYTES_POR_IMAGEM:
            raise HTTPException(413, f"Imagem {i} maior que {config.MAX_BYTES_POR_IMAGEM // (1024 * 1024)} MB.")
        conteudos.append(dados)
    return conteudos


def _extrair_vetores(conteudos: list):
    """Decodifica e extrai o vetor de cada foto; diz qual foto falhou (roda em thread)."""
    vetores = []
    for i, dados in enumerate(conteudos, start=1):
        try:
            vetores.append(embedding.extrair(decodificar(dados)))
        except ErroVisao as e:
            raise ErroVisao(e.codigo, f"Foto {i}: {e.mensagem}") from e
    return vetores


def _nome(uid):
    u = repositorio.obter_usuario(uid)
    return f"{u['nome']} (matrícula {u['matricula']})" if u else f"usuário {uid}"


def _validar_biometria(vetores, uid: int = None):
    """Regras do cadastro: as fotos são da mesma pessoa e essa pessoa não está cadastrada com outro nome."""
    par = matcher.menor_similaridade_entre([v.vetor for v in vetores])
    if par and par[2] < config.LIMIAR:
        i, j, s = par
        raise HTTPException(422, f"As fotos {i} e {j} não parecem ser da mesma pessoa (similaridade {s:.2f}). "
                                 "Refaça as capturas com a mesma pessoa.")
    for n, v in enumerate(vetores, start=1):
        outro, score = matcher.parecido_com(v.vetor, ignorar=uid)
        if outro is not None:
            raise HTTPException(409, f"O rosto da foto {n} já está cadastrado como {_nome(outro)} "
                                     f"(similaridade {score:.2f}).")
    if uid is not None and uid in set(galeria.instantaneo()[0].tolist()):
        # fotos novas de alguém que já tem biometria precisam bater com a biometria dele
        for n, v in enumerate(vetores, start=1):
            score = dict(matcher.ranking(v.vetor)).get(uid, -1.0)
            if score < config.LIMIAR:
                raise HTTPException(422, f"A foto {n} não parece ser de {_nome(uid)} (similaridade {score:.2f}).")


# ---------- terminal ----------
@app.get("/api/saude")
def saude():
    return {
        "banco": banco_disponivel(),
        "galeria": galeria.tamanho(),
        "modelo_carregado": detector.modelo_carregado(),
        "prova_de_vida": liveness.disponivel(),
        "segredos_padrao": config.USANDO_SEGREDOS_PADRAO,
    }


@app.get("/api/recursos")
def recursos():
    return repositorio.listar_recursos()


@app.post("/api/reconhecer")  # APS-16
async def reconhecer(
    recurso_id: int = Form(...),
    pin: str = Form(""),
    imagens: list[UploadFile] = File(...),
):
    dados = await _ler(imagens)
    # o reconhecimento é pesado (CPU): fora do laço de eventos para não travar as outras requisições
    return await run_in_threadpool(fluxo.tentar_acesso, dados, recurso_id, pin)


# ---------- cadastro (APS-15) ----------
@app.get("/api/divisoes", dependencies=[Depends(admin)])
def divisoes():
    return repositorio.listar_divisoes()


@app.post("/api/qualidade", dependencies=[Depends(admin)])
async def qualidade(foto: UploadFile = File(...)):
    """Confere uma foto na hora da captura: rosto único, nítido, iluminado e se já existe no cadastro."""
    dados = (await _ler([foto], maximo=1))[0]
    r = await run_in_threadpool(lambda: embedding.extrair(decodificar(dados)))
    outro, score = matcher.parecido_com(r.vetor)
    return {
        "ok": True,
        "qualidade": round(r.qualidade, 3),
        "largura_rosto": round(r.bbox[2] - r.bbox[0]),
        "ja_cadastrado": _nome(outro) if outro is not None else None,
        "similaridade": round(score, 3),
    }


@app.post("/api/usuarios", status_code=201, dependencies=[Depends(admin)])
async def cadastrar(
    nome: str = Form(...),
    matricula: str = Form(...),
    cargo: str = Form(""),
    divisao_id: str | None = Form(None),
    nivel: int = Form(...),
    pin: str = Form(""),
    fotos: list[UploadFile] = File(...),
):
    nome, matricula = nome.strip(), matricula.strip()
    if not nome or not matricula:
        raise HTTPException(422, "Nome e matrícula são obrigatórios.")
    if nivel not in (1, 2, 3):
        raise HTTPException(422, "Nível deve ser 1, 2 ou 3.")
    try:
        divisao_id = int(divisao_id) if divisao_id not in (None, "") else None
    except ValueError:
        raise HTTPException(422, "Divisão inválida.")
    if nivel == 2 and not divisao_id:
        raise HTTPException(422, "Diretor de divisão precisa de uma divisão vinculada.")
    if nivel == 3 and not seguranca.formato_pin_ok(pin):
        raise HTTPException(422, "Nível 3 exige PIN de 6 dígitos.")

    conteudos = await _ler(fotos, config.CADASTRO_FOTOS_MIN, config.CADASTRO_FOTOS_MAX)
    # extrai e valida os vetores ANTES de gravar: foto ruim não deixa usuário pela metade
    vetores = await run_in_threadpool(_extrair_vetores, conteudos)
    _validar_biometria(vetores)

    try:
        uid = repositorio.criar_usuario(
            nome, matricula, cargo or None, divisao_id, nivel,
            seguranca.hash_pin(pin) if nivel == 3 else None,
        )
    except mysql.connector.IntegrityError:
        raise HTTPException(409, f"Matrícula {matricula} já cadastrada.")
    for v in vetores:
        repositorio.adicionar_biometria(uid, embedding.para_bytes(v.vetor), v.qualidade)
    galeria.recarregar()
    return {"id": uid, "biometrias": len(vetores)}


@app.post("/api/usuarios/{uid}/biometrias", status_code=201, dependencies=[Depends(admin)])
async def adicionar_fotos(uid: int, fotos: list[UploadFile] = File(...)):
    if not repositorio.obter_usuario(uid):
        raise HTTPException(404, "Usuário não encontrado.")
    conteudos = await _ler(fotos, 1, config.CADASTRO_FOTOS_MAX)
    vetores = await run_in_threadpool(_extrair_vetores, conteudos)
    _validar_biometria(vetores, uid=uid)
    for v in vetores:
        repositorio.adicionar_biometria(uid, embedding.para_bytes(v.vetor), v.qualidade)
    galeria.recarregar()
    return {"biometrias_adicionadas": len(vetores)}


# ---------- gerenciar pessoas (APS-19) ----------
class UsuarioEdicao(BaseModel):
    nome: str | None = None
    cargo: str | None = None
    divisao_id: int | None = None
    nivel: int | None = Field(default=None, ge=1, le=3)
    ativo: bool | None = None
    pin: str | None = None


@app.get("/api/usuarios", dependencies=[Depends(admin)])
def listar_usuarios():
    return repositorio.listar_usuarios()


@app.put("/api/usuarios/{uid}", dependencies=[Depends(admin)])
def editar(uid: int, dados: UsuarioEdicao):
    atual = repositorio.obter_usuario(uid)
    if not atual:
        raise HTTPException(404, "Usuário não encontrado.")
    campos = dados.model_dump(exclude_unset=True)
    pin = campos.pop("pin", None)
    if pin is not None:
        if not seguranca.formato_pin_ok(pin):
            raise HTTPException(422, "PIN deve ter 6 dígitos.")
        campos["pin_hash"] = seguranca.hash_pin(pin)
    nivel = campos.get("nivel", atual["nivel"])
    if nivel == 3 and not (campos.get("pin_hash") or atual["pin_hash"]):
        raise HTTPException(422, "Nível 3 exige PIN de 6 dígitos.")
    if nivel == 2 and not campos.get("divisao_id", atual["divisao_id"]):
        raise HTTPException(422, "Diretor de divisão precisa de uma divisão vinculada.")
    repositorio.atualizar_usuario(uid, campos)
    galeria.recarregar()
    return {"ok": True}


@app.delete("/api/usuarios/{uid}", dependencies=[Depends(admin)])
def remover(uid: int):
    if not repositorio.remover_usuario(uid):
        raise HTTPException(404, "Usuário não encontrado.")
    galeria.recarregar()
    return {"ok": True}


# ---------- logs (APS-18) ----------
def _filtrar(inicio, fim, usuario_id, resultado, limite=500):
    return repositorio.consultar_acessos(inicio, fim, usuario_id, resultado, limite)


@app.get("/api/logs", dependencies=[Depends(admin)])
def logs(inicio: str | None = None, fim: str | None = None,
         usuario_id: int | None = None, resultado: str | None = None):
    return _filtrar(inicio, fim, usuario_id, resultado)


@app.get("/api/resumo", dependencies=[Depends(admin)])
def resumo():
    """Números de hoje para o topo da tela de logs."""
    return repositorio.resumo_do_dia()


@app.get("/api/logs/exportar", dependencies=[Depends(admin)])  # APS-19
def exportar(formato: str = "csv", inicio: str | None = None, fim: str | None = None,
             usuario_id: int | None = None, resultado: str | None = None):
    registros = _filtrar(inicio, fim, usuario_id, resultado, limite=10000)
    if formato == "pdf":
        corpo, tipo = relatorios.para_pdf(registros), "application/pdf"
    elif formato == "csv":
        corpo, tipo = relatorios.para_csv(registros), "text/csv"
    else:
        raise HTTPException(422, "Formato deve ser csv ou pdf.")
    return Response(corpo, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="auditoria.{formato}"'})


@app.get("/api/evidencia/{nome}", dependencies=[Depends(admin)])
def evidencia(nome: str):
    """Foto da tentativa negada. O token vai no cabeçalho (a tela baixa a imagem com fetch),
    nunca na URL — assim ele não fica em histórico do navegador nem em logs de servidor."""
    caminho = (config.DIR_EVIDENCIAS / nome).resolve()
    if caminho.parent != config.DIR_EVIDENCIAS.resolve() or not caminho.is_file():
        raise HTTPException(404, "Evidência não encontrada.")
    return FileResponse(caminho, media_type="image/jpeg")


@app.get("/api/alertas", dependencies=[Depends(admin)])
def alertas():
    return repositorio.alertas_recentes(config.JANELA_ALERTA_MIN)


# ---------- frontend estático (deve ser o último mount) ----------
app.mount("/", StaticFiles(directory=config.BASE_DIR / "web", html=True), name="web")
