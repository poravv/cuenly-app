import sys
from pathlib import Path

# Agregar backend/ al PYTHONPATH para que los tests encuentren el módulo 'app'
sys.path.insert(0, str(Path(__file__).parent.parent))
