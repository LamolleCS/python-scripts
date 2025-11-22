#!/home/stolz/prog/python/python-scripts/.venv/bin/python3
# -*- coding: utf-8 -*-

# -------------------- Colores ANSI --------------------

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

"""

Herramienta de vocabulario para textos en varios idiomas.

- Cuenta palabras únicas (ignorando una lista opcional).
- Traduce cada palabra al español usando:
    1) DeepL (requiere DEEPL_API_KEY)
    2) MyMemory
- Usa cache.json para no volver a traducir la misma palabra.
- Muestra una tabla formateada en la terminal.
- Permite guardar resultados en CSV/TXT, interactivo o con --save.

Idiomas soportados (flag -l / --lang):
    de, en, pt, it   (por defecto: de)
"""

import deepl
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Requests es opcional pero muy recomendable
try:
    import requests
except ImportError:
    requests = None

# -------------------- Constantes de configuración --------------------

SUPPORTED_LANGS = ["de", "en", "pt", "it", "es"]
DEFAULT_LANG = "de"
TARGET_LANG = "es"  # siempre traducimos al español en esta versión

MAX_LITERAL_LEN = 800
DEFAULT_IGNORE_FILENAME = "ignore.txt"
CACHE_FILENAME = "cache.json"

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")  # setear en tu sistema

DEEPL_CLIENT = None
if DEEPL_API_KEY:
    try:
        DEEPL_CLIENT = deepl.DeepLClient(DEEPL_API_KEY)
    except Exception as e:
        print(f"⚠️ No se pudo inicializar DeepL: {e}")
        DEEPL_CLIENT = None


# -------------------- Utilidades básicas --------------------


def normalize_word(word: str, lang: str) -> str:
    """
    Devuelve una versión normalizada de la palabra para:
    - agrupar
    - ignorar
    - cachear

    PERO NO se usa para mostrar. Para alemán, normaliza ß/ä/ö/ü.
    Luego pasa todo a minúsculas.
    """
    word = word.strip()
    if not word:
        return ""

    if lang == "de":
        # reemplazo simple: no es lingüísticamente perfecto, pero sirve para agrupar
        word = (word
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("Ä", "Ae")
                .replace("Ö", "Oe")
                .replace("Ü", "Ue")
                .replace("ß", "ss"))
    # para otros idiomas por ahora no normalizamos caracteres especiales
    return word.lower()


def contains_number(word: str) -> bool:
    """
    Verifica si una palabra contiene algún dígito.
    """
    return any(char.isdigit() for char in word)


def tokenize(text: str):
    """
    Extrae "palabras" usando una expresión regular Unicode.
    Ej: "Maßstäbe," -> "Maßstäbe"
    """
    # \w incluye letras con acentos y unicode en Python 3
    return re.findall(r"\b\w+\b", text, flags=re.UNICODE)


def read_text_from_inputs(inputs, lang: str):
    """
    Procesa los argumentos posicionales:
    - Si son rutas de archivos existentes, los lee.
    - Si no son archivos, se trata como texto literal (con límite de longitud).
    - Si no hay inputs, intenta leer de stdin.
    """
    text_chunks = []

    if inputs:
        for item in inputs:

            # 1) Si contiene espacios → es texto literal
            # 2) Si es demasiado largo para ser nombre de archivo → texto literal
            if " " in item or len(item) > 200:
                # Texto literal
                if len(item) > MAX_LITERAL_LEN:
                    print(f"❌ Texto literal demasiado largo ({len(item)} caracteres).", file=sys.stderr)
                    print("   Para textos largos, usá un archivo .txt o stdin (cat archivo.txt | python vocab.py).")
                    sys.exit(1)
                text_chunks.append(item)
                continue

            # 3) Si no cumple lo anterior, PUEDE ser archivo → probamos
            p = Path(item)
            if p.is_file():
                try:
                    text_chunks.append(p.read_text(encoding="utf8"))
                except UnicodeDecodeError:
                    print(f"❌ No se pudo leer '{item}' como UTF-8.", file=sys.stderr)
                    sys.exit(1)
                continue

            # 4) Si no es archivo → texto literal corto
            if len(item) > MAX_LITERAL_LEN:
                print(f"❌ Texto literal demasiado largo ({len(item)} caracteres).", file=sys.stderr)
                sys.exit(1)

            text_chunks.append(item)

    else:
        # Leer stdin
        if not sys.stdin.isatty():
            data = sys.stdin.read()
            if not data.strip():
                print("❌ No se recibió texto desde stdin.", file=sys.stderr)
                sys.exit(1)
            text_chunks.append(data)
        else:
            print("Uso:")
            print("  python vocab.py texto.txt")
            print('  python vocab.py "Texto literal"')
            print("  cat texto.txt | python vocab.py")
            sys.exit(1)

    return "\n".join(text_chunks)



