from app.utils.clave_acceso import tipo_identificacion_sri
from app.utils.sri_xml_utils import (
    escape_xml,
    format_cantidad,
    format_date_sri,
    format_decimal,
    format_entero_o_decimal,
    format_precio_unitario,
    format_tarifa,
)


def _build_impuestos_resumen(detalles):
    grouped = {}
    for d in detalles:
        key = f"{d['codigo_iva']}-{d['tarifa_iva']}"
        if key not in grouped:
            grouped[key] = {
                "codigo_porcentaje": d["codigo_iva"],
                "tarifa": float(d["tarifa_iva"]),
                "base_imponible": 0.0,
                "valor": 0.0,
            }
        grouped[key]["base_imponible"] += float(d["precio_total_sin_impuesto"])
        grouped[key]["valor"] += float(d["valor_iva"])
    return list(grouped.values())


def _build_info_adicional(campos, cliente):
    merged = {}
    if cliente.get("telefono"):
        merged["Telefono"] = cliente["telefono"].strip()
    if cliente.get("email"):
        merged["Email"] = cliente["email"].strip()
    if cliente.get("direccion"):
        merged["Direccion"] = cliente["direccion"].strip()
    for campo in campos or []:
        nombre = (campo.get("nombre") or "").strip()
        valor = (campo.get("valor") or "").strip()
        if nombre and valor:
            merged[nombre] = valor
    if not merged:
        return ""
    campos_xml = "".join(
        f'<campoAdicional nombre="{escape_xml(n)}">{escape_xml(v)}</campoAdicional>'
        for n, v in merged.items()
    )
    return f"<infoAdicional>{campos_xml}</infoAdicional>"


