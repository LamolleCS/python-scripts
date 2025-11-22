#!/home/stolz/prog/python/python-scripts/.venv/bin/python3
# -*- coding: utf-8 -*-

"""
sortrd.py - Sort & Remove Duplicates
Elimina duplicados y ordena alfabéticamente las palabras de un archivo de texto.

Uso:
    sortrd.py archivo.txt [--output salida.txt]

Si no se especifica --output, sobrescribe el archivo original.
"""

import argparse
import sys
from pathlib import Path


def process_file(input_path: Path, output_path: Path = None):
    """
    Lee un archivo, elimina duplicados, líneas vacías y ordena alfabéticamente.
    
    Args:
        input_path: Ruta del archivo a procesar
        output_path: Ruta del archivo de salida (None = sobrescribir original)
    """
    if not input_path.exists():
        print(f"❌ Error: El archivo '{input_path}' no existe.")
        sys.exit(1)
    
    try:
        # Leer archivo
        with input_path.open('r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Procesar: eliminar duplicados y líneas vacías
        unique_words = set()
        for line in lines:
            word = line.strip()
            if word:  # Solo agregar si no está vacía
                unique_words.add(word)
        
        # Ordenar alfabéticamente (case-insensitive)
        sorted_words = sorted(unique_words, key=str.lower)
        
        # Determinar archivo de salida
        if output_path is None:
            output_path = input_path
        
        # Escribir resultado
        with output_path.open('w', encoding='utf-8') as f:
            for word in sorted_words:
                f.write(word + '\n')
        
        # Mostrar resumen
        original_lines = len(lines)
        final_lines = len(sorted_words)
        duplicates = original_lines - final_lines
        
        print(f"✅ Procesamiento completado:")
        print(f"   Líneas originales: {original_lines}")
        print(f"   Líneas finales:    {final_lines}")
        print(f"   Duplicados/vacías: {duplicates}")
        print(f"   Archivo guardado:  {output_path}")
        
    except UnicodeDecodeError:
        print(f"❌ Error: No se pudo leer '{input_path}' como UTF-8.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Elimina duplicados y ordena alfabéticamente un archivo de texto.",
        epilog="Ejemplo: sortrd.py palabras.txt --output palabras_limpias.txt"
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='Archivo de entrada (.txt)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Archivo de salida (si no se especifica, sobrescribe el original)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None
    
    process_file(input_path, output_path)


if __name__ == "__main__":
    main()
