from __future__ import annotations

from datetime import date


def gregorian_to_jalali(value: date) -> str:
    """Convert a Gregorian date to the provider-standard YYYY-MM-DD format."""

    year, month, day = value.year, value.month, value.day
    month_days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    adjusted_year = year + 1 if month > 2 else year
    days = (
        355_666
        + (365 * year)
        + ((adjusted_year + 3) // 4)
        - ((adjusted_year + 99) // 100)
        + ((adjusted_year + 399) // 400)
        + day
        + sum(month_days[: month - 1])
    )
    jalali_year = -1595 + (33 * (days // 12_053))
    days %= 12_053
    jalali_year += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jalali_year += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jalali_month = 1 + (days // 31)
        jalali_day = 1 + (days % 31)
    else:
        jalali_month = 7 + ((days - 186) // 30)
        jalali_day = 1 + ((days - 186) % 30)
    return f"{jalali_year:04d}-{jalali_month:02d}-{jalali_day:02d}"