def build_factura_xml(company, factura, cliente, detalles):
    ambiente = "2" if company["ambiente"] == "PRODUCCION" else "1"
    tipo_emision = "2" if company.get("tipo_emision") == "CONTINGENCIA" else "1"
    impuestos = _build_impuestos_resumen(detalles)

    total_con_impuestos = "".join(
        f"""
            <totalImpuesto>
                <codigo>2</codigo>
                <codigoPorcentaje>{i['codigo_porcentaje']}</codigoPorcentaje>
                <baseImponible>{format_decimal(i['base_imponible'])}</baseImponible>
                <valor>{format_decimal(i['valor'])}</valor>
            </totalImpuesto>"""
        for i in impuestos
    )

    detalles_xml = "".join(
        f"""<detalle>
      <codigoPrincipal>{escape_xml(d['codigo_principal'])}</codigoPrincipal>
      {f"<codigoAuxiliar>{escape_xml(d['codigo_auxiliar'])}</codigoAuxiliar>" if d.get('codigo_auxiliar') else ''}
      <descripcion>{escape_xml(d['descripcion'])}</descripcion>
      <cantidad>{format_cantidad(d['cantidad'])}</cantidad>
      <precioUnitario>{format_precio_unitario(d['precio_unitario'])}</precioUnitario>
      <descuento>{format_entero_o_decimal(d['descuento'])}</descuento>
      <precioTotalSinImpuesto>{format_decimal(d['precio_total_sin_impuesto'])}</precioTotalSinImpuesto>
      <impuestos>
        <impuesto>
          <codigo>2</codigo>
          <codigoPorcentaje>{d['codigo_iva']}</codigoPorcentaje>
          <tarifa>{format_tarifa(d['tarifa_iva'])}</tarifa>
          <baseImponible>{format_decimal(d['precio_total_sin_impuesto'])}</baseImponible>
          <valor>{format_decimal(d['valor_iva'])}</valor>
        </impuesto>
      </impuestos>
    </detalle>"""
        for d in detalles
    )

    info_adicional = _build_info_adicional(factura.get("info_adicional"), cliente)
    pagos = factura.get("pagos") or [{"forma_pago": "01", "total": factura["importe_total"]}]
    pagos_xml = "".join(
        f"""
            <pago>
                <formaPago>{p['forma_pago']}</formaPago>
                <total>{format_decimal(p['total'])}</total>
                {f"<plazo>{p['plazo']}</plazo><unidadTiempo>{escape_xml(p['unidad_tiempo'])}</unidadTiempo>" if p.get('plazo') is not None and p.get('unidad_tiempo') else ''}
            </pago>"""
        for p in pagos
    )

    rimpe = ""
    if company.get("contribuyente_rimpe"):
        rimpe = f"<contribuyenteRimpe>{escape_xml(company['contribuyente_rimpe'])}</contribuyenteRimpe>"

    contrib_especial = ""
    if company.get("contribuyente_especial"):
        contrib_especial = f"<contribuyenteEspecial>{escape_xml(company['contribuyente_especial'])}</contribuyenteEspecial>"

    nombre_comercial = ""
    nc = (company.get("nombre_comercial") or "").strip()
    rs = (company.get("razon_social") or "").strip()
    if nc and nc.lower() != rs.lower():
        nombre_comercial = f"<nombreComercial>{escape_xml(nc)}</nombreComercial>"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<factura id="comprobante" version="1.1.0">
  <infoTributaria>
    <ambiente>{ambiente}</ambiente>
    <tipoEmision>{tipo_emision}</tipoEmision>
    <razonSocial>{escape_xml(company['razon_social'])}</razonSocial>
    {nombre_comercial}
    <ruc>{company['ruc']}</ruc>
    <claveAcceso>{factura['clave_acceso']}</claveAcceso>
    <codDoc>01</codDoc>
    <estab>{factura['codigo_establecimiento']}</estab>
    <ptoEmi>{factura['codigo_punto_emision']}</ptoEmi>
    <secuencial>{factura['secuencial']}</secuencial>
    <dirMatriz>{escape_xml(company['direccion_matriz'])}</dirMatriz>
    {rimpe}
  </infoTributaria>
  <infoFactura>
    <fechaEmision>{format_date_sri(factura['fecha_emision'])}</fechaEmision>
    <dirEstablecimiento>{escape_xml(factura['dir_establecimiento'])}</dirEstablecimiento>
    <obligadoContabilidad>{'SI' if company.get('obligado_contabilidad') else 'NO'}</obligadoContabilidad>
    {contrib_especial}
    <tipoIdentificacionComprador>{tipo_identificacion_sri(cliente['tipo_identificacion'])}</tipoIdentificacionComprador>
    <razonSocialComprador>{escape_xml(cliente['razon_social'])}</razonSocialComprador>
    <identificacionComprador>{escape_xml(cliente['identificacion'])}</identificacionComprador>
    <totalSinImpuestos>{format_decimal(factura['subtotal_sin_impuestos'])}</totalSinImpuestos>
    <totalDescuento>{format_decimal(factura['descuento'])}</totalDescuento>
    <totalConImpuestos>{total_con_impuestos}
        </totalConImpuestos>
    <propina>{format_entero_o_decimal(factura.get('propina', 0))}</propina>
    <importeTotal>{format_decimal(factura['importe_total'])}</importeTotal>
    <moneda>DOLAR</moneda>
    <pagos>{pagos_xml}
        </pagos>
  </infoFactura>
  <detalles>{detalles_xml}</detalles>
  {info_adicional}
