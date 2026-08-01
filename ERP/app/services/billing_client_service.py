"""Cliente/adquirente para facturación SRI (upsert desde formulario)."""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.services.sri_catastro_service import (
    consultar_contribuyente,
    consultar_direccion_matriz,
    normalizar_identificacion,
    ruc_para_consulta,
)
from app.utils.sri_constants import CONSUMIDOR_FINAL, inferir_tipo_identificacion


def _cliente_dict(client: Client) -> dict:
    identificacion = client.ruc_ci or ""
    razon_social = client.company or client.name or ""
    return {
        "id": client.id,
        "tipo_identificacion": client.tipo_identificacion or inferir_tipo_identificacion(identificacion),
        "identificacion": identificacion,
        "razon_social": razon_social,
        "direccion": client.address or "",
        "email": client.email or "",
        "telefono": client.phone or "",
        "label": f"{identificacion or 'sin ID'} — {razon_social}",
    }


def list_local_clients(db: Session, search: str = "") -> list[dict]:
    """Catálogo local de clientes (equivalente a ClientesService.findAll en FactuSRI)."""
    q = db.query(Client).order_by(Client.name)
    term = (search or "").strip()
    if term:
        like = f"%{term}%"
        q = q.filter(
            or_(
                Client.name.ilike(like),
                Client.company.ilike(like),
                Client.ruc_ci.ilike(like),
                Client.email.ilike(like),
            )
        )
    return [_cliente_dict(c) for c in q.limit(500).all()]


def find_client_by_identificacion(db: Session, identificacion: str) -> Client | None:
    identificacion = normalizar_identificacion(identificacion)
    if not identificacion:
        return None

    filters = [Client.ruc_ci == identificacion]
    if len(identificacion) == 10:
        filters.append(Client.ruc_ci == f"{identificacion}001")
    if len(identificacion) == 13 and identificacion.endswith("001"):
        filters.append(Client.ruc_ci == identificacion[:10])

    return db.query(Client).filter(or_(*filters)).first()


def consult_client_identificacion(db: Session, identificacion_input: str) -> dict:
    identificacion = normalizar_identificacion(identificacion_input)
    if len(identificacion) < 3:
        return {"source": "manual", "mensaje": "Ingrese una identificación válida"}

    local = find_client_by_identificacion(db, identificacion)
    if local:
        return {
            "source": "local",
            "cliente": _cliente_dict(local),
            "mensaje": "Cliente encontrado en el catálogo ERP",
        }

    if identificacion == CONSUMIDOR_FINAL:
        return {
            "source": "sri",
            "sugerido": {
                "tipo_identificacion": "CONSUMIDOR_FINAL",
                "identificacion": identificacion,
                "razon_social": "CONSUMIDOR FINAL",
                "direccion": "",
            },
            "mensaje": "Consumidor final",
        }

    ruc_consulta = ruc_para_consulta(identificacion)
    if not ruc_consulta:
        return {
            "source": "manual",
            "mensaje": "No se encontró en clientes. Complete los datos manualmente.",
            "sugerido": {
                "tipo_identificacion": inferir_tipo_identificacion(identificacion),
                "identificacion": identificacion,
                "razon_social": "",
                "direccion": "",
            },
        }

    contribuyente = consultar_contribuyente(ruc_consulta)
    if not contribuyente or not contribuyente.get("razon_social"):
        return {
            "source": "manual",
            "mensaje": "No se encontró en el catastro del SRI. Complete los datos manualmente.",
            "sugerido": {
                "tipo_identificacion": inferir_tipo_identificacion(identificacion),
                "identificacion": identificacion,
                "razon_social": "",
                "direccion": "",
            },
        }

    direccion = consultar_direccion_matriz(ruc_consulta)
    estado = contribuyente.get("estado_contribuyente")
    mensaje = "Datos obtenidos del catastro del SRI"
    if estado:
        mensaje = f"Datos obtenidos del SRI ({estado})"

    return {
        "source": "sri",
        "sugerido": {
            "tipo_identificacion": inferir_tipo_identificacion(identificacion),
            "identificacion": identificacion,
            "razon_social": contribuyente["razon_social"],
            "direccion": direccion or "",
            "estado_contribuyente": estado,
        },
        "mensaje": mensaje,
    }


