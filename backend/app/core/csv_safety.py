FORMULA_TRIGGER_CHARACTERS = ("=", "+", "-", "@", "\t", "\r")


def neutralize_formula(value: str) -> str:
    """Stop a text cell from being executed as a formula when the CSV is opened in a spreadsheet.

    Excel and Sheets treat a cell starting with = + - @ (or a tab/CR) as a formula, so user-entered
    text such as a product name could run attacker-chosen formulas. A leading apostrophe makes the
    application show the text literally. Apply only to free-text columns, not to numbers.
    """
    if value.startswith(FORMULA_TRIGGER_CHARACTERS):
        return f"'{value}"
    return value