# -------------------- Manejo de ignorados --------------------


def load_ignore_words(script_dir: Path, exclude_path: str, lang: str):
    """
    Carga palabras a ignorar según la lógica acordada:

    - Si el usuario pasa --exclude RUTA:
        * Si existe → usar SOLO esa.
        * Si no existe → error y salir.

    - Si NO pasa --exclude:
        * Buscamos DEFAULT_IGNORE_FILENAME en la carpeta del script.
        * Si existe → usarlo.
        * Si no → no se excluye nada.
    
    Devuelve un dict con:
    - 'normalized': set de palabras normalizadas
    - 'originals': set de palabras originales (sin normalizar)
    """
    ignore_normalized = set()
    ignore_originals = set()

    if exclude_path:
        path = Path(exclude_path)
        if not path.is_file():
            print(f"❌ Archivo de exclusión no encontrado: '{exclude_path}'", file=sys.stderr)
            sys.exit(1)
        paths_to_use = [path]
    else:
        default_path = script_dir / DEFAULT_IGNORE_FILENAME
        if default_path.is_file():
            paths_to_use = [default_path]
            print(f"ℹ️ Usando archivo de exclusión por defecto: '{default_path.name}'")
        else:
            print("ℹ️ No se encontró ignore.txt. No se excluirán palabras.")
            paths_to_use = []

    for p in paths_to_use:
        try:
            with p.open("r", encoding="utf8") as f:
                for line in f:
                    w = line.strip()
                    if not w:
                        continue
                    # Guardar tanto normalizada como original
                    ignore_originals.add(w.lower())
                    norm = normalize_word(w, lang)
                    if norm:
                        ignore_normalized.add(norm)
        except UnicodeDecodeError:
            print(f"❌ No se pudo leer '{p}' como UTF-8.", file=sys.stderr)
            sys.exit(1)

    return {
        'normalized': ignore_normalized,
        'originals': ignore_originals
    }


# -------------------- Cache --------------------


