# Prospector na VPS. Python com o Chromium do Playwright junto, porque a
# varredura do Maps, do Google e do Instagram roda por navegador de verdade.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PROSPECTOR_HOST=0.0.0.0 \
    PROSPECTOR_PORTA=8000 \
    PROSPECTOR_DADOS=/app/dados \
    PLAYWRIGHT_BROWSERS_PATH=/opt/navegadores

WORKDIR /app

COPY requirements.txt ./

# O navegador e instalado pelo proprio Playwright ja instalado aqui, nunca por
# versao escolhida a mao: navegador e biblioteca fora de par falham so na hora
# de abrir a pagina, com erro que nao diz que a culpa e da versao.
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m playwright install --with-deps chromium

COPY app.py config.py contas.py niches.py run.py scheduler.py storage.py ./
COPY analysis/ analysis/
COPY scrapers/ scrapers/
COPY web/ web/
COPY tools/ tools/

# Configuracoes e resultados vem por volume. Se entrassem na imagem, cada
# publicacao apagaria a chave da OpenAI e o sessionid do Instagram.
RUN mkdir -p /app/dados

EXPOSE 8000

CMD ["python", "run.py"]
