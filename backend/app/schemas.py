from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    sku: str | None = None
    unit: str = "unidad"
    price: Decimal = Field(default=0, ge=0)
    cost_price: Decimal = Field(default=0, ge=0)
    stock: Decimal = Field(default=0, ge=0)
    minimum_stock: Decimal = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=160,
    )
    sku: str | None = Field(
        default=None,
        max_length=60,
    )
    unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    price: Decimal | None = Field(
        default=None,
        ge=0,
    )
    cost_price: Decimal | None = Field(
        default=None,
        ge=0,
    )
    minimum_stock: Decimal | None = Field(
        default=None,
        ge=0,
    )


class ProductRead(ProductCreate):
    id: int
    active: bool
    model_config = ConfigDict(from_attributes=True)


class SupplierCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=160,
    )

    document: str | None = Field(
        default=None,
        max_length=60,
    )

    phone: str | None = Field(
        default=None,
        max_length=40,
    )

    email: str | None = Field(
        default=None,
        max_length=160,
    )

    address: str | None = Field(
        default=None,
        max_length=250,
    )

    contact_name: str | None = Field(
        default=None,
        max_length=160,
    )

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )


class SupplierUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=160,
    )

    document: str | None = Field(
        default=None,
        max_length=60,
    )

    phone: str | None = Field(
        default=None,
        max_length=40,
    )

    email: str | None = Field(
        default=None,
        max_length=160,
    )

    address: str | None = Field(
        default=None,
        max_length=250,
    )

    contact_name: str | None = Field(
        default=None,
        max_length=160,
    )

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    active: bool | None = None


class PurchaseItemCreate(BaseModel):
    product_id: int

    quantity: Decimal = Field(
        gt=0
    )

    unit_cost: Decimal = Field(
        ge=0
    )


class PurchaseCreate(BaseModel):
    supplier_id: int

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )

    items: list[PurchaseItemCreate] = Field(
        min_length=1
    )


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)


class SaleCreate(BaseModel):
    customer_name: str = "Consumidor final"
    payment_method: str = "efectivo"
    items: list[SaleItemCreate] = Field(min_length=1)



class OpenAccountCreate(BaseModel):
    account_type: str = Field(
        default="MESA",
        min_length=2,
        max_length=30,
    )

    label: str = Field(
        min_length=1,
        max_length=80,
    )

    zone: str | None = Field(
        default=None,
        max_length=80,
    )

    customer_name: str = Field(
        default="Consumidor final",
        max_length=160,
    )


class OpenAccountItemCreate(BaseModel):
    product_id: int

    quantity: Decimal = Field(
        gt=0
    )


class OpenAccountCloseCreate(BaseModel):
    payment_method: str = Field(
        default="efectivo",
        min_length=2,
        max_length=30,
    )


class SaleCancelCreate(BaseModel):
    reason: str = Field(
        min_length=4,
        max_length=500,
    )


class ExpenseCreate(BaseModel):
    concept: str = Field(min_length=2, max_length=160)
    provider: str | None = None
    value: Decimal = Field(gt=0)
    payment_method: str = "efectivo"
    notes: str | None = None

class InventoryAdjustmentCreate(BaseModel):
    product_id: int
    movement_type: str
    quantity: Decimal = Field(gt=0)
    notes: str | None = None


class CashRegisterOpenCreate(BaseModel):
    opening_amount: Decimal = Field(ge=0)


class CashRegisterCloseCreate(BaseModel):
    closing_amount: Decimal = Field(ge=0)
    notes: str | None = Field(
        default=None,
        max_length=500,
    )




class LoginCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=80,
    )

    password: str = Field(
        min_length=6,
        max_length=200,
    )


class UserCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=80,
    )

    full_name: str = Field(
        min_length=2,
        max_length=160,
    )

    password: str = Field(
        min_length=6,
        max_length=200,
    )

    role: str = "VENDEDOR"


class UserActiveUpdate(BaseModel):
    active: bool


class QRResolveRequest(BaseModel):
    qr_value: str = Field(min_length=1, max_length=200)


class ProductImageUpdate(BaseModel):
    image_url: str | None = Field(
        default=None,
        max_length=500,
    )


class TaxConfigUpdate(BaseModel):
    tax_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100)
    tax_type: str = Field(default="IVA", max_length=20)


class CompanyInfoCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    nit: str = Field(min_length=3, max_length=30)
    dv: str | None = Field(default=None, max_length=5)
    address: str | None = Field(default=None, max_length=250)
    municipality: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    country: str = Field(default="CO", max_length=5)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=160)
    regime: str | None = Field(default=None, max_length=50)
    responsibilities: str | None = Field(default=None)
    resolution_number: str | None = Field(default=None, max_length=80)
    resolution_prefix: str | None = Field(default=None, max_length=20)
    resolution_range_from: int | None = None
    resolution_range_to: int | None = None
    resolution_date: str | None = Field(default=None, max_length=30)
    software_id: str | None = Field(default=None, max_length=80)
    software_secret: str | None = Field(default=None, max_length=200)
    certificate_path: str | None = Field(default=None, max_length=500)


class CompanyInfoUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    nit: str | None = Field(default=None, min_length=3, max_length=30)
    dv: str | None = Field(default=None, max_length=5)
    address: str | None = Field(default=None, max_length=250)
    municipality: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=5)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=160)
    regime: str | None = Field(default=None, max_length=50)
    responsibilities: str | None = None
    resolution_number: str | None = Field(default=None, max_length=80)
    resolution_prefix: str | None = Field(default=None, max_length=20)
    resolution_range_from: int | None = None
    resolution_range_to: int | None = None
    resolution_date: str | None = Field(default=None, max_length=30)
    software_id: str | None = Field(default=None, max_length=80)
    software_secret: str | None = Field(default=None, max_length=200)
    certificate_path: str | None = Field(default=None, max_length=500)


class ElectronicInvoiceCreate(BaseModel):
    sale_id: int
    customer_name: str = Field(default="Consumidor final", max_length=160)
    customer_document_type: str | None = Field(default=None, max_length=10)
    customer_document_number: str | None = Field(default=None, max_length=30)
    customer_email: str | None = Field(default=None, max_length=160)
    customer_address: str | None = Field(default=None, max_length=250)
    customer_phone: str | None = Field(default=None, max_length=40)


class ElectronicInvoiceFilter(BaseModel):
    status: str | None = None
    customer_name: str | None = None
    invoice_number: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
