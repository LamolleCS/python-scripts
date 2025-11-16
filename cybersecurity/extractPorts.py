#!/home/stolz/prog/python/python-scripts/.venv/bin/python3
# -*- coding: utf-8 -*-

"""
extractPorts.py - Extrae IP y puertos abiertos desde un archivo tipo -oG de nmap.
Uso:
    python extractPorts.py allPorts

Requisitos:
    pip install pyperclip
"""

import re
import sys
import pyperclip
from pathlib import Path

def extract_ip(content: str) -> str | None:
    """Devuelve la primera IP válida encontrada."""
    match = re.search(r'(\d{1,3}\.){3}\d{1,3}', content)
    return match.group(0) if match else None


def extract_ports(content: str) -> list[int]:
    """Devuelve una lista con los puertos abiertos encontrados."""
    ports = re.findall(r'(\d{1,5})/open', content)
    return sorted(set(int(p) for p in ports))


def main():
    if len(sys.argv) != 2:
        print("\n[!] Uso incorrecto.")
        print("Ejemplo: python extractPorts.py allPorts\n")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"[!] Error: No existe el archivo {file_path}")
        sys.exit(1)

    content = file_path.read_text(errors="ignore")

    ip = extract_ip(content)
    ports = extract_ports(content)

    if not ip:
        print("[!] No se encontró ninguna IP en el archivo.")
        sys.exit(1)

    if not ports:
        print("[!] No se detectaron puertos abiertos.")
        sys.exit(1)

    ports_str = ",".join(str(p) for p in ports)

    # Copiar al portapapeles
    pyperclip.copy(ports_str)

    print("\n====================================")
    print("             ExtractPorts            ")
    print("====================================")
    print(f"[*] IP objetivo: {ip}")
    print(f"[*] Puertos abiertos ({len(ports)}): {ports_str}")
    print("[*] ✔ Copiados al clipboard")
    print("====================================\n")


if __name__ == "__main__":
    main()
