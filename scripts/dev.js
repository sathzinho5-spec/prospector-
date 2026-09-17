#!/usr/bin/env node
// proposito: npm run dev: sobe o Prospector em Python pelo comando padrao do ecossistema
/**
 * `npm run dev` - sobe o Prospector em http://127.0.0.1:8000
 *
 * O projeto e Python; este script existe so pra dar a ele o mesmo comando de
 * partida dos outros projetos do workspace, sem obrigar ninguem a lembrar do
 * caminho da venv.
 *
 * O que ele faz, nesta ordem:
 *   1. Garante o ambiente isolado em venv/ (cria se nao existir).
 *   2. Garante as dependencias do requirements.txt.
 *   3. Garante o Chromium do Playwright, que a varredura do Maps usa.
 *   4. Sobe o servidor e devolve o Ctrl+C pra quem chamou.
 *
 * Numa maquina ja preparada os passos 1 a 3 sao so uma checagem de pasta, entao
 * o servidor sobe direto. Numa maquina limpa, a primeira execucao demora - ela
 * esta baixando o navegador.
 *
 * As checagens dos passos 2 e 3 sao heuristicas de pasta, e isso e intencional:
 * perguntar pro Python custa 3 segundos em toda partida. Se a heuristica errar,
 * o unico efeito e reexecutar um comando idempotente - ela nunca impede o
 * servidor de subir.
 */

const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const RAIZ = path.resolve(__dirname, "..");
const WINDOWS = process.platform === "win32";
const VENV = path.join(RAIZ, "venv");
const VENV_PYTHON = path.join(VENV, WINDOWS ? "Scripts" : "bin", WINDOWS ? "python.exe" : "python");
const URL_LOCAL = "http://127.0.0.1:8000";

function log(mensagem) {
  console.log(`[dev] ${mensagem}`);
}

function erroFatal(mensagem) {
  console.error(`[dev] ERRO: ${mensagem}`);
  process.exit(1);
}

/** Roda um comando ate o fim, herdando o terminal. Aborta a partida se falhar. */
function rodar(comando, args, descricao) {
  const r = spawnSync(comando, args, { cwd: RAIZ, stdio: "inherit" });
  if (r.error) {
    erroFatal(`${descricao} nao pode ser executado: ${r.error.message}`);
  }
  if (r.status !== 0) {
    erroFatal(`${descricao} terminou com codigo ${r.status}.`);
  }
}

/** Primeiro Python do sistema que responda, pra criar a venv. */
function acharPythonBase() {
  const candidatos = WINDOWS
    ? [["py", ["-3"]], ["python", []], ["python3", []]]
    : [["python3", []], ["python", []]];

  for (const [comando, prefixo] of candidatos) {
    const r = spawnSync(comando, [...prefixo, "--version"], { stdio: "ignore" });
    if (!r.error && r.status === 0) return { comando, prefixo };
  }
  return null;
}

/** Onde o Playwright guarda os navegadores nesta maquina. */
function pastaDosNavegadores() {
  const configurada = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (configurada) {
    // "0" significa guardar dentro do proprio pacote; ai nao da pra conferir por
    // pasta, entao deixamos o passo de instalacao decidir.
    return configurada === "0" ? null : configurada;
  }
  if (WINDOWS) {
    const local = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(local, "ms-playwright");
  }
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Caches", "ms-playwright");
  }
  return path.join(os.homedir(), ".cache", "ms-playwright");
}

function temChromium() {
  const pasta = pastaDosNavegadores();
  if (!pasta) return false;
  try {
    return fs.readdirSync(pasta).some((nome) => nome.startsWith("chromium-"));
  } catch {
    return false;
  }
}

function temDependencias() {
  try {
    if (WINDOWS) {
      return fs.existsSync(path.join(VENV, "Lib", "site-packages", "fastapi"));
    }
    // No Linux e no macOS o caminho carrega a versao: lib/python3.x/site-packages
    const lib = path.join(VENV, "lib");
    return fs
      .readdirSync(lib)
      .some((versao) => fs.existsSync(path.join(lib, versao, "site-packages", "fastapi")));
  } catch {
    return false;
  }
}

function prepararAmbiente() {
  if (!fs.existsSync(VENV_PYTHON)) {
    const base = acharPythonBase();
    if (!base) {
      erroFatal("Python nao encontrado no PATH. Instale o Python 3 e rode de novo.");
    }
    log("Ambiente isolado nao existe ainda. Criando venv/ (uma vez so).");
    rodar(base.comando, [...base.prefixo, "-m", "venv", VENV], "a criacao da venv");
  }

  if (!temDependencias()) {
    log("Instalando as dependencias do requirements.txt.");
    rodar(VENV_PYTHON, ["-m", "pip", "install", "-r", "requirements.txt"], "o pip install");
  }

  if (!temChromium()) {
    log("Baixando o Chromium do Playwright. Na primeira vez isso demora alguns minutos.");
    rodar(VENV_PYTHON, ["-m", "playwright", "install", "chromium"], "a instalacao do Chromium");
  }
}

function subirServidor() {
  log(`Subindo o servidor em ${URL_LOCAL} - Ctrl+C encerra.`);

  const servidor = spawn(VENV_PYTHON, ["run.py"], { cwd: RAIZ, stdio: "inherit" });

  servidor.on("error", (e) => erroFatal(`o servidor nao pode ser iniciado: ${e.message}`));

  // Repassa a interrupcao pro Python em vez de deixar processo orfao segurando a porta.
  for (const sinal of ["SIGINT", "SIGTERM"]) {
    process.on(sinal, () => {
      if (!servidor.killed) servidor.kill(sinal);
    });
  }

  servidor.on("exit", (codigo, sinal) => {
    if (sinal) process.exit(0);
    process.exit(codigo === null ? 1 : codigo);
  });
}

function main() {
  if (!fs.existsSync(path.join(RAIZ, "run.py"))) {
    erroFatal(`run.py nao encontrado em ${RAIZ}. Rode o comando dentro da pasta do projeto.`);
  }
  prepararAmbiente();
  subirServidor();
}

main();
