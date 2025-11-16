#!/home/stolz/prog/python/python-scripts/.venv/bin/python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import shutil
import platform

# Colores ──────────────────────────────────────────────────────────
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"


def ping_host(target_ip: str) -> bool:
    """Realiza ping según el sistema operativo."""
    print(f"{BLUE}[*] Comprobando si la máquina responde al ping...{RESET}")

    param = "-n" if platform.system().lower() == "windows" else "-c"
    
    result = subprocess.run(["ping", param, "1", target_ip],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    
    if result.returncode == 0:
        print(f"{GREEN}[+] Máquina activa{RESET}")
        return True
    else:
        print(f"{RED}[-] La máquina no responde al ping. Continuaré igualmente.{RESET}")
        return False


def run_script(script_name: str, *args):
    """Ejecuta un script Python externo y retorna su salida."""
    print(f"{CYAN}[*] Ejecutando {script_name}...{RESET}")
    result = subprocess.run(
        ["python3", script_name, *args],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"{RED}[!] Error ejecutando {script_name}:{RESET}\n{result.stderr}")
        sys.exit(1)

    print(result.stdout.strip())
    return result.stdout.strip()


def run_command(command_list: list, description: str):
    """Ejecuta comandos externos como Nmap."""
    print(f"{CYAN}[*] {description}{RESET}")
    result = subprocess.run(command_list, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"{RED}[!] Error ejecutando comando:{RESET}\n{result.stderr}")
        sys.exit(1)

    return result.stdout


def main():
    if len(sys.argv) != 2:
        print(f"{YELLOW}Uso: python3 mainRecon.py <IP>{RESET}")
        sys.exit(1)

    target_ip = sys.argv[1]

    # 1️⃣ Ping
    ping_host(target_ip)

    # 2️⃣ Detectar OS remoto
    run_script("whichOs.py", target_ip)

    # 3️⃣ Scan inicial full ports
    print(f"{BLUE}[*] Ejecutando escaneo Nmap completo...{RESET}")
    run_command(
        ["nmap", "-p-", "--open", "-sS", "--min-rate", "5000",
         "-vvv", "-n", "-Pn", target_ip, "-oG", "allPorts"],
        "Escaneo full de puertos"
    )
    print(f"{GREEN}[+] Escaneo inicial realizado -> archivo: allPorts{RESET}")

    # 4️⃣ Extraer puertos usando extractPorts.py
    ports_output = run_script("extractPorts.py", "allPorts")

    # Sanitizar puertos
    ports = ports_output.strip().replace(" ", "").replace("\n", "")
    if not ports:
        print(f"{RED}[!] No se encontraron puertos abiertos.{RESET}")
        sys.exit(1)

    print(f"{GREEN}[+] Puertos detectados: {ports}{RESET}")

    # 5️⃣ Escaneo dirigido con -sCV
    print(f"{BLUE}[*] Ejecutando escaneo dirigido...{RESET}")
    run_command(
        ["nmap", f"-p{ports}", "-sCV", target_ip, "-oN", "targeted"],
        "Escaneo Nmap enfocado"
    )
    print(f"{GREEN}[+] Escaneo detallado completado -> archivo: targeted{RESET}")

    # 6️⃣ Mostrar resultados con bat (alias de cat)
    print(f"{BLUE}[*] Mostrando resultados...{RESET}")
    subprocess.run(["bat", "-l", "python", "targeted"])


if __name__ == "__main__":
    main()
