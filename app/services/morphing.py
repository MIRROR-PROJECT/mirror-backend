def apply_morphing_logic(available_minutes: int, student_type: str):
    """
    기획된 3가지 유형에 따른 시간 분배 가중치 적용
    """
    # 표준 비율 (Mirroring): 개념 30%, 문제 50%, 복습 20%
    standard = {"CONCEPT": 0.3, "PRACTICE": 0.5, "REVIEW": 0.2}
    
    # 유형별 변형 (Morphing) 가중치
    weights = {
        "SPRINTER": {"CONCEPT": 1.2, "PRACTICE": 0.8, "REVIEW": 1.0}, # 실수 방지용 브레이크
        "DIVER":    {"CONCEPT": 0.8, "PRACTICE": 0.7, "REVIEW": 1.5}, # 타임어택 강제
        "FIGHTER":  {"CONCEPT": 1.0, "PRACTICE": 1.3, "REVIEW": 0.7}  # 짧고 굵은 문제풀이
    }
    
    selected_weight = weights.get(student_type, weights["SPRINTER"])
    
    # 가중치 적용 및 계산
    tasks = []
    total_factor = sum(standard[k] * selected_weight[k] for k in standard)
    
    for key in standard:
        ratio = (standard[key] * selected_weight[key]) / total_factor
        assigned = int(available_minutes * ratio)
        tasks.append({
            "category": key,
            "assigned_minutes": assigned,
            "title": f"오늘의 {key} 집중 학습"
        })
        
    return tasks