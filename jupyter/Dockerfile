# Imagen liviana de Jupyter con lo necesario para los notebooks del proyecto.
FROM python:3.12-slim

RUN pip install --no-cache-dir \
    jupyterlab==4.2.5 \
    pandas==2.2.3 \
    matplotlib==3.9.2 \
    sqlalchemy==2.0.36 \
    psycopg2-binary==2.9.10

WORKDIR /proyecto/notebooks

# Se abre sin token ni contraseña: es un entorno local de revisión.
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", \
     "--IdentityProvider.token=", "--ServerApp.password=", "--notebook-dir=/proyecto"]
