"""ISO 4217 currencies offered out of the box: (code, name, symbol, minor units, active by default).

The ones a US or European company most often buys in start active; the rest can be switched on in
Settings > Currencies, and any other code can be added there.
"""

STANDARD_CURRENCIES: tuple[tuple[str, str, str, int, bool], ...] = (
    ("USD", "US Dollar", "$", 2, True),
    ("EUR", "Euro", "€", 2, True),
    ("GBP", "Pound Sterling", "£", 2, True),
    ("CAD", "Canadian Dollar", "CA$", 2, True),
    ("CHF", "Swiss Franc", "CHF", 2, True),
    ("SEK", "Swedish Krona", "kr", 2, True),
    ("NOK", "Norwegian Krone", "kr", 2, True),
    ("DKK", "Danish Krone", "kr", 2, True),
    ("PLN", "Polish Zloty", "zł", 2, True),
    ("CZK", "Czech Koruna", "Kč", 2, False),
    ("HUF", "Hungarian Forint", "Ft", 2, False),
    ("RON", "Romanian Leu", "lei", 2, False),
    ("BGN", "Bulgarian Lev", "лв", 2, False),
    ("ISK", "Icelandic Krona", "kr", 0, False),
    ("TRY", "Turkish Lira", "₺", 2, False),
    ("AUD", "Australian Dollar", "A$", 2, False),
    ("NZD", "New Zealand Dollar", "NZ$", 2, False),
    ("MXN", "Mexican Peso", "MX$", 2, False),
    ("BRL", "Brazilian Real", "R$", 2, False),
    ("JPY", "Japanese Yen", "¥", 0, False),
    ("CNY", "Chinese Yuan", "¥", 2, False),
    ("HKD", "Hong Kong Dollar", "HK$", 2, False),
    ("SGD", "Singapore Dollar", "S$", 2, False),
    ("KRW", "South Korean Won", "₩", 0, False),
    ("INR", "Indian Rupee", "₹", 2, False),
    ("ZAR", "South African Rand", "R", 2, False),
    ("AED", "UAE Dirham", "AED", 2, False),
    ("SAR", "Saudi Riyal", "SAR", 2, False),
    ("BHD", "Bahraini Dinar", "BHD", 3, False),
    ("KWD", "Kuwaiti Dinar", "KWD", 3, False),
)
