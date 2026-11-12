# Cofre Biométrico — Ministério do Meio Ambiente

Identificação facial com três níveis de permissão. APS 5º/6º Ciência da Computação 2026/2 · PIVC.

**Stack:** Python **3.11** (o `mediapipe==0.10.14` só tem pacote até o 3.12) · OpenCV · InsightFace (SCRFD + ArcFace) · MediaPipe FaceMesh (prova de vida) · FastAPI · MySQL 8 · frontend web.

## Instalação

Se o seu Python padrão for mais novo, instale o 3.11 ao lado dele (pelo instalador do python.org; um não atrapalha o outro) e crie o ambiente com ele:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # ajuste DB_PASSWORD, ADMIN_TOKEN, PIN_PEPPER

python -m db.init_db          # cria o banco e os dados de demonstração (e atualiza bancos de versões anteriores)
python main.py                # http://localhost:8000
```

Na primeira execução o servidor baixa o modelo `buffalo_l` (~300 MB) em segundo plano; `GET /api/saude` mostra `modelo_carregado: true` quando ele estiver pronto. O FaceMesh já vem dentro do pacote do MediaPipe.

## Cadastrar biometrias

- **Pela tela:** `http://localhost:8000/cadastro.html` (pede o token do `.env`).
- **Em lote:** coloque fotos em `dados/cadastro/<matricula>/` e rode `python -m db.cadastro_lote`.

Ao capturar cada foto, a tela confere na hora se há um único rosto nítido e iluminado e se ele já está cadastrado. Ao salvar, o servidor recusa fotos de pessoas diferentes misturadas e rostos que já pertencem a outra matrícula.

Dados de demonstração: matrículas `1001` (nível 1), `2001` (nível 2, Biodiversidade), `2002` (nível 2, Recursos Hídricos), `3001` (ministro, PIN `123456`).

## Níveis de acesso

| Nível | Quem | Pode |
|---|---|---|
| 1 | Servidores | Antessala e catálogo de toxinas |
| 2 | Diretores de divisão | + acervo da **própria** divisão, só 08h–18h (antessala e catálogo não têm horário) |
| 3 | Ministro | Cofre principal; exige **prova de vida + PIN** |

Regras de segurança:

- **Identificação:** o rosto precisa passar do limiar (`LIMIAR`, 0,40) **e** vencer a segunda pessoa mais parecida por uma margem (`MARGEM_IDENTIFICACAO`, 0,05); empate entre dois cadastrados = não reconhecido.
- **Prova de vida (nível 3):** rajada de 15 quadros; exige olhos abertos → fechados → abertos, com limiar relativo ao olho da própria pessoa; reprova se aparecer um segundo rosto ou se quem pisca não for quem foi identificado.
- **PIN:** guardado com PBKDF2-HMAC-SHA256 (200 mil iterações, sal por PIN + pepper do `.env`). PINs antigos (SHA-256) continuam válidos e são convertidos no primeiro acesso correto. Três PINs errados da mesma pessoa bloqueiam o PIN dela por 15 minutos.
- **Terminal:** três negativas seguidas (em até 60 s) travam o terminal por 60 s, com contagem regressiva na tela. Toda negativa grava o quadro em `dados/evidencias/`; negativas no cofre principal geram alerta na tela de logs.
- **Administração:** token no cabeçalho `X-Admin-Token` (nunca na URL, nem para ver evidências); 5 tokens errados do mesmo IP em 5 minutos bloqueiam novas tentativas (HTTP 429).
- **API:** limite de 20 imagens e 5 MB por imagem por envio; cabeçalhos de segurança (CSP, `X-Frame-Options`, `nosniff`, `no-store` nas rotas da API).

## Estrutura

```
main.py · config.py
visao/   captura · preproc · detector · embedding · liveness   (fases 1–4)
core/    galeria · matcher · permissoes · auditoria · fluxo    (fase 5 + regras)
db/      schema.sql · repositorio · init_db · cadastro_lote
api/     app.py                                                (rotas)
web/     index (terminal) · cadastro · pessoas · logs
testes/  test_permissoes.py · avaliacao.py (FAR, FRR, ROC)
docs/    fluxo.md · gerar_figuras.py
```

Fluxo completo e rotas: [`docs/fluxo.md`](docs/fluxo.md).

## Testes e métricas

```powershell
pytest                              # regras, fluxo completo, bloqueio e API (sem MySQL/câmera)
python -m testes.avaliacao          # acurácia, FAR, FRR, ROC, matriz de confusão
python docs/gerar_figuras.py foto.jpg   # figura das fases para a dissertação
python -m testes.calibrar_piscada   # mostra o EAR ao vivo e conta piscadas na sua webcam
```

Calibre `LIMIAR` (padrão 0,40) com a curva de `docs/figuras/roc.png`.

## Configuração

Tudo em `config.py`, com variáveis do `.env` quando existem: `LIMIAR`, `ADMIN_TOKEN`, `PIN_PEPPER`, `DB_*`, `CTX_ID`. Se `ADMIN_TOKEN`/`PIN_PEPPER` estiverem com os valores padrão, o servidor avisa na inicialização e `GET /api/saude` devolve `segredos_padrao: true`. Esse mesmo endpoint informa se o banco e a prova de vida (MediaPipe) estão funcionando.

Se o cofre principal negar tudo com "Prova de vida falhou" mesmo piscando, confira `/api/saude` (`prova_de_vida: true`) e rode `python -m testes.calibrar_piscada`: se a contagem de piscadas não sobe quando você pisca, aumente `PISCADA_QUEDA` em `config.py` (ex.: 0,75); para exigir duas piscadas, mude `PISCADAS_EXIGIDAS` para 2.

## Backlog (Jira APS)

| Sprint | Tarefas | Onde está |
|---|---|---|
| APS-1 Design | 6, 7, 8 | `docs/fluxo.md` |
| APS-2 Banco | 9, 10, 11 | `db/schema.sql`, `db/init_db.py` |
| APS-3 Backend | 12–19 | `api/`, `core/`, `visao/` |
| APS-4 Frontend | 20–23 | `web/` |
| APS-5 Documentação | 24 | este arquivo |
