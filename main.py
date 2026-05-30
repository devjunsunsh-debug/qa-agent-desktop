from agent import (
    get_pbi, 
    generate_test_cases, 
    create_test_case_in_azure, 
    agregar_tag_pbi,
    buscar_tc_manual,     
    sobreescribir_tc
)

def main():
    print("=" * 55)
    print("  QA Agent - Generador de Test Cases")
    print("=" * 55)

    pbi_id = input("\nIngresa el ID del PBI: ").strip()

    print(f"\nObteniendo PBI {pbi_id} de Azure DevOps...")
    pbi = get_pbi(pbi_id)

    if not pbi:
        print("No se pudo obtener el PBI. Revisa tus credenciales.")
        return

    completitud = pbi["completitud"]
    print(f"PBI encontrado: {pbi['titulo']}")
    print(f"Completitud: {completitud['nivel'].upper()}")

    if completitud["necesita_tag"]:
        print(f"\nFaltan: {', '.join(completitud['campos_faltantes'])}")
        print("Agregando tag 'AC-Pendiente' al PBI...")
        agregar_tag_pbi(pbi_id, "AC-Pendiente")

    if completitud["nivel"] == "incompleto":
        print("\nEl PBI no tiene suficiente informacion para generar test cases de calidad.")
        continuar = input("Deseas intentarlo de todas formas solo con el titulo? (s/n): ").strip().lower()
        if continuar != "s":
            print("Operacion cancelada. El tag 'AC-Pendiente' ya fue agregado al PBI.")
            return

    elif completitud["nivel"] == "parcial":
        print("\nEl PBI tiene informacion parcial. Los test cases pueden ser basicos.")
        continuar = input("Deseas continuar? (s/n): ").strip().lower()
        if continuar != "s":
            print("Operacion cancelada. El tag 'AC-Pendiente' ya fue agregado al PBI.")
            return

    print(f"\nGenerando test cases con IA...")
    resultado = generate_test_cases(pbi)

    if not resultado:
        print("No se pudieron generar los test cases.")
        return

    if resultado.get("advertencia"):
        print(f"\nNota: {resultado['advertencia']}")

    test_cases = resultado["test_cases"]
    print(f"\nSe generaron {len(test_cases)} test cases:")
    for i, tc in enumerate(test_cases, 1):
        print(f"  {i}. {tc['titulo']} ({len(tc['pasos'])} pasos)")

    confirmar = input("\nCrear estos test cases en Azure DevOps? (s/n): ").strip().lower()
    if confirmar != "s":
        print("Operacion cancelada.")
        return

    print("\nCreando test cases en Azure DevOps...")
    ids_creados = []
    for i, tc in enumerate(test_cases):
        # enumerate() nos da el índice i (0, 1, 2...)
        # es_primero=True solo cuando i==0, es decir el primer TC
        # En los siguientes, es_primero=False y el flujo es normal
        tc_id, error = create_test_case_in_azure(
            pbi, 
            tc, 
            es_primero=(i == 0)
        )
        if tc_id:
            ids_creados.append(tc_id)
        elif error:
            print(f"  ⚠️ Error en '{tc['titulo']}': {error}")

    print(f"\n{'=' * 55}")
    print(f"Proceso completado.")
    print(f"{len(ids_creados)} de {len(test_cases)} test cases creados.")
    if completitud["necesita_tag"]:
        print(f"Tag 'AC-Pendiente' agregado al PBI.")
    print(f"{'=' * 55}")

if __name__ == "__main__":
    main()