def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)

def get_bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "Underweight (體重過輕)"
    elif bmi < 24.0:
        return "Normal weight (正常範圍)"
    elif bmi < 27.0:
        return "Overweight (過重)"
    else:
        return "Obese (肥胖)"

def main():
    print("=== BMI 計算器 ===")
    try:
        height = float(input("請輸入身高 (公分 cm): "))
        weight = float(input("請輸入體重 (公斤 kg): "))
        bmi = calculate_bmi(height, weight)
        category = get_bmi_category(bmi)
        print(f"您的 BMI 為: {bmi:.2f}")
        print(f"健康狀態: {category}")
    except ValueError:
        print("輸入錯誤，請輸入有效的數字。")

if __name__ == "__main__":
    main()
