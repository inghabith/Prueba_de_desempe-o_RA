#!/usr/bin/env bash
# Prepara Airflow antes de que arranquen el webserver y el scheduler.
# Se ejecuta en el servicio airflow-init de docker-compose y termina al finalizar.
# Todos los comandos son repetibles: se puede correr varias veces sin errores.
set -euo pipefail

echo "1. Creando o actualizando la base de metadatos de Airflow"
airflow db migrate

echo "2. Creando el usuario administrador (si ya existe, se omite)"
airflow users create \
  --username "${AIRFLOW_ADMIN_USER}" \
  --password "${AIRFLOW_ADMIN_PASSWORD}" \
  --firstname Admin \
  --lastname DataMart \
  --role Admin \
  --email admin@datamart.local || true

echo "3. Registrando las Airflow Connections"
# Repositorio analítico (PostgreSQL destino del pipeline).
airflow connections delete dw_postgres >/dev/null 2>&1 || true
airflow connections add dw_postgres \
  --conn-type postgres \
  --conn-host postgres-dw \
  --conn-port 5432 \
  --conn-schema datamart_dw \
  --conn-login "${POSTGRES_USER}" \
  --conn-password "${POSTGRES_PASSWORD}"

# API interna de productos (fuente del catálogo y sus categorías).
airflow connections delete api_productos >/dev/null 2>&1 || true
airflow connections add api_productos \
  --conn-type http \
  --conn-host api-productos \
  --conn-port 8000

echo "4. Inicializando las Airflow Variables"
airflow variables set ruta_datos "/opt/airflow/data"
airflow variables set zona_horaria_origen "Europe/London"
airflow variables set tamano_pagina_api "500"

echo "Airflow quedó listo."
