"""
Estado global de la aplicación — instancia única de CuenlyApp.
Importado por api.py y los routers que necesitan invoice_sync.
"""
from app.main import CuenlyApp

invoice_sync = CuenlyApp()
