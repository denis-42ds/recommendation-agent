from pathlib import Path

import pandas as pd

path = Path("docs/source-materials/Датасет_Рекомендации_ЛК_v5.xlsx")

sheets = [
    "README",
    "Каталог",
    "Текущий_блок",
    "Протокол_проверки",
]

for sheet in sheets:
    df = pd.read_excel(
        path,
        sheet_name=sheet,
        header=None,
        engine="openpyxl",
        nrows=20,
    )

    print(f"\n{'=' * 20} {sheet} {'=' * 20}")
    print(df.to_string(index=False, header=False))
