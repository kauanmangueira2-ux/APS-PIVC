// Utilidades compartilhadas pelas telas.
const MENU = [
  ["/", "Terminal"], ["/cadastro.html", "Cadastro"],
  ["/pessoas.html", "Pessoas"], ["/logs.html", "Logs"],
];

// Ícones inline (traço, herdam a cor do texto).
const ICONES = {
  cofre: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 4.5 6v5.5c0 4.4 3 8.2 7.5 9.5 4.5-1.3 7.5-5.1 7.5-9.5V6L12 3Z"/><rect x="9" y="10.5" width="6" height="4.5" rx="1"/><path d="M10.5 10.5V9a1.5 1.5 0 0 1 3 0v1.5"/></svg>',
  ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.6 2.6L16 9.5"/></svg>',
  no: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/></svg>',
  aviso: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5 2.8 19.5h18.4L12 3.5Z"/><path d="M12 10v4.2M12 17.2v.1"/></svg>',
};

// Rótulos legíveis para os valores do ENUM acessos.resultado (a ordem define o filtro dos logs).
const ROTULOS = {
  concedido: "Concedido",
  negado_nivel: "Negado · nível",
  negado_divisao: "Negado · divisão",
  negado_horario: "Negado · horário",
  nao_reconhecido: "Não reconhecido",
  falha_liveness: "Falha na prova de vida",
  pin_invalido: "PIN inválido",
  pin_bloqueado: "PIN bloqueado",
};

// Link "Sair" da barra superior: só aparece quando há token de administrador na sessão.
function atualizarSair() {
  const topo = document.querySelector(".topbar");
  if (!topo) return;
  topo.querySelector("#sair")?.remove();
  if (!sessionStorage.getItem("admin_token")) return;
  topo.insertAdjacentHTML("beforeend", `<a href="#" id="sair" class="sair">Sair</a>`);
  topo.querySelector("#sair").addEventListener("click", ev => {
    ev.preventDefault(); sessionStorage.removeItem("admin_token"); location.href = "/";
  });
}

function menu() {
  const atual = location.pathname === "/index.html" ? "/" : location.pathname;
  document.body.insertAdjacentHTML("afterbegin",
    `<header class="topbar"><a class="brand" href="/">${ICONES.cofre}Cofre Biométrico</a><nav>` +
    MENU.map(([h, t]) => `<a href="${h}" class="${h === atual ? "on" : ""}">${t}</a>`).join("") +
    `</nav></header>`);
  atualizarSair();
}

// Token guardado na sessão (aba). Só é gravado depois que o servidor o aceita.
function token() { return sessionStorage.getItem("admin_token") || ""; }

// Pergunta ao servidor se o token vale. Devolve "ok", "invalido" ou "fora".
async function verificarToken(t) {
  try {
    const r = await fetch("/api/admin/verificar", { headers: { "X-Admin-Token": t } });
    return r.ok ? "ok" : (r.status === 401 ? "invalido" : "fora");
  } catch { return "fora"; }
}

function liberarPagina() {
  document.body.classList.add("liberado");
  atualizarSair();
}

// Porta das páginas de administração (<body class="admin">): o conteúdo só aparece
// depois que o servidor confirmar o token. "Cancelar" volta ao terminal público.
async function exigirAdmin() {
  const guardado = token();
  if (guardado && await verificarToken(guardado) === "ok") return liberarPagina();
  sessionStorage.removeItem("admin_token");

  return new Promise(resolve => {
    const fundo = document.createElement("div");
    fundo.className = "loginbg";
    fundo.innerHTML = `<form class="card login" autocomplete="off">
      <div class="marca">${ICONES.cofre}Cofre Biométrico</div>
      <h2>Acesso administrativo</h2>
      <p>Informe o token de administrador (variável ADMIN_TOKEN do arquivo .env).</p>
      <label>Token <input type="password" name="t" required autofocus></label>
      <div class="erro" role="alert" hidden></div>
      <div class="acoes"><button type="submit">Entrar</button>
        <button type="button" class="sec" id="cancelarLogin">Cancelar</button></div></form>`;
    document.body.append(fundo);
    const form = fundo.querySelector("form"), campo = form.t, erro = fundo.querySelector(".erro");
    fundo.querySelector("#cancelarLogin").onclick = () => location.replace("/");
    form.onsubmit = async ev => {
      ev.preventDefault();
      const t = campo.value.trim(); if (!t) return;
      form.querySelector("button[type=submit]").disabled = true;
      const r = await verificarToken(t);
      form.querySelector("button[type=submit]").disabled = false;
      if (r === "ok") {
        sessionStorage.setItem("admin_token", t);
        fundo.remove(); liberarPagina(); resolve();
      } else {
        erro.hidden = false;
        erro.textContent = r === "fora" ? "Servidor fora do ar. Verifique se a API está rodando." : "Token incorreto.";
        campo.value = ""; campo.focus();
      }
    };
  });
}

