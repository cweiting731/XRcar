import sympy as sp

# PWM / ADC 值
x_vals = [300, 507, 1527, 2013, 4095]

# 原本的 f(x) 是 duration / circleCounts
# 轉換為每秒轉幾圈，即 circleCounts / duration = 1 / f(x)
f_vals = [1.119, 0.725, 0.529, 0.508, 0.482]
y_vals = [1 / v for v in f_vals]  # 每秒轉幾圈
print("y:", y_vals)


x = sp.Symbol('x')

# 牛頓插值法 (divided differences)
def divided_diff(x_vals, y_vals):
    n = len(x_vals)
    coef = [y for y in y_vals]
    for j in range(1, n):
        for i in range(n - 1, j - 1, -1):
            coef[i] = (coef[i] - coef[i - 1]) / (x_vals[i] - x_vals[i - j])
    return coef

coef = divided_diff(x_vals, y_vals)

# 建立牛頓插值多項式
poly = coef[0]
for i in range(1, len(coef)):
    term = coef[i]
    for j in range(i):
        term *= (x - x_vals[j])
    poly += term

poly_simplified = sp.simplify(poly)

print("circle/s:")
print(poly_simplified)
print("\nLaTeX 輸出:")
print(sp.latex(poly_simplified))