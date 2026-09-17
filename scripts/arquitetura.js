// proposito: acha o gerador de mapa da Dodo e roda; sem ele, avisa e nao quebra o lint
//
// O gerador mora no workspace da Dodo, nao dentro deste projeto (Regra de Ouro 6:
// uma ferramenta, nao uma copia por projeto). Este repositorio tem outro dono, que
// nao tem o workspace. Por isso a ausencia da ferramenta NAO e erro: e so ausencia.
// O ARQUITETURA.md ja vem gerado e commitado, entao nada depende de rodar isto aqui.

const { existsSync } = require("node:fs");
const { spawnSync } = require("node:child_process");
const { join, resolve } = require("node:path");

const RAIZ = resolve(__dirname, "..");
const RELATIVO = join("Agente Orquestrador", "tools", "gerar_arquitetura.py");

const candidatos = [
  process.env.DODO_TOOLS ? join(process.env.DODO_TOOLS, "gerar_arquitetura.py") : null,
  resolve(RAIZ, "..", "..", "..", RELATIVO),
  resolve(RAIZ, "..", "..", RELATIVO),
].filter(Boolean);

const ferramenta = candidatos.find((c) => existsSync(c));

if (!ferramenta) {
  console.log("gerador de mapa da Dodo nao encontrado neste ambiente, pulando.");
  console.log("O ARQUITETURA.md commitado continua valendo.");
  console.log("Pra gerar: DODO_TOOLS=<caminho>/Agente Orquestrador/tools npm run mapa");
  process.exit(0);
}

const python = process.platform === "win32" ? "python" : "python3";
const r = spawnSync(python, [ferramenta, RAIZ, ...process.argv.slice(2)], { stdio: "inherit" });
process.exit(r.status === null ? 1 : r.status);