// Chamada à API; devolve JSON ou lança Error com a mensagem do servidor.
async function api(caminho, opcoes = {}, admin = false) {
  opcoes.headers = { ...(opcoes.headers || {}) };
  if (admin) opcoes.headers["X-Admin-Token"] = token();
  let r;
  try { r = await fetch(caminho, opcoes); }
  catch { throw new Error("Servidor fora do ar. Verifique se a API está rodando."); }
  if (r.status === 401) {
    sessionStorage.removeItem("admin_token");
    if (admin) setTimeout(() => location.reload(), 1200);   // reabre a tela de login
    throw new Error("Token de administrador inválido.");
  }
  const tipo = r.headers.get("content-type") || "";
  const corpo = tipo.includes("json") ? await r.json() : await r.blob();
  if (!r.ok) {
    const det = corpo.mensagem || corpo.detail || "Erro inesperado.";
    const erro = new Error(typeof det === "string" ? det : "Dados inválidos. Confira os campos e tente de novo.");
    erro.status = r.status; erro.dados = corpo instanceof Blob ? {} : corpo;   // ex.: dados.erro, dados.segundos
    throw erro;
  }
  return corpo;
}

// Mostra uma imagem protegida (baixada com o token no cabeçalho) em uma janela sobre a página.
async function mostrarImagemAdmin(caminho, titulo) {
  const blob = await api(caminho, {}, true);
  const url = URL.createObjectURL(blob);
  const d = document.createElement("dialog");
  d.className = "visor";
  d.innerHTML = `<form method="dialog"><div class="visor-topo"><h2>${esc(titulo)}</h2>
    <button class="sec peq" value="fechar" autofocus>Fechar</button></div>
    <img alt="${esc(titulo)}" src="${url}"></form>`;
  document.body.append(d);
  d.addEventListener("close", () => { URL.revokeObjectURL(url); d.remove(); });
  d.addEventListener("click", ev => { if (ev.target === d) d.close(); });   // clique fora fecha
  d.showModal();
}

// --- câmera ---
async function abrirCamera(video) {
  if (!navigator.mediaDevices?.getUserMedia)
    throw new Error("Este navegador não permite câmera. Abra em http://localhost:8000.");
  try {
    const s = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
    video.srcObject = s;
    await video.play();
  } catch (e) {
    throw new Error(e.name === "NotAllowedError"
      ? "Permissão de câmera negada. Libere a câmera no navegador."
      : "Câmera não encontrada. Conecte uma webcam e recarregue.");
  }
}

// O vídeo é exibido espelhado (mais natural diante da tela), mas o quadro enviado é o original.
function quadro(video) {
  if (!video.videoWidth) return Promise.reject(new Error("A câmera ainda não está ativa."));
  const c = document.createElement("canvas");
  c.width = video.videoWidth; c.height = video.videoHeight;
  c.getContext("2d").drawImage(video, 0, 0);
  return new Promise(res => c.toBlob(res, "image/jpeg", 0.92));
}

// Diálogo para pedir um PIN de 6 dígitos. Devolve a string ou null se cancelar.
function pedirPin(titulo = "Nível 3 exige um PIN de 6 dígitos.") {
  return new Promise(resolve => {
    const d = document.createElement("dialog");
    d.innerHTML = `<form method="dialog" autocomplete="off">
      <h2>Definir PIN</h2><p>${esc(titulo)}</p>
      <label>PIN <input type="password" name="pin" inputmode="numeric" maxlength="6" pattern="\\d{6}" required autofocus></label>
      <div class="acoes"><button type="submit" value="ok">Confirmar</button>
        <button type="button" class="sec" value="cancelar">Cancelar</button></div></form>`;
    document.body.append(d);
    const fim = v => { d.close(); d.remove(); resolve(v); };
    d.querySelector("form").onsubmit = ev => { ev.preventDefault(); fim(d.querySelector("input").value); };
    d.querySelector("button[type=button]").onclick = () => fim(null);
    d.addEventListener("cancel", ev => { ev.preventDefault(); fim(null); });
    d.showModal();
  });
}

const esperar = ms => new Promise(r => setTimeout(r, ms));
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function dataHora(s) {
  const m = String(s ?? "").match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}` : String(s ?? "");
}
// Mensagem em bloco (resultado) com ícone: classe = ok | no | aviso.
function bloco(classe, titulo, detalhe = "") {
  return `<div class="resultado ${classe}">${ICONES[classe] || ""}<div>${esc(titulo)}${detalhe ? `<small>${esc(detalhe)}</small>` : ""}</div></div>`;
}
document.addEventListener("DOMContentLoaded", menu);
