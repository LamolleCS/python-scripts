#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import platform
import subprocess
from typing import Optional

try:
    from termcolor import colored
    COLOR = True
except ImportError:
    COLOR = False


TTL_OS_MAP = {
    255: "Cisco / Unix-based",
    128: "Windows",
    64: "Linux / Unix / Android / macOS",
    60: "AIX / BSD (old)"
}


def colorize(text, color):
    return colored(text, color) if COLOR else text


def is_valid_ip(ip: str) -> bool:
    pattern = re.compile(
        r"^(25[0-5]|2[0-4]\d|[0-1]?\d?\d)"
        r"(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}$"
    )
    return bool(pattern.match(ip))


def execute_ping(ip: str) -> Optional[str]:
    count_flag = "-c" if platform.system() != "Windows" else "-n"
    cmd = ["ping", count_flag, "1", ip]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            text=True
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def extract_ttl(ping_output: str) -> Optional[int]:
    match = re.search(r"ttl[=|:](\d+)", ping_output, re.IGNORECASE)
    return int(match.group(1)) if match else None


def identify_os(ttl: int) -> str:
    # Buscar match exacto primero
    if ttl in TTL_OS_MAP:
        return TTL_OS_MAP[ttl]

    # Inferencia por rangos
    if ttl >= 240:
        return "Probable Cisco / Device"
    elif ttl >= 120:
        return "Probable Windows"
    elif ttl >= 50:
        return "Probable Linux/Unix/macOS"
    else:
        return "Desconocido / Alterado / Firewall"


def main(ip: str):
    if not is_valid_ip(ip):
        print(colorize("[!] Dirección IP inválida", "red"))
        sys.exit(1)

    print(colorize(f"[*] Enviando ping a {ip} ...", "cyan"))

    output = execute_ping(ip)
    if not output:
        print(colorize("[!] No se pudo obtener respuesta.", "red"))
        sys.exit(1)

    ttl = extract_ttl(output)
    if ttl is None:
        print(colorize("[!] No se encontró TTL en la salida.", "red"))
        sys.exit(1)

    os_guess = identify_os(ttl)

    print()
    print(colorize("[*] RESULTADO", "yellow"))
    print(colorize(f"[*] IP  : {ip}", "cyan"))
    print(colorize(f"[*] TTL : {ttl}", "cyan"))
    if COLOR:
        print(colorize(f"[*] {os_guess}", "green"))
    else:
        print(f"[*] {os_guess}")
    print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Uso: python3 {sys.argv[0]} <IP>")
        sys.exit(1)

    main(sys.argv[1])
