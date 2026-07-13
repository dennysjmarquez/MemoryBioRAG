import json
import os

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cases_file = os.path.join(base_dir, "scripts", "casos_qa.jsonl")
    
    if not os.path.exists(cases_file):
        print(f"Error: Cases file not found at {cases_file}")
        return
        
    # Read existing cases
    existing_cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_cases.append(json.loads(line))
                
    print(f"Read {len(existing_cases)} existing cases.")
    
    # Check if we already appended retadores to avoid duplicates
    retadores_exist = any(c.get("notes") == "Challenging negative control for short tokens" for c in existing_cases)
    if retadores_exist:
        print("Challenging negatives already exist. Removing them to regenerate.")
        existing_cases = [c for c in existing_cases if c.get("notes") != "Challenging negative control for short tokens"]
        
    # New challenging negative queries
    new_negatives_queries = [
        "paraguas cv",
        "chocolate ia",
        "jirafa db",
        "velero v6",
        "bufanda v8",
        "espejo v18",
        "balon fn",
        "zapato xp",
        "camisa qt",
        "sombrero fk",
        "biorag paraguas",
        "sistema jirafa",
        "archivo velero",
        "datos bufanda",
        "conexion chocolate",
        "guardar espejo",
        "buscar linterna",
        "servidor almohada",
        "cliente piscina",
        "codigo orquesta",
        "ia de chocolate",
        "cv de jirafa",
        "db de velero",
        "v8 de bufanda",
        "v18 de espejo",
        "fk de martillo",
        "xp de zapato",
        "qt de camisa",
        "v6 de paraguas",
        "biorag de velero"
    ]
    
    next_id = max(int(c["id"]) for c in existing_cases) + 1
    
    new_cases = []
    for query in new_negatives_queries:
        case = {
            "id": f"{next_id:04d}",
            "categoria": "negativo",
            "query": query,
            "concepto_esperado": None,
            "deep": True,
            "notes": "Challenging negative control for short tokens"
        }
        new_cases.append(case)
        next_id += 1
        
    all_cases = existing_cases + new_cases
    
    with open(cases_file, "w", encoding="utf-8") as f:
        for case in all_cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
            
    print(f"Successfully appended {len(new_cases)} challenging negatives. Total cases now: {len(all_cases)}")

if __name__ == "__main__":
    main()
