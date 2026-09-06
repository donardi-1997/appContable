from decimal import Decimal, InvalidOperation


def validate_invoice_data(invoice_data: dict) -> list[str]:
    errors: list[str] = []

    required_fields = [
        "invoice_number",
        "prefix",
        "customer_name",
        "items",
        "subtotal",
        "tax_total",
        "total",
    ]
    for field_name in required_fields:
        if field_name not in invoice_data or invoice_data[field_name] is None:
            errors.append(f"El campo '{field_name}' es obligatorio")

    if "items" in invoice_data:
        items = invoice_data["items"]
        if not isinstance(items, list) or len(items) == 0:
            errors.append("Debe incluir al menos un ítem en la factura")
        else:
            for i, item in enumerate(items):
                item_errors = validate_item(item, i + 1)
                errors.extend(item_errors)

    for field_name in ["subtotal", "tax_total", "total"]:
        if field_name in invoice_data and invoice_data[field_name] is not None:
            try:
                val = Decimal(str(invoice_data[field_name]))
                if val < 0:
                    errors.append(f"'{field_name}' no puede ser negativo")
            except (InvalidOperation, ValueError):
                errors.append(f"'{field_name}' no es un valor numérico válido")

    return errors


def validate_item(item: dict, index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"Ítem {index}: "

    required = ["product_name", "quantity", "unit_price", "subtotal", "tax_rate", "tax_amount"]
    for field_name in required:
        if field_name not in item or item[field_name] is None:
            errors.append(f"{prefix}El campo '{field_name}' es obligatorio")

    for field_name in ["quantity", "unit_price", "subtotal", "tax_rate", "tax_amount"]:
        if field_name in item and item[field_name] is not None:
            try:
                val = Decimal(str(item[field_name]))
                if val < 0:
                    errors.append(f"{prefix}'{field_name}' no puede ser negativo")
            except (InvalidOperation, ValueError):
                errors.append(f"{prefix}'{field_name}' no es un valor numérico válido")

    if "subtotal" in item and "quantity" in item and "unit_price" in item:
        try:
            expected = Decimal(str(item["quantity"])) * Decimal(str(item["unit_price"]))
            actual = Decimal(str(item["subtotal"]))
            if expected != actual:
                errors.append(
                    f"{prefix}El subtotal ({actual}) no coincide "
                    f"con cantidad × precio unitario ({expected})"
                )
        except (InvalidOperation, ValueError):
            pass

    return errors


def validate_company_info(company_info: dict) -> list[str]:
    errors: list[str] = []

    required = ["company_name", "nit"]
    for field_name in required:
        if field_name not in company_info or not company_info.get(field_name):
            errors.append(f"El campo '{field_name}' de la empresa es obligatorio")

    if company_info.get("nit"):
        nit = str(company_info["nit"]).strip()
        if not nit.isdigit() and not all(c.isdigit() or c == "-" for c in nit):
            errors.append("El NIT contiene caracteres no válidos")

    if company_info.get("email"):
        email = str(company_info["email"])
        if "@" not in email or "." not in email:
            errors.append("El email de la empresa no es válido")

    return errors


def validate_resolution(resolution: dict) -> list[str]:
    errors: list[str] = []

    required = ["resolution_number", "resolution_prefix", "resolution_from", "resolution_to"]
    for field_name in required:
        if field_name not in resolution or not resolution.get(field_name):
            errors.append(f"El campo '{field_name}' es obligatorio")

    if resolution.get("resolution_from") and resolution.get("resolution_to"):
        try:
            from_num = int(resolution["resolution_from"])
            to_num = int(resolution["resolution_to"])
            if from_num >= to_num:
                errors.append("El rango de numeración 'desde' debe ser menor que 'hasta'")
        except (ValueError, TypeError):
            errors.append("El rango de numeración debe ser numérico")

    return errors


def validate_tax_totals(
    items: list,
    subtotal: Decimal | float | str,
    tax_total: Decimal | float | str,
    total: Decimal | float | str,
) -> list[str]:
    errors: list[str] = []

    try:
        subtotal_dec = Decimal(str(subtotal))
        tax_total_dec = Decimal(str(tax_total))
        total_dec = Decimal(str(total))
    except (InvalidOperation, ValueError, TypeError):
        errors.append("Los valores de totales no son numéricos válidos")
        return errors

    items_subtotal = Decimal("0")
    items_tax = Decimal("0")

    for i, item in enumerate(items):
        try:
            item_sub = Decimal(str(item.get("subtotal", 0)))
            item_tax = Decimal(str(item.get("tax_amount", 0)))
            items_subtotal += item_sub
            items_tax += item_tax
        except (InvalidOperation, ValueError, TypeError):
            errors.append(f"Ítem {i + 1}: valores numéricos inválidos")

    if items_subtotal != subtotal_dec:
        errors.append(
            f"La suma de subtotales de ítems ({items_subtotal}) "
            f"no coincide con el subtotal de la factura ({subtotal_dec})"
        )

    if items_tax != tax_total_dec:
        errors.append(
            f"La suma de impuestos de ítems ({items_tax}) "
            f"no coincide con el impuesto total ({tax_total_dec})"
        )

    expected_total = subtotal_dec + tax_total_dec
    if expected_total != total_dec:
        errors.append(
            f"El total ({total_dec}) no coincide con "
            f"subtotal + impuestos ({expected_total})"
        )

    return errors
