import json, os

archivos_json_vacio = ["estado.json", "cedulas_procesadas.json", "estado_expedientes.json"]

for nombre in archivos_json_vacio:
    if os.path.isfile(nombre):
        contenido = {"cedulas": []} if nombre == "estado.json" else {}
        with open(nombre, "w", encoding="utf-8") as f:
            json.dump(contenido, f, ensure_ascii=False, indent=2)
        print(f"  ✓ {nombre} vaciado")
    else:
        print(f"  - {nombre} no existía, no hace falta nada")

print("\nListo. Los tres registros quedaron limpios.")
