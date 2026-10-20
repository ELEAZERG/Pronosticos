"""Motor de cálculo: promedios, mediana, moda, probabilidades y margen de seguridad."""
import math
from collections import Counter
from statistics import median, pvariance

SAFE_P = 0.85      # probabilidad mínima para marcar "segura"
SAFE_HIT = 0.80    # frecuencia real mínima en la muestra
MIN_N = 10         # partidos mínimos


def weights(n, half_life=5):
    """Pesos exponenciales: el último partido (índice n-1) pesa más."""
    return [0.5 ** ((n - 1 - i) / half_life) for i in range(n)]


def wmean(xs, half_life=5):
    if not xs:
        return 0.0
    w = weights(len(xs), half_life)
    return sum(x * wi for x, wi in zip(xs, w)) / sum(w)


def mode(xs):
    if not xs:
        return None
    c = Counter(xs)
    top = max(c.values())
    return min(k for k, v in c.items() if v == top)


def stats(xs):
    return {"n": len(xs), "promedio": round(sum(xs) / len(xs), 2) if xs else 0,
            "ponderado": round(wmean(xs), 2), "mediana": median(xs) if xs else 0,
            "moda": mode(xs)}


# ---------- distribuciones ----------
def poisson_pmf(k, lam):
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1)) if lam > 0 else float(k == 0)


def poisson_cdf(k, lam):
    return sum(poisson_pmf(i, lam) for i in range(int(k) + 1))


def nb_cdf(k, mean, var):
    """Binomial negativa (sobredispersión). Si var <= mean cae a Poisson."""
    if var <= mean * 1.02:
        return poisson_cdf(k, mean)
    p = mean / var
    r = mean * p / (1 - p)
    tot = 0.0
    for i in range(int(k) + 1):
        tot += math.exp(math.lgamma(i + r) - math.lgamma(r) - math.lgamma(i + 1)
                        + r * math.log(p) + i * math.log(1 - p))
    return min(tot, 1.0)


def normal_cdf(x, mu, sigma):
    return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))


def p_over(line, mean, kind="poisson", var=None, sigma=None):
    """P(total > línea). Líneas .5, así que over = total >= floor(línea)+1."""
    if kind == "poisson":
        return 1 - poisson_cdf(math.floor(line), mean)
    if kind == "nbinom":
        return 1 - nb_cdf(math.floor(line), mean, var if var else mean)
    return 1 - normal_cdf(line, mean, sigma)


# ---------- goles esperados ----------
def expected_goals(gf_team, ga_rival, league_avg):
    """λ = (ataque / prom_liga) × (defensa rival / prom_liga) × prom_liga."""
    if league_avg <= 0:
        return (gf_team + ga_rival) / 2
    return (gf_team / league_avg) * (ga_rival / league_avg) * league_avg


# ---------- empírico y mezcla ----------
def hit_rate(xs, line, over=True):
    if not xs:
        return 0.0
    return sum((x > line) if over else (x < line) for x in xs) / len(xs)


def blend(p_model, p_emp, n):
    """60% modelo / 40% frecuencia real; con poca muestra pesa más el modelo."""
    w_emp = 0.4 * min(1.0, n / MIN_N)
    return (1 - w_emp) * p_model + w_emp * p_emp


def analyze_market(series_a, series_b, lam, lines, kind="poisson"):
    """series_a/b: totales por partido de cada equipo. lam: total esperado."""
    allx = list(series_a) + list(series_b)
    n = min(len(series_a), len(series_b))
    var = pvariance(allx) if len(allx) > 1 else lam
    rows = []
    for line in lines:
        for over in (True, False):
            pm = p_over(line, lam, kind, var=var)
            pm = pm if over else 1 - pm
            emp_a = hit_rate(series_a, line, over)
            emp_b = hit_rate(series_b, line, over)
            emp = (emp_a + emp_b) / 2
            p = blend(pm, emp, n)
            safe = p >= SAFE_P and min(emp_a, emp_b) >= SAFE_HIT and n >= MIN_N
            rows.append({"Línea": f"{'Over' if over else 'Under'} {line}",
                         "Prob. final": round(p * 100, 1),
                         "Modelo": round(pm * 100, 1),
                         "Real equipo A": round(emp_a * 100),
                         "Real equipo B": round(emp_b * 100),
                         "Segura": "✅" if safe else ""})
    return rows


def value(p, odds):
    """Ventaja = prob. del modelo − prob. implícita de la cuota (decimal)."""
    return p - 1 / odds