def load_cache(cache_path: Path):
    """
    Carga cache.json si existe, sino devuelve dict vacío.
    Estructura:
    {
        "de": { "massstaebe": "criterios", ... },
        "en": { ... },
        ...
    }
    """
    if not cache_path.is_file():
        return {}
    try:
        with cache_path.open("r", encoding="utf8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        # cache roto → empezamos de cero
        return {}


def save_cache(cache_path: Path, cache: dict):
    try:
        with cache_path.open("w", encoding="utf8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=True)
    except Exception as e:
        print(f"⚠️ No se pudo guardar cache en '{cache_path}': {e}", file=sys.stderr)


# -------------------- Traducción (APIs externas) --------------------


def translate_with_deepl(text: str, source_lang: str, target_lang: str):
    """
    Traducción usando el SDK oficial de DeepL.
    Devuelve None si falla para permitir fallback a MyMemory.
    """
    if DEEPL_CLIENT is None:
        return None

    try:
        # DeepL usa códigos como "DE", "EN", "ES", "PT", "IT"
        source = source_lang.upper()
        target = target_lang.upper()

        # IMPORTANTE: el SDK requiere target_lang SIEMPRE,
        # pero source_lang es opcional si el idioma se detecta solo.
        result = DEEPL_CLIENT.translate_text(
            text,
            source_lang=source,
            target_lang=target
        )

        if hasattr(result, "text"):
            return result.text.strip()
        return None

    except Exception as e:
        # si falla, devolvemos None para activar backups
        print(f"[DEBUG] DeepL ERROR: {e}")
        return None


def translate_with_mymemory(text: str, source_lang: str, target_lang: str):
    if not requests:
        return None
    params = {
        "q": text,
        "langpair": f"{source_lang}|{target_lang}",
    }
    resp = requests.get("https://api.mymemory.translated.net/get", params=params, timeout=10)
    resp.raise_for_status()
    js = resp.json()
    data = js.get("responseData") or {}
    translated = data.get("translatedText")
    if translated:
        return translated.strip()
    return None




def get_translation(norm_key: str,
                    original_word: str,
                    lang: str,
                    lang_cache: dict,
                    debug=False):

    """
    Devuelve la traducción de una palabra usando:
    - cache -> DeepL -> MyMemory -> "X"
    """

    # 1) Cache
    if norm_key in lang_cache:
        if debug:
            print(f"[DEBUG] Cache → {original_word} = {lang_cache[norm_key]}")
        return lang_cache[norm_key]

    source_lang = lang
    target_lang = TARGET_LANG

    # 2) DeepL
    if debug:
        print(f"{BLUE}[DEBUG]{RESET} DeepL → traduciendo '{original_word}'...")
    try:
        result = translate_with_deepl(original_word, source_lang, target_lang)
        if result:
            if debug:
                print(f"{GREEN}[DEBUG]{RESET} DeepL ✔ '{original_word}' → {result}")
            lang_cache[norm_key] = result
            return result
        else:
            if debug:
                print(f"{YELLOW}[DEBUG]{RESET} DeepL ✖ sin resultado para '{original_word}'")
    except Exception as e:
        if debug:
            print(f"{RED}[DEBUG]{RESET} DeepL ERROR: {e}")

    # 3) MyMemory
    if debug:
        print(f"{BLUE}[DEBUG]{RESET} MyMemory → traduciendo '{original_word}'...")
    try:
        result = translate_with_mymemory(original_word, source_lang, target_lang)
        if result:
            if debug:
                print(f"{GREEN}[DEBUG]{RESET} MyMemory ✔ '{original_word}' → {result}")
            lang_cache[norm_key] = result
            return result
        else:
            if debug:
                print(f"{YELLOW}[DEBUG]{RESET} MyMemory ✖ sin resultado para '{original_word}'")
    except Exception as e:
        if debug:
            print(f"{RED}[DEBUG]{RESET} MyMemory ERROR: {e}")

    # 4) Si TODO falla
    if debug:
        print(f"{RED}[DEBUG]{RESET} Fallback final: '{original_word}' → X")
    lang_cache[norm_key] = "X"
    return "X"


# -------------------- Conteo de palabras --------------------


def count_words(text: str, lang: str, ignore_dict):
    """
    Cuenta palabras:
    - mantiene la forma original (primera vista) para mostrar
    - agrupa por forma normalizada para contar y traducir
    - ignora las que estén en ignore_dict (normalizadas o originales)
    - ignora palabras que contienen números
    """

    tokens = tokenize(text)
    total_tokens = len(tokens)

    words_data = {}  # norm -> {"original": str, "count": int}
    
    ignore_normalized = ignore_dict['normalized']
    ignore_originals = ignore_dict['originals']

    for original in tokens:
        # Filtrar palabras con números
        if contains_number(original):
            continue
            
        norm = normalize_word(original, lang)
        if not norm:
            continue
            
        # Filtrar palabras en ignore.txt (normalizada)
        if norm in ignore_normalized:
            continue
            
        # Filtrar palabras en ignore.txt (original en minúsculas)
        if original.lower() in ignore_originals:
            continue

        entry = words_data.get(norm)
        if entry is None:
            words_data[norm] = {"original": original, "count": 1}
        else:
            entry["count"] += 1

    considered_tokens = sum(v["count"] for v in words_data.values())

    return words_data, total_tokens, considered_tokens


# -------------------- Formateo y salida --------------------


def format_table(entries):
    """
    entries: lista de tuplas (original, count, meaning)
    Devuelve una cadena con una tabla bonita.
    """
    header_word = f"{BLUE}Palabra{RESET}"
    header_freq = f"{YELLOW}Frecuencia{RESET}"
    header_mean = f"{GREEN}Significado(s){RESET}"

    # cálculos de ancho (sin ANSI)
    def strip_ansi(s):
        import re
        return re.sub(r'\x1b\[[0-9;]*m', '', s)

    max_word = max([len(strip_ansi("Palabra"))] + [len(strip_ansi(e[0])) for e in entries]) if entries else len(strip_ansi("Palabra"))
    max_freq = max([len(strip_ansi("Frecuencia"))] + [len(str(e[1])) for e in entries]) if entries else len(strip_ansi("Frecuencia"))
    max_mean = max([len(strip_ansi("Significado(s)"))] + [len(strip_ansi(e[2])) for e in entries]) if entries else len(strip_ansi("Significado(s)"))

    sep_line = "━" * (max_word + max_freq + max_mean + 8)

    lines = [sep_line]
    header = f" {header_word.ljust(max_word)} | {header_freq.center(max_freq)} | {header_mean.ljust(max_mean)}"
    lines.append(header)
    lines.append(sep_line)

    for original, count, meaning in entries:
        line = f" {BLUE}{original.ljust(max_word)}{RESET} | {YELLOW}{str(count).center(max_freq)}{RESET} | {GREEN}{meaning.ljust(max_mean)}{RESET}"
        lines.append(line)

    lines.append(sep_line)
    return "\n".join(lines)


def save_as_csv(path: Path, entries):
    with path.open("w", encoding="utf8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["palabra", "frecuencia", "significado"])
        for original, count, meaning in entries:
            writer.writerow([original, count, meaning])


def save_as_txt(path: Path, entries):
    with path.open("w", encoding="utf8") as f:
        f.write("Palabra | Frecuencia | Significado(s)\n")
        f.write("-" * 60 + "\n")
        for original, count, meaning in entries:
            f.write(f"{original} | {count} | {meaning}\n")


def auto_filenames():
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base = f"vocab_output_{ts}"
    return Path(base + ".csv"), Path(base + ".txt")


def handle_save_option(save_opt: str, entries):
    """
    Lógica de guardado cuando el usuario pasa --save.
    - "csv", "txt", "both"/"all" → nombres automáticos en cwd.
    - otra cosa → tratamos como ruta:
        * si termina en .csv → CSV
        * si termina en .txt → TXT
        * si es carpeta → genera archivo con nombre automático adentro
        * si tiene otro nombre sin extensión → asumimos .csv
    """
    if not entries:
        print("No hay entradas para guardar.")
        return

    save_opt = save_opt.strip()

    lower = save_opt.lower()
    csv_path_auto, txt_path_auto = auto_filenames()

    if lower in ("csv", "txt", "both", "all"):
        if lower in ("csv", "both", "all"):
            save_as_csv(csv_path_auto, entries)
            print(f"✅ CSV guardado en: {csv_path_auto}")
        if lower in ("txt", "both", "all"):
            save_as_txt(txt_path_auto, entries)
            print(f"✅ TXT guardado en: {txt_path_auto}")
        return

    # tratamos save_opt como ruta
    path = Path(save_opt)

    if path.is_dir():
        # guardar dentro de la carpeta
        csv_p, txt_p = auto_filenames()
        if not csv_p.is_absolute():
            csv_p = path / csv_p.name
        if not txt_p.is_absolute():
            txt_p = path / txt_p.name
        save_as_csv(csv_p, entries)
        print(f"✅ CSV guardado en: {csv_p}")
        return

    # si tiene extensión
    if path.suffix.lower() == ".csv":
        save_as_csv(path, entries)
        print(f"✅ CSV guardado en: {path}")
    elif path.suffix.lower() == ".txt":
        save_as_txt(path, entries)
        print(f"✅ TXT guardado en: {path}")
    else:
        # sin extensión conocida → asumimos CSV
        if not path.suffix:
            path = path.with_suffix(".csv")
        save_as_csv(path, entries)
        print(f"✅ CSV guardado en: {path}")


def interactive_save(entries):
    if not entries:
        print("No hay entradas para guardar.")
        return
    print()
    print("¿Dónde querés guardar los resultados?")
    print("[ 1 ] CSV")
    print("[ 2 ] TXT")
    print("[ 3 ] Ambos")
    print("[ Enter ] No guardar")

    try:
        choice = input("> ").strip()
    except KeyboardInterrupt:
        print("\nNo se guardó ningún archivo.")
        return

    if choice == "":
        print("No se guardó ningún archivo.")
        return

    csv_path_auto, txt_path_auto = auto_filenames()

    if choice == "1":
        save_as_csv(csv_path_auto, entries)
        print(f"✅ CSV guardado en: {csv_path_auto}")
    elif choice == "2":
        save_as_txt(txt_path_auto, entries)
        print(f"✅ TXT guardado en: {txt_path_auto}")
    elif choice == "3":
        save_as_csv(csv_path_auto, entries)
        save_as_txt(txt_path_auto, entries)
        print(f"✅ CSV guardado en: {csv_path_auto}")
        print(f"✅ TXT guardado en: {txt_path_auto}")
    else:
        print("Opción no reconocida. No se guardó ningún archivo.")


# -------------------- CLI principal --------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analizador de vocabulario con traducción automática.",
        epilog=(
            "Ejemplos:\n"
            "  python vocab.py texto.txt\n"
            "  python vocab.py texto1.txt texto2.txt\n"
            '  python vocab.py "Das ist nur ein Test"\n'
            "  cat texto.txt | python vocab.py\n\n"
            "Opcional:\n"
            "  --exclude RUTA   Archivo con palabras a excluir (una por línea).\n"
            "                   Si no se pasa y existe 'ignore.txt' al lado del script, se usa.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "inputs",
        nargs="*",
        help="Archivos de texto y/o texto literal entre comillas."
    )

    parser.add_argument(
    "-l", "--lang",
    choices=SUPPORTED_LANGS,
    default=DEFAULT_LANG,
    help="Idioma del texto de entrada (default: de). Opciones: de, en, pt, it, es.",
    )

    parser.add_argument(
        "--exclude",
        metavar="RUTA",
        help="Archivo con palabras a excluir (una por línea)."
    )

    parser.add_argument(
        "--save",
        metavar="MODO_O_RUTA",
        help=(
            "Opciones:\n"
            "  csv / txt / both / all    → guarda en archivos automáticos.\n"
            "  RUTA                      → guarda en esa ruta (.csv o .txt).\n"
            "Si no se pasa --save, se pregunta al final."
        )
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Muestra qué API se usa para cada palabra."
    )

    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Cuenta palabras pero omite las llamadas a las APIs de traducción. Se fuerza si el idioma es 'es'."
    )

    return parser.parse_args()


def main():
    args = parse_args()

    lang = args.lang  # de, en, pt, it, es
    script_dir = Path(__file__).resolve().parent
    cache_path = script_dir / CACHE_FILENAME

    if lang == "es" and not args.no_translate:
        print("ℹ️ Idioma 'es' detectado: se omitirá la traducción automáticamente.")

    no_translate_mode = args.no_translate or (lang == "es")

    # 1) Leer texto (archivos, literal o stdin)
    text = read_text_from_inputs(args.inputs, lang)

    # 2) Cargar palabras ignoradas
    ignore_dict = load_ignore_words(script_dir, args.exclude, lang)

    # 3) Contar palabras
    words_data, total_tokens, considered_tokens = count_words(text, lang, ignore_dict)

    if not words_data:
        print("No se encontraron palabras (o todas fueron excluidas).")
        return

    # 4) Cargar cache
    cache = load_cache(cache_path)
    if lang not in cache:
        cache[lang] = {}
    lang_cache = cache[lang]

    if no_translate_mode:
        # Saltar traducciones y rellenar con marcador
        for info in words_data.values():
            info["meaning"] = "-"
    else:
        # 5) Traducir palabras únicas con barra de progreso
        #    words_data: norm -> {original, count}
        from tqdm import tqdm
        for norm, info in tqdm(words_data.items(), desc="Traduciendo", ncols=80):
            original_word = info["original"]
            meaning = get_translation(norm, original_word, lang, lang_cache, debug=args.debug)
            info["meaning"] = meaning

        # Guardar cache actualizado solo si hubo traducciones
        save_cache(cache_path, cache)

    # 6) Preparar lista ordenada para salida
    entries = []
    for norm, info in words_data.items():
        entries.append((info["original"], info["count"], info["meaning"]))

    # ordenar por frecuencia desc, luego alfabético por palabra original
    entries.sort(key=lambda x: (-x[1], x[0].lower()))

    # 7) Mostrar tabla en terminal
    print()
    print(format_table(entries))
    print()
    print(f"Total de tokens en el texto:        {total_tokens}")
    print(f"Tokens considerados (sin ignorados): {considered_tokens}")
    print(f"Palabras únicas tras ignorar:       {len(entries)}")

    # 8) Guardado: automático (--save) o interactivo
    if args.save:
        handle_save_option(args.save, entries)
    else:
        interactive_save(entries)


if __name__ == "__main__":
    main()
