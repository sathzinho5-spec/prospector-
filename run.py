# proposito: sobe o uvicorn, com os cabecalhos do proxy quando roda na VPS
import os

import uvicorn

# Local continua em 127.0.0.1. No container o HOST vem como 0.0.0.0, senao o
# proxy da VPS bate na porta e nao encontra ninguem escutando.
HOST = os.environ.get("PROSPECTOR_HOST", "127.0.0.1")
PORTA = int(os.environ.get("PROSPECTOR_PORTA", "8000"))

if __name__ == "__main__":
    # forwarded_allow_ips="*" porque quem fala com este servidor e o proxy da
    # VPS, que e outro container. Sem isso o uvicorn descarta os cabecalhos
    # dele e o sistema passa a ver TODO mundo com o IP do proxy e chegando por
    # http. As duas coisas quebram algo: o freio de forca bruta trancaria todo
    # mundo junto, e o cookie de sessao nunca seria marcado como seguro.
    # Abrir pra "*" so e seguro porque o container nao publica porta nenhuma:
    # o unico caminho ate ele e passando pelo proxy.
    uvicorn.run("app:app", host=HOST, port=PORTA, reload=False,
                proxy_headers=True, forwarded_allow_ips="*")
