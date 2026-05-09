from datetime import datetime


def formatar_reais(valor):
    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def converter_valor_brasileiro(valor_str):
    if not valor_str:
        return 0

    try:
        valor_str = str(valor_str).replace("R$", "").strip()
        valor_str = valor_str.replace(".", "").replace(",", ".")
        return float(valor_str)
    except:
        return 0


def converter_data_brasileira(data_str):
    if not data_str:
        return None

    formatos = ["%d/%m/%Y", "%Y-%m-%d"]

    for formato in formatos:
        try:
            return datetime.strptime(data_str, formato)
        except:
            pass

    return None
