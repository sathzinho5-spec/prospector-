# proposito: quem sabe enviar: Simulado, Evolution API e Meta Cloud API
import datetime
import re
import time

import requests

class SimuladoProvider:
    name = "simulado"

    def send(self, phone, message):
        print(f"[disparo-simulado] para {phone}: {message[:60]}...")
        return True, ""


def _erro_amigavel(status, body):
    """Traduz erros da Evolution para linguagem humana."""
    txt = str(body or "")
    if '"exists":false' in txt.replace(" ", "") or '"exists": false' in txt:
        return "Este número não existe no WhatsApp (conta desativada ou inválida)."
    if status in (401, 403):
        return "Evolution recusou a autenticação — confira a API key nas Configurações."
    if status == 404:
        return "Instância não encontrada — confira o nome da instância nas Configurações."
    if "not connected" in txt.lower() or "connection" in txt.lower() and "closed" in txt.lower():
        return "WhatsApp desconectado — escaneie o QR de novo no painel Disparo."
    return f"Evolution HTTP {status}: {txt[:150]}"


class EvolutionProvider:
    name = "evolution"

    def __init__(self, base_url, apikey, instance):
        self.base_url = (base_url or "").rstrip("/")
        self.apikey = apikey or ""
        self.instance = instance or ""

    def _headers(self):
        return {"apikey": self.apikey, "Content-Type": "application/json"}

    def _check_cfg(self):
        if not self.base_url or not self.apikey or not self.instance:
            return False, "Evolution não configurado (url/key/instance)"
        return True, ""

    def numero_existe(self, phone):
        """Pergunta a Evolution se o numero existe no WhatsApp. Devolve
        (existe, erro). Erro preenchido significa que a pergunta NAO pode ser
        feita, e nesse caso nao se envia: tentativa em numero morto e
        justamente o que queima o chip."""
        try:
            r = requests.post(
                f"{self.base_url}/chat/whatsappNumbers/{self.instance}",
                headers=self._headers(),
                json={"numbers": [phone]},
                timeout=30,
            )
            if r.status_code not in (200, 201):
                return False, _erro_amigavel(r.status_code, r.text)
            dados = r.json()
            if isinstance(dados, list) and dados:
                return bool(dados[0].get("exists")), ""
            return False, "A Evolution nao respondeu se o numero existe."
        except Exception as e:
            return False, str(e)[:200]

    def send(self, phone, message):
        ok, err = self._check_cfg()
        if not ok:
            return False, err
        # Conferir ANTES de mandar. Depois do sendText a tentativa ja foi gasta,
        # e o erro bonito nao devolve a reputacao do numero.
        existe, err_check = self.numero_existe(phone)
        if err_check:
            return False, err_check
        if not existe:
            return False, "Este numero nao existe no WhatsApp (conta desativada ou invalida)."
        try:
            r = requests.post(
                f"{self.base_url}/message/sendText/{self.instance}",
                headers=self._headers(),
                json={"number": phone, "text": message},
                timeout=60,
            )
            if r.status_code in (200, 201):
                return True, ""
            return False, _erro_amigavel(r.status_code, r.text)
        except Exception as e:
            return False, str(e)[:200]

    def criar_instancia(self):
        ok, err = self._check_cfg()
        if not ok:
            return False, err, ""
        try:
            r = requests.post(
                f"{self.base_url}/instance/create",
                headers=self._headers(),
                json={"instanceName": self.instance, "qrcode": True,
                      "integration": "WHATSAPP-BAILEYS"},
                timeout=30,
            )
            if r.status_code not in (200, 201):
                return False, f"HTTP {r.status_code}: {r.text[:200]}", ""
            data = r.json()
            qr = ((data.get("qrcode") or {}).get("base64")
                  or data.get("base64") or "")
            return True, "", qr
        except Exception as e:
            return False, str(e)[:200], ""

    def numero_dono(self):
        """Numero do chip pareado nesta instancia, so digitos, "" quando a
        Evolution nao devolve. NAO conferido contra a Evolution real desta
        operacao: cobre os dois nomes de campo conhecidos (ownerJid e number)
        e as duas formas de resposta do fetchInstances (instancia solta ou
        aninhada em "instance"). Sem numero, quem chama mostra o que ja
        mostrava."""
        ok, _ = self._check_cfg()
        if not ok:
            return ""
        try:
            r = requests.get(
                f"{self.base_url}/instance/fetchInstances",
                headers=self._headers(),
                params={"instanceName": self.instance},
                timeout=15,
            )
            if r.status_code not in (200, 201):
                return ""
            dados = r.json()
        except Exception:
            return ""
        if isinstance(dados, dict):
            dados = [dados]
        if not isinstance(dados, list):
            return ""
        for item in dados:
            if not isinstance(item, dict):
                continue
            info = item.get("instance") if isinstance(item.get("instance"), dict) else item
            nome = info.get("instanceName") or info.get("name") or ""
            if nome and nome != self.instance:
                continue
            bruto = info.get("ownerJid") or info.get("owner") or info.get("number") or ""
            digitos = "".join(c for c in str(bruto) if c.isdigit())
            if digitos:
                return digitos
        return ""

    def estado(self):
        ok, err = self._check_cfg()
        if not ok:
            return {"conectado": False, "erro": err, "estado": "nao_configurado"}
        try:
            r = requests.get(
                f"{self.base_url}/instance/connectionState/{self.instance}",
                headers=self._headers(),
                timeout=15,
            )
            if r.status_code not in (200, 201):
                return {"conectado": False, "estado": f"http_{r.status_code}",
                        "erro": r.text[:200]}
            st = (r.json().get("instance") or {}).get("state") or r.json().get("state", "")
            conectado = st == "open"
            # So pergunta o numero quando ha chip pareado: evita uma segunda
            # chamada HTTP por instancia desconectada a cada atualizacao da tela.
            return {"conectado": conectado, "estado": st, "erro": "",
                    "numero": self.numero_dono() if conectado else ""}
        except Exception as e:
            return {"conectado": False, "estado": "offline", "erro": str(e)[:200]}

    @staticmethod
    def _texto(msg):
        if not isinstance(msg, dict):
            return ""
        if msg.get("conversation"):
            return msg["conversation"]
        ext = msg.get("extendedTextMessage") or {}
        if ext.get("text"):
            return ext["text"]
        for k in ("imageMessage", "videoMessage", "documentMessage", "audioMessage"):
            m = msg.get(k) or {}
            if m.get("caption"):
                return "[img] " + m["caption"]
            if k in msg:
                return f"[{k.replace('Message', '').lower()}]"
        if msg.get("buttonsResponseMessage"):
            return msg["buttonsResponseMessage"].get("selectedDisplayText", "[botão]")
        if msg.get("listResponseMessage"):
            return msg["listResponseMessage"].get("title", "[lista]")
        if msg.get("reactionMessage"):
            return msg["reactionMessage"].get("text", "[reação]")
        pt = msg.get("protocolMessage") or {}
        if pt.get("type"):
            return f"[sistema: {pt['type']}]"
        return ""

    @staticmethod
    def _quando(ts):
        try:
            import datetime as _dt
            return _dt.datetime.fromtimestamp(int(ts)).strftime("%d/%m %H:%M")
        except Exception:
            return ""

    def listar_chats(self):
        ok, err = self._check_cfg()
        if not ok:
            return False, err, []
        try:
            r = requests.post(
                f"{self.base_url}/chat/findChats/{self.instance}",
                headers=self._headers(),
                json={},
                timeout=30,
            )
            if r.status_code not in (200, 201):
                return False, f"HTTP {r.status_code}: {r.text[:200]}", []
            data = r.json()
            if isinstance(data, list):
                chats = data
            elif isinstance(data, dict):
                chats = data.get("chats") or data.get("data") or data.get("result") or []
                if not chats:
                    print(f"[evo] findChats formato desconhecido: chaves={list(data.keys())}")
            else:
                chats = []
            out = []
            for c in chats or []:
                jid = c.get("remoteJid", "")
                if not jid or "@g.us" in jid or "status@" in jid:
                    continue
                fone = re.sub(r"\D", "", jid.split("@")[0])
                nome = c.get("pushName") or c.get("name") or fone
                lm = c.get("lastMessage")
                if isinstance(lm, dict):
                    ultima = self._texto(lm.get("message", {}))
                else:
                    ultima = str(lm or "")
                out.append({
                    "jid": jid,
                    "telefone": fone,
                    "nome": nome,
                    "foto": c.get("profilePicUrl") or "",
                    "ultima": (ultima or "")[:120],
                    "quando": c.get("updatedAt") or "",
                    "nao_lidas": c.get("unreadCount", 0),
                })
            return True, "", out
        except Exception as e:
            return False, str(e)[:200], []

    def mensagens(self, jid, limite=50):
        ok, err = self._check_cfg()
        if not ok:
            return False, err, []
        try:
            r = requests.post(
                f"{self.base_url}/chat/findMessages/{self.instance}",
                headers=self._headers(),
                json={"where": {"key": {"remoteJid": jid}}, "limit": int(limite)},
                timeout=30,
            )
            if r.status_code not in (200, 201):
                return False, f"HTTP {r.status_code}: {r.text[:200]}", []
            data = r.json() or {}
            recs = ((data.get("messages") or {}).get("records")
                    if isinstance(data.get("messages"), dict)
                    else data.get("messages")) or []
            out = []
            for m in recs:
                key = m.get("key") or {}
                out.append({
                    "de_mim": bool(key.get("fromMe")),
                    "texto": self._texto(m.get("message", {})),
                    "quando": self._quando(m.get("messageTimestamp")),
                    "ts": m.get("messageTimestamp", 0),
                    "tipo": m.get("messageType", ""),
                })
            out.sort(key=lambda x: x["ts"] or 0)
            return True, "", out
        except Exception as e:
            return False, str(e)[:200], []


