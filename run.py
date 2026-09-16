import os

import uvicorn

# Local continua em 127.0.0.1. No container o HOST vem como 0.0.0.0, senao o
# proxy da VPS bate na porta e nao encontra ninguem escutando.
HOST = os.environ.get("PROSPECTOR_HOST", "127.0.0.1")
PORTA = int(os.environ.get("PROSPECTOR_PORTA", "8000"))

if __name__ == "__main__":
    uvicorn.run("app:app", host=HOST, port=PORTA, reload=False)
