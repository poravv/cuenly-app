from app.modules.openai_processor.xml_parser import ParaguayanXMLParser

def test_sifen_v150_new_fields_extraction():
    parser = ParaguayanXMLParser()
    
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rDE xmlns="http://ekuatia.set.gov.py/sifen/xsd">
        <dVerFor>150</dVerFor>
        <DE Id="01234567890123456789012345678901234567890123">
            <gTimb>
                <iTiDE>1</iTiDE>
                <dDesTiDE>Factura electrónica</dDesTiDE>
                <dNumTim>12345678</dNumTim>
                <dEst>001</dEst>
                <dPunExp>001</dPunExp>
                <dNumDoc>0000123</dNumDoc>
            </gTimb>
            <gDatGralOpe>
                <dFeEmiDE>2023-10-27T10:00:00</dFeEmiDE>
                <gOpeDE>
                    <iIndPres>1</iIndPres>
                    <dDesIndPres>Operación presencial</dDesIndPres>
                </gOpeDE>
            </gDatGralOpe>
            <gEmis>
                <dRucEm>80000000</dRucEm>
                <dDVEmi>5</dDVEmi>
            </gEmis>
            <gDtipDE>
                <gCamCond>
                    <gPagCred>
                        <iCondCred>1</iCondCred>
                        <dDCondCred>Plazo</dDCondCred>
                        <dPlazoCre>30</dPlazoCre>
                    </gPagCred>
                </gCamCond>
                <gCamItem>
                    <dCodInt>ITEM1</dCodInt>
                    <dDesProSer>Producto de Prueba</dDesProSer>
                    <dCantProSer>1.0</dCantProSer>
                    <dDesUniMed>UNIDAD</dDesUniMed>
                    <gValorItem>
                        <dPUniProSer>100000.0</dPUniProSer>
                        <gValorRestaItem>
                            <dTotOpeItem>100000.0</dTotOpeItem>
                        </gValorRestaItem>
                    </gValorItem>
                    <gCamIVA>
                        <dTasaIVA>10</dTasaIVA>
                        <dPropIVA>100</dPropIVA>
                    </gCamIVA>
                </gCamItem>
                <gCamEsp>
                    <gGrupAdi>
                        <dCiclo>Octubre 2023</dCiclo>
                        <dFecIniC>2023-10-01</dFecIniC>
                        <dFecFinC>2023-10-31</dFecFinC>
                    </gGrupAdi>
                </gCamEsp>
                <gTransp>
                    <iModTrans>1</iModTrans>
                    <iRespFlete>2</iRespFlete>
                    <dNuDespImp>12345-IM</dNuDespImp>
                </gTransp>
            </gDtipDE>
            <gTotSub>
                <dLtotIsc>5000.0</dLtotIsc>
                <dBaseImpISC>50000.0</dBaseImpISC>
                <dSubVISC>55000.0</dSubVISC>
            </gTotSub>
        </DE>
        <gCamFuFD>
             <dCarQR>https://ekuatia.set.gov.py/consultas/qr?id=0123456789</dCarQR>
             <dInfAdic>Gracias por su compra</dInfAdic>
        </gCamFuFD>
    </rDE>
    """
    
    success, data = parser.parse_xml(mock_xml)
    
    assert success == True
    
    # Validar extracción básica de QR y URL
    assert data.get('qr_url') == "https://ekuatia.set.gov.py/consultas/qr?id=0123456789"
    assert data.get('info_adicional') == "Gracias por su compra"
    
    # Validar Datos del Documento y Presencia
    assert data.get('tipo_documento_electronico') == "Factura electrónica"
    assert data.get('ind_presencia') == "Operación presencial"
    
    # Validar Transorte
    assert data.get('transporte_modalidad_codigo') == "1"
    assert data.get('transporte_nro_despacho') == "12345-IM"
    
    # Validar Ciclo de Facturación
    assert data.get('ciclo_facturacion') == "Octubre 2023"
    
    # Validar Condición de Crédito
    assert data.get('cond_credito_codigo') == "1"
    assert data.get('cond_credito') == "Plazo"
    assert data.get('plazo_credito_dias') == 30
    
    # Validar ISC
    assert data.get('isc_total') == 5000.0
    assert data.get('isc_base_imponible') == 50000.0
    
    print("✅ Test exitoso! Todos los campos nuevos del SIFEN han sido parseados y mapeados correctamente.")

if __name__ == "__main__":
    test_sifen_v150_new_fields_extraction()