def consult_sri_identificacion(identificacion_input: str) -> dict:
    """Consulta únicamente el catastro del SRI (sin buscar en catálogo local)."""
    identificacion = normalizar_identificacion(identificacion_input)
    if len(identificacion) < 3:
        return {"source": "manual", "mensaje": "Ingrese una cédula o RUC válido"}

    if identificacion == CONSUMIDOR_FINAL:
        return {
            "source": "sri",
            "sugerido": {
                "tipo_identificacion": "CONSUMIDOR_FINAL",
                "identificacion": identificacion,
                "razon_social": "CONSUMIDOR FINAL",
                "direccion": "",
            },
            "mensaje": "Consumidor final",
        }

    ruc_consulta = ruc_para_consulta(identificacion)
    if not ruc_consulta:
        return {
            "source": "manual",
            "mensaje": "Identificación no válida para consulta SRI. Use cédula (10) o RUC (13).",
            "sugerido": {
                "tipo_identificacion": inferir_tipo_identificacion(identificacion),
                "identificacion": identificacion,
                "razon_social": "",
                "direccion": "",
            },
        }

    contribuyente = consultar_contribuyente(ruc_consulta)
    if not contribuyente or not contribuyente.get("razon_social"):
        return {
            "source": "manual",
            "mensaje": "No se encontró en el catastro del SRI.",
            "sugerido": {
                "tipo_identificacion": inferir_tipo_identificacion(identificacion),
                "identificacion": identificacion,
                "razon_social": "",
                "direccion": "",
            },
        }

    direccion = consultar_direccion_matriz(ruc_consulta)
    estado = contribuyente.get("estado_contribuyente")
    mensaje = f"Datos obtenidos del SRI ({estado})" if estado else "Datos obtenidos del catastro del SRI"
    return {
        "source": "sri",
        "sugerido": {
            "tipo_identificacion": inferir_tipo_identificacion(identificacion),
            "identificacion": identificacion,
            "razon_social": contribuyente["razon_social"],
            "direccion": direccion or "",
            "estado_contribuyente": estado,
        },
        "mensaje": mensaje,
    }


def consult_local_client(db: Session, identificacion_input: str) -> dict:
    """Busca solo en el catálogo de clientes del ERP."""
    identificacion = normalizar_identificacion(identificacion_input)
    if len(identificacion) < 1:
        return {"source": "manual", "mensaje": "Ingrese identificación o seleccione un cliente"}

    local = find_client_by_identificacion(db, identificacion)
    if local:
        return {
            "source": "local",
            "cliente": _cliente_dict(local),
            "mensaje": "Cliente encontrado en su catálogo",
        }
    return {
        "source": "manual",
        "mensaje": "No hay un cliente registrado con esa identificación.",
    }


def upsert_client_from_adquirente(
    db: Session,
    *,
    client_id: int | None,
    tipo_identificacion: str,
    identificacion: str,
    razon_social: str,
    direccion: str = "",
    telefono: str = "",
    email: str = "",
) -> Client:
    identificacion = (identificacion or "").strip()
    razon_social = (razon_social or "").strip()
    email = (email or "").strip()

    if not identificacion or not razon_social:
        raise ValueError("Identificación y razón social del adquirente son obligatorias.")
    if not email:
        raise ValueError("El correo electrónico del adquirente es obligatorio.")

    tipo = (tipo_identificacion or inferir_tipo_identificacion(identificacion)).strip().upper()

    client = None
    if client_id:
        client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        client = find_client_by_identificacion(db, identificacion)

    if client:
        client.tipo_identificacion = tipo
        client.ruc_ci = identificacion
        client.company = razon_social
        client.name = razon_social
        client.address = (direccion or "").strip() or client.address
        client.phone = (telefono or "").strip() or client.phone
        client.email = email
        db.commit()
        db.refresh(client)
        return client

    client = Client(
        tipo_identificacion=tipo,
        ruc_ci=identificacion,
        company=razon_social,
        name=razon_social,
        address=(direccion or "").strip() or None,
        phone=(telefono or "").strip() or None,
        email=email,
        client_type="cliente",
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client