class MetaCloudProvider:
    name = "meta"

    def __init__(self, token, phone_id):
        self.token = token or ""
        self.phone_id = phone_id or ""

    def send(self, phone, message):
        if not self.token or not self.phone_id:
            return False, "Meta Cloud não configurado (token/phone_id)"
        try:
            r = requests.post(
                f"https://graph.facebook.com/v21.0/{self.phone_id}/messages",
                headers={"Authorization": f"Bearer {self.token}",
                         "Content-Type": "application/json"},
                json={"messaging_product": "whatsapp", "to": phone,
                      "type": "text", "text": {"body": message}},
                timeout=60,
            )
            if r.status_code in (200, 201):
                return True, ""
            return False, _erro_amigavel(r.status_code, r.text)
        except Exception as e:
            return False, str(e)[:200]


def _eh_falha_conexao(err):
    """Distingue problema na CONEXÃO/conta (troca de chip) de problema no LEAD (ex: número inexistente)."""
    t = str(err or "").lower()
    chaves = ["timed out", "timeout", "failed to establish", "connection",
              "desconectado", "offline", "autentica", "nao_configurado",
              "name or service not known", "getaddrinfo", "max retries"]
    return any(k in t for k in chaves)


def _build_providers(cfg):
    """Monta a lista de provedores (1 por chip no modo Evolution)."""
    which = (cfg.get("provider") or "simulado").lower()
    if which == "meta":
        return [MetaCloudProvider(cfg.get("meta_token"), cfg.get("meta_phone_id"))]
    if which == "evolution":
        insts = [i.strip() for i in (cfg.get("evo_instances") or []) if i.strip()]
        if not insts and cfg.get("evo_instance"):
            insts = [cfg["evo_instance"].strip()]
        if not insts:
            insts = [""]
        return [EvolutionProvider(cfg.get("evo_url"), cfg.get("evo_key"), inst) for inst in insts]
    return [SimuladoProvider()]


def _make_provider(cfg):
    """Compat: retorna o primeiro provedor (usado em teste/envio avulso)."""
    lst = _build_providers(cfg)
    return lst[0] if lst else SimuladoProvider()


# ---------------- Worker ----------------