</factura>"""


def build_nota_credito_xml(company, nota, cliente, detalles):
    ambiente = "2" if company["ambiente"] == "PRODUCCION" else "1"
    tipo_emision = "2" if company.get("tipo_emision") == "CONTINGENCIA" else "1"
    impuestos = _build_impuestos_resumen(detalles)

    total_con_impuestos = "".join(
        f"""
            <totalImpuesto>
                <codigo>2</codigo>
                <codigoPorcentaje>{i['codigo_porcentaje']}</codigoPorcentaje>
                <baseImponible>{format_decimal(i['base_imponible'])}</baseImponible>
                <valor>{format_decimal(i['valor'])}</valor>
            </totalImpuesto>"""
        for i in impuestos
    )

    detalles_xml = "".join(
        f"""<detalle>
      <codigoInterno>{escape_xml(d['codigo_principal'])}</codigoInterno>
      {f"<codigoAdicional>{escape_xml(d['codigo_auxiliar'])}</codigoAdicional>" if d.get('codigo_auxiliar') else ''}
      <descripcion>{escape_xml(d['descripcion'])}</descripcion>
      <cantidad>{format_cantidad(d['cantidad'])}</cantidad>
      <precioUnitario>{format_precio_unitario(d['precio_unitario'])}</precioUnitario>
      <descuento>{format_entero_o_decimal(d['descuento'])}</descuento>
      <precioTotalSinImpuesto>{format_decimal(d['precio_total_sin_impuesto'])}</precioTotalSinImpuesto>
      <impuestos>
        <impuesto>
          <codigo>2</codigo>
          <codigoPorcentaje>{d['codigo_iva']}</codigoPorcentaje>
          <tarifa>{format_tarifa(d['tarifa_iva'])}</tarifa>
          <baseImponible>{format_decimal(d['precio_total_sin_impuesto'])}</baseImponible>
          <valor>{format_decimal(d['valor_iva'])}</valor>
        </impuesto>
      </impuestos>
    </detalle>"""
        for d in detalles
    )

    info_adicional = _build_info_adicional(nota.get("info_adicional"), cliente)
    rimpe = ""
    if company.get("contribuyente_rimpe"):
        rimpe = f"<contribuyenteRimpe>{escape_xml(company['contribuyente_rimpe'])}</contribuyenteRimpe>"

    contrib_especial = ""
    if company.get("contribuyente_especial"):
        contrib_especial = f"<contribuyenteEspecial>{escape_xml(company['contribuyente_especial'])}</contribuyenteEspecial>"

    nombre_comercial = ""
    nc_name = (company.get("nombre_comercial") or "").strip()
    rs = (company.get("razon_social") or "").strip()
    if nc_name and nc_name.lower() != rs.lower():
        nombre_comercial = f"<nombreComercial>{escape_xml(nc_name)}</nombreComercial>"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<notaCredito id="comprobante" version="1.1.0">
  <infoTributaria>
    <ambiente>{ambiente}</ambiente>
    <tipoEmision>{tipo_emision}</tipoEmision>
    <razonSocial>{escape_xml(company['razon_social'])}</razonSocial>
    {nombre_comercial}
    <ruc>{company['ruc']}</ruc>
    <claveAcceso>{nota['clave_acceso']}</claveAcceso>
    <codDoc>04</codDoc>
    <estab>{nota['codigo_establecimiento']}</estab>
    <ptoEmi>{nota['codigo_punto_emision']}</ptoEmi>
    <secuencial>{nota['secuencial']}</secuencial>
    <dirMatriz>{escape_xml(company['direccion_matriz'])}</dirMatriz>
    {rimpe}
  </infoTributaria>
  <infoNotaCredito>
    <fechaEmision>{format_date_sri(nota['fecha_emision'])}</fechaEmision>
    <dirEstablecimiento>{escape_xml(nota['dir_establecimiento'])}</dirEstablecimiento>
    <tipoIdentificacionComprador>{tipo_identificacion_sri(cliente['tipo_identificacion'])}</tipoIdentificacionComprador>
    <razonSocialComprador>{escape_xml(cliente['razon_social'])}</razonSocialComprador>
    <identificacionComprador>{escape_xml(cliente['identificacion'])}</identificacionComprador>
    <obligadoContabilidad>{'SI' if company.get('obligado_contabilidad') else 'NO'}</obligadoContabilidad>
    {contrib_especial}
    <codDocModificado>{nota['cod_doc_modificado']}</codDocModificado>
    <numDocModificado>{escape_xml(nota['num_doc_modificado'])}</numDocModificado>
    <fechaEmisionDocSustento>{format_date_sri(nota['fecha_emision_doc_sustento'])}</fechaEmisionDocSustento>
    <totalSinImpuestos>{format_decimal(nota['subtotal_sin_impuestos'])}</totalSinImpuestos>
    <valorModificacion>{format_decimal(nota['importe_total'])}</valorModificacion>
    <moneda>DOLAR</moneda>
    <totalConImpuestos>{total_con_impuestos}
        </totalConImpuestos>
    <motivo>{escape_xml(nota['motivo'])}</motivo>
  </infoNotaCredito>
  <detalles>{detalles_xml}</detalles>
  {info_adicional}
</notaCredito>"""
