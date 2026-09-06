from datetime import datetime, timedelta
import base64
import hashlib
import hmac
import io
import os
import secrets
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, UploadFile, File, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

import qrcode
import jwt

from .db import Base, engine, get_db
from .models import (
    CashRegisterSession, CompanyInfo, ElectronicInvoice,
    Expense, InventoryHistory, InventoryMovement, Product, ProductQR,
    Sale, SaleItem, User, UserAuditLog, SystemAuditLog,
    OpenAccount, OpenAccountItem, Supplier, Purchase, PurchaseItem,
)
from .schemas import (
    CashRegisterCloseCreate,
    CashRegisterOpenCreate,
    CompanyInfoCreate,
    CompanyInfoUpdate,
    ElectronicInvoiceCreate,
    ElectronicInvoiceFilter,
    ExpenseCreate,
    InventoryAdjustmentCreate,
    LoginCreate,
    ProductCreate,
    ProductImageUpdate,
    ProductUpdate,
    QRResolveRequest,
    SaleCreate,
    ProductRead,
    TaxConfigUpdate,
    UserActiveUpdate,
    UserCreate,

    OpenAccountCreate,
    OpenAccountItemCreate,
    OpenAccountCloseCreate,

    SaleCancelCreate,
    SupplierCreate,
    SupplierUpdate,
    PurchaseCreate,
)
from .services.file_storage import (
    delete_image,
    get_image_full_path,
    get_image_url,
    save_image,
    validate_image,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIMES,
    MAX_IMAGE_SIZE,
)
from .services.invoice_provider import InvoiceItemData
from .services.mock_provider import MockElectronicInvoiceProvider

Base.metadata.create_all(bind=engine)
app = FastAPI(title="La Patrona VIP API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/app.js", include_in_schema=False)
def serve_app_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"), media_type="application/javascript")


@app.get("/styles.css", include_in_schema=False)
def serve_styles_css():
    return FileResponse(str(FRONTEND_DIR / "styles.css"), media_type="text/css")

invoice_provider_type = os.getenv(
    "ELECTRONIC_INVOICE_PROVIDER", "mock"
).strip().lower()


def _build_invoice_provider():
    if invoice_provider_type == "dian":
        try:
            from .services.dian.config import DIANConfig
            from .services.dian.provider import DianElectronicInvoiceProvider
            config = DIANConfig()
            return DianElectronicInvoiceProvider(config=config)
        except Exception:
            return MockElectronicInvoiceProvider()
    return MockElectronicInvoiceProvider()


invoice_provider = _build_invoice_provider()


ADMIN_API_KEY = os.getenv(
    "ADMIN_API_KEY",
    "",
).strip()

AUTH_SECRET = (
    os.getenv(
        "AUTH_SECRET",
        "",
    ).strip()
    or ADMIN_API_KEY
)

AUTH_ALGORITHM = "HS256"

AUTH_TOKEN_HOURS = 12

AUTH_COOKIE_NAME = "lp_session"

AUTH_COOKIE_MAX_AGE = (
    AUTH_TOKEN_HOURS
    * 60
    * 60
)


VALID_ROLES = {
    "ADMIN",
    "VENDEDOR",
}


# ============================================================
# PASSWORDS
# ============================================================

def hash_password(
    password: str,
) -> str:

    salt = secrets.token_bytes(16)

    iterations = 310_000

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )

    return (
        f"pbkdf2_sha256"
        f"${iterations}"
        f"${base64.b64encode(salt).decode('ascii')}"
        f"${base64.b64encode(digest).decode('ascii')}"
    )


def verify_password(
    password: str,
    encoded: str,
) -> bool:

    try:
        algorithm, iterations, salt_b64, hash_b64 = (
            encoded.split(
                "$",
                3,
            )
        )

        if algorithm != "pbkdf2_sha256":
            return False

        salt = base64.b64decode(
            salt_b64
        )

        expected = base64.b64decode(
            hash_b64
        )

        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )

        return hmac.compare_digest(
            actual,
            expected,
        )

    except Exception:
        return False


# ============================================================
# JWT
# ============================================================

def create_access_token(
    user: User,
) -> str:

    if not AUTH_SECRET:
        raise HTTPException(
            status_code=500,
            detail=(
                "AUTH_SECRET no está configurada "
                "en el servidor"
            ),
        )

    now = datetime.utcnow()

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": (
            now
            + timedelta(
                hours=AUTH_TOKEN_HOURS
            )
        ),
    }

    return jwt.encode(
        payload,
        AUTH_SECRET,
        algorithm=AUTH_ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> dict:

    if not AUTH_SECRET:
        raise HTTPException(
            status_code=500,
            detail=(
                "AUTH_SECRET no está configurada "
                "en el servidor"
            ),
        )

    try:
        return jwt.decode(
            token,
            AUTH_SECRET,
            algorithms=[
                AUTH_ALGORITHM
            ],
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="La sesión expiró",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Sesión inválida",
        )


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user(
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
    session_cookie: str | None = Cookie(
        default=None,
        alias=AUTH_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
) -> User:

    token = None

    # ----------------------------------------
    # Cookie HttpOnly
    # ----------------------------------------

    if session_cookie:
        token = session_cookie

    # ----------------------------------------
    # Bearer temporal para compatibilidad API
    # ----------------------------------------

    elif (
        authorization
        and authorization.startswith(
            "Bearer "
        )
    ):
        token = authorization[
            len("Bearer "):
        ].strip()


    if not token:
        raise HTTPException(
            status_code=401,
            detail="Debes iniciar sesión",
        )


    payload = decode_access_token(
        token
    )


    try:
        user_id = int(
            payload.get("sub")
        )

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Sesión inválida",
        )


    user = db.get(
        User,
        user_id,
    )


    if (
        not user
        or not user.active
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "Usuario inactivo "
                "o inexistente"
            ),
        )


    return user


# ============================================================
# ROLE CHECKS
# ============================================================

def require_roles(
    *roles: str,
):
    def dependency(
        user: User = Depends(
            get_current_user
        ),
    ) -> User:

        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=(
                    "No tienes permiso "
                    "para realizar esta acción"
                ),
            )

        return user

    return dependency


def require_admin(
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
    session_cookie: str | None = Cookie(
        default=None,
        alias=AUTH_COOKIE_NAME,
    ),
    x_admin_key: str | None = Header(
        default=None,
        alias="X-Admin-Key",
    ),
    db: Session = Depends(get_db),
) -> User | None:

    # ----------------------------------------
    # API key temporal / mantenimiento
    # ----------------------------------------

    if (
        ADMIN_API_KEY
        and x_admin_key
        and secrets.compare_digest(
            x_admin_key,
            ADMIN_API_KEY,
        )
    ):
        return None


    token = None


    # ----------------------------------------
    # Cookie HttpOnly
    # ----------------------------------------

    if session_cookie:
        token = session_cookie


    # ----------------------------------------
    # Bearer temporal
    # ----------------------------------------

    elif (
        authorization
        and authorization.startswith(
            "Bearer "
        )
    ):
        token = authorization[
            len("Bearer "):
        ].strip()


    if not token:
        raise HTTPException(
            status_code=403,
            detail=(
                "Permiso exclusivo "
                "de administrador"
            ),
        )


    payload = decode_access_token(
        token
    )


    try:
        user_id = int(
            payload.get("sub")
        )

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Sesión inválida",
        )


    user = db.get(
        User,
        user_id,
    )


    if (
        not user
        or not user.active
    ):
        raise HTTPException(
            status_code=401,
            detail="Usuario inválido",
        )


    if user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail=(
                "Permiso exclusivo "
                "de administrador"
            ),
        )


    return user


# ============================================================
# AUTH ENDPOINTS
# ============================================================

@app.post(
    "/api/auth/bootstrap-admin",
    status_code=status.HTTP_201_CREATED,
)
def bootstrap_admin(
    payload: UserCreate,
    x_admin_key: str | None = Header(
        default=None,
        alias="X-Admin-Key",
    ),
    db: Session = Depends(get_db),
):

    if (
        not ADMIN_API_KEY
        or not x_admin_key
        or not secrets.compare_digest(
            x_admin_key,
            ADMIN_API_KEY,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="Clave administrativa inválida",
        )

    existing_admin = db.scalars(
        select(User).where(
            User.role == "ADMIN"
        )
    ).first()

    if existing_admin:
        raise HTTPException(
            status_code=409,
            detail=(
                "Ya existe un administrador. "
                "Usa el módulo de usuarios."
            ),
        )

    username = (
        payload.username
        .strip()
        .lower()
    )

    existing = db.scalars(
        select(User).where(
            User.username == username
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="El usuario ya existe",
        )

    user = User(
        username=username,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(
            payload.password
        ),
        role="ADMIN",
        active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
    }


@app.post("/api/auth/login")
def login(
    payload: LoginCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):

    username = (
        payload.username
        .strip()
        .lower()
    )


    user = db.scalars(
        select(User).where(
            User.username == username
        )
    ).first()


    if (
        not user
        or not user.active
        or not verify_password(
            payload.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "Usuario o contraseña "
                "incorrectos"
            ),
        )


    user.last_login = datetime.utcnow()

    db.commit()


    token = create_access_token(
        user
    )

    is_https = request.headers.get("x-forwarded-proto", "").lower() == "https"

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,

        httponly=True,

        secure=is_https,

        samesite="lax",

        max_age=AUTH_COOKIE_MAX_AGE,

        path="/",
    )


    return {
        "authenticated": True,

        "expires_in_hours":
            AUTH_TOKEN_HOURS,

        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "active": user.active,
        },
    }



@app.post("/api/auth/logout")
def logout(
    response: Response,
):
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=False,
        samesite="lax",
    )

    return {
        "authenticated": False
    }


@app.get("/api/auth/me")
def auth_me(
    user: User = Depends(
        get_current_user
    ),
):

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
        "created_at": user.created_at,
        "last_login": user.last_login,
    }



def write_user_audit(
    db: Session,
    actor: User | None,
    target: User,
    action: str,
) -> None:

    log = UserAuditLog(
        actor_user_id=(
            actor.id
            if actor
            else None
        ),
        target_user_id=target.id,
        action=action,
        actor_name=(
            actor.full_name
            if actor
            else "Sistema"
        ),
        target_name=target.full_name,
        target_username=target.username,
        target_role=target.role,
    )

    db.add(log)



def write_system_audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    entity_name: str | None = None,
    description: str | None = None,
) -> None:

    log = SystemAuditLog(
        actor_user_id=(
            actor.id
            if actor
            else None
        ),
        actor_name=(
            actor.full_name
            if actor
            else "Sistema"
        ),
        actor_role=(
            actor.role
            if actor
            else None
        ),
        action=action,
        entity_type=entity_type,
        entity_id=(
            str(entity_id)
            if entity_id is not None
            else None
        ),
        entity_name=entity_name,
        description=description,
    )

    db.add(log)


# ============================================================
# USER ADMINISTRATION
# ============================================================


@app.get("/api/users/audit")
def list_user_audit(
    db: Session = Depends(get_db),
    _admin: User | None = Depends(
        require_admin
    ),
):

    logs = db.scalars(
        select(UserAuditLog)
        .order_by(
            UserAuditLog.created_at.desc()
        )
        .limit(100)
    ).all()

    return [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "target_user_id": log.target_user_id,
            "action": log.action,
            "actor_name": log.actor_name,
            "target_name": log.target_name,
            "target_username": log.target_username,
            "target_role": log.target_role,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@app.get("/api/users")
def list_users(
    db: Session = Depends(get_db),
    _admin: User | None = Depends(
        require_admin
    ),
):

    users = db.scalars(
        select(User)
        .order_by(
            User.full_name
        )
    ).all()

    return [
        {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "active": user.active,
            "created_at": user.created_at,
            "last_login": user.last_login,
        }
        for user in users
    ]


@app.post(
    "/api/users",
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(
        require_admin
    ),
):

    username = (
        payload.username
        .strip()
        .lower()
    )

    role = (
        payload.role
        .strip()
        .upper()
    )

    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=(
                "Rol inválido. "
                "Usa ADMIN o VENDEDOR."
            ),
        )

    existing = db.scalars(
        select(User).where(
            User.username == username
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="El usuario ya existe",
        )

    user = User(
        username=username,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(
            payload.password
        ),
        role=role,
        active=True,
    )

    db.add(user)
    db.flush()

    write_user_audit(
        db=db,
        actor=_admin,
        target=user,
        action="CREATE",
    )

    write_system_audit(
        db=db,
        actor=_admin,
        action="USER_CREATE",
        entity_type="USER",
        entity_id=user.id,
        entity_name=user.full_name,
        description=(
            f"Usuario @{user.username} "
            f"creado con rol {user.role}"
        ),
    )

    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "active": user.active,
    }


@app.patch(
    "/api/users/{user_id}/active"
)
def update_user_active(
    user_id: int,
    payload: UserActiveUpdate,
    db: Session = Depends(get_db),
    admin: User | None = Depends(
        require_admin
    ),
):

    user = db.get(
        User,
        user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    if (
        admin
        and admin.id == user.id
        and not payload.active
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "No puedes desactivar "
                "tu propio usuario."
            ),
        )

    previous_active = user.active

    user.active = payload.active

    if previous_active != user.active:
        write_user_audit(
            db=db,
            actor=admin,
            target=user,
            action=(
                "REACTIVATE"
                if user.active
                else "DEACTIVATE"
            ),
        )

    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "active": user.active,
    }




@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User | None = Depends(
        require_admin
    ),
):
    user = db.get(
        User,
        user_id,
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    if user.role == "ADMIN":
        raise HTTPException(
            status_code=403,
            detail=(
                "Los administradores no pueden "
                "eliminarse desde este módulo"
            ),
        )

    user.active = False

    write_user_audit(
        db=db,
        actor=admin,
        target=user,
        action="DEACTIVATE",
    )

    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "active": user.active,
        "deleted": True,
    }



@app.get("/api/audit")
def list_system_audit(
    limit: int = 100,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(
        require_admin
    ),
):

    limit = max(
        1,
        min(
            limit,
            500,
        ),
    )

    logs = db.scalars(
        select(SystemAuditLog)
        .order_by(
            SystemAuditLog.created_at.desc()
        )
        .limit(limit)
    ).all()

    return [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "actor_name": log.actor_name,
            "actor_role": log.actor_role,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "entity_name": log.entity_name,
            "description": log.description,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": "development"}




# ============================================================
# SUPPLIERS
# ============================================================

@app.get("/api/suppliers")
def list_suppliers(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):

    suppliers = db.scalars(
        select(Supplier)
        .order_by(Supplier.name.asc())
    ).all()

    return {
        "suppliers": [
            {
                "id": supplier.id,
                "name": supplier.name,
                "document": supplier.document,
                "phone": supplier.phone,
                "email": supplier.email,
                "address": supplier.address,
                "contact_name": supplier.contact_name,
                "notes": supplier.notes,
                "active": supplier.active,
                "created_at": supplier.created_at,
            }
            for supplier in suppliers
        ]
    }


@app.post("/api/suppliers")
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):

    supplier = Supplier(
        name=payload.name.strip(),
        document=(
            payload.document.strip()
            if payload.document
            else None
        ),
        phone=(
            payload.phone.strip()
            if payload.phone
            else None
        ),
        email=(
            payload.email.strip()
            if payload.email
            else None
        ),
        address=(
            payload.address.strip()
            if payload.address
            else None
        ),
        contact_name=(
            payload.contact_name.strip()
            if payload.contact_name
            else None
        ),
        notes=(
            payload.notes.strip()
            if payload.notes
            else None
        ),
    )

    db.add(supplier)
    db.flush()

    db.add(
        SystemAuditLog(
            actor_user_id=current_user.id,
            actor_name=current_user.full_name,
            actor_role=current_user.role,
            action="SUPPLIER_CREATE",
            entity_type="supplier",
            entity_id=str(supplier.id),
            entity_name=supplier.name,
            description=(
                f"Proveedor creado: {supplier.name}"
            ),
        )
    )

    db.commit()
    db.refresh(supplier)

    return {
        "id": supplier.id,
        "name": supplier.name,
        "document": supplier.document,
        "phone": supplier.phone,
        "email": supplier.email,
        "address": supplier.address,
        "contact_name": supplier.contact_name,
        "notes": supplier.notes,
        "active": supplier.active,
        "created_at": supplier.created_at,
    }


@app.patch("/api/suppliers/{supplier_id}")
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):

    supplier = db.get(
        Supplier,
        supplier_id,
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Proveedor no encontrado.",
        )

    values = payload.model_dump(
        exclude_unset=True
    )

    for field, value in values.items():

        if isinstance(value, str):
            value = value.strip()

        setattr(
            supplier,
            field,
            value,
        )

    db.add(
        SystemAuditLog(
            actor_user_id=current_user.id,
            actor_name=current_user.full_name,
            actor_role=current_user.role,
            action="SUPPLIER_UPDATE",
            entity_type="supplier",
            entity_id=str(supplier.id),
            entity_name=supplier.name,
            description=(
                f"Proveedor actualizado: {supplier.name}"
            ),
        )
    )

    db.commit()
    db.refresh(supplier)

    return {
        "id": supplier.id,
        "name": supplier.name,
        "document": supplier.document,
        "phone": supplier.phone,
        "email": supplier.email,
        "address": supplier.address,
        "contact_name": supplier.contact_name,
        "notes": supplier.notes,
        "active": supplier.active,
        "created_at": supplier.created_at,
    }


# ============================================================
# PURCHASES
# ============================================================

@app.get("/api/purchases")
def list_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):

    purchases = db.scalars(
        select(Purchase)
        .order_by(Purchase.created_at.desc())
    ).all()

    return {
        "purchases": [
            {
                "id": purchase.id,
                "number": purchase.number,
                "supplier_id": purchase.supplier_id,
                "supplier_name": (
                    purchase.supplier.name
                    if purchase.supplier
                    else None
                ),
                "status": purchase.status,
                "subtotal": purchase.subtotal,
                "total": purchase.total,
                "notes": purchase.notes,
                "created_by_user_id": purchase.created_by_user_id,
                "created_at": purchase.created_at,
            }
            for purchase in purchases
        ]
    }


@app.get("/api/purchases/{purchase_id}")
def get_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):

    purchase = db.get(
        Purchase,
        purchase_id,
    )

    if not purchase:
        raise HTTPException(
            status_code=404,
            detail="Compra no encontrada.",
        )

    return {
        "id": purchase.id,
        "number": purchase.number,
        "supplier_id": purchase.supplier_id,
        "supplier_name": (
            purchase.supplier.name
            if purchase.supplier
            else None
        ),
        "status": purchase.status,
        "subtotal": purchase.subtotal,
        "total": purchase.total,
        "notes": purchase.notes,
        "created_by_user_id": purchase.created_by_user_id,
        "created_at": purchase.created_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": (
                    item.product.name
                    if item.product
                    else None
                ),
                "quantity": item.quantity,
                "unit_cost": item.unit_cost,
                "subtotal": item.subtotal,
            }
            for item in purchase.items
        ],
    }


@app.post("/api/purchases")
def create_purchase(
    payload: PurchaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN")
    ),
):

    supplier = db.get(
        Supplier,
        payload.supplier_id,
    )

    if not supplier:
        raise HTTPException(
            status_code=404,
            detail="Proveedor no encontrado.",
        )

    if not supplier.active:
        raise HTTPException(
            status_code=400,
            detail="El proveedor está inactivo.",
        )

    product_ids = [
        item.product_id
        for item in payload.items
    ]

    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(
            status_code=400,
            detail="No repitas productos dentro de la misma compra.",
        )

    products = {}

    for item in payload.items:

        product = db.get(
            Product,
            item.product_id,
        )

        if not product:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Producto {item.product_id} no encontrado."
                ),
            )

        if not product.active:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El producto {product.name} está inactivo."
                ),
            )

        products[item.product_id] = product

    last_purchase = db.scalar(
        select(Purchase)
        .order_by(Purchase.id.desc())
    )

    next_number = (
        (last_purchase.id + 1)
        if last_purchase
        else 1
    )

    purchase_number = (
        f"COMP-{next_number:06d}"
    )

    purchase = Purchase(
        number=purchase_number,
        supplier_id=supplier.id,
        status="RECEIVED",
        subtotal=Decimal("0"),
        total=Decimal("0"),
        notes=(
            payload.notes.strip()
            if payload.notes
            else None
        ),
        created_by_user_id=current_user.id,
    )

    db.add(purchase)
    db.flush()

    total = Decimal("0")

    try:

        for payload_item in payload.items:

            product = products[
                payload_item.product_id
            ]

            quantity = Decimal(
                payload_item.quantity
            )

            unit_cost = Decimal(
                payload_item.unit_cost
            )

            subtotal = (
                quantity
                * unit_cost
            )

            previous_stock = Decimal(
                product.stock or 0
            )

            new_stock = (
                previous_stock
                + quantity
            )

            purchase_item = PurchaseItem(
                purchase_id=purchase.id,
                product_id=product.id,
                quantity=quantity,
                unit_cost=unit_cost,
                subtotal=subtotal,
            )

            db.add(
                purchase_item
            )

            product.stock = new_stock

            # Costo de última compra
            product.cost_price = unit_cost

            db.add(
                InventoryMovement(
                    product_id=product.id,
                    movement_type="PURCHASE",
                    quantity=quantity,
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    reference_type="PURCHASE",
                    reference_id=purchase.id,
                    notes=(
                        f"Compra {purchase.number} "
                        f"- {supplier.name}"
                    ),
                )
            )

            total += subtotal

        purchase.subtotal = total
        purchase.total = total

        db.add(
            SystemAuditLog(
                actor_user_id=current_user.id,
                actor_name=current_user.full_name,
                actor_role=current_user.role,
                action="PURCHASE_CREATE",
                entity_type="purchase",
                entity_id=str(purchase.id),
                entity_name=purchase.number,
                description=(
                    f"Compra {purchase.number} "
                    f"a {supplier.name} "
                    f"por {total}"
                ),
            )
        )

        db.commit()

    except Exception:

        db.rollback()

        raise

    db.refresh(purchase)

    return {
        "id": purchase.id,
        "number": purchase.number,
        "supplier_id": purchase.supplier_id,
        "supplier_name": supplier.name,
        "status": purchase.status,
        "subtotal": purchase.subtotal,
        "total": purchase.total,
        "notes": purchase.notes,
        "created_by_user_id": purchase.created_by_user_id,
        "created_at": purchase.created_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": (
                    item.product.name
                    if item.product
                    else None
                ),
                "quantity": item.quantity,
                "unit_cost": item.unit_cost,
                "subtotal": item.subtotal,
            }
            for item in purchase.items
        ],
    }


@app.get("/api/products")
def list_products(db: Session = Depends(get_db)):
    products = db.scalars(
        select(Product)
        .where(Product.active.is_(True))
        .order_by(Product.name)
    ).all()

    qr_product_ids = set(
        db.scalars(
            select(ProductQR.product_id)
        ).all()
    )

    return [
        {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "unit": product.unit,
            "price": product.price,
            "cost_price": product.cost_price,
            "margin": (
                product.price
                - product.cost_price
            ),
            "margin_percent": (
                (
                    (
                        product.price
                        - product.cost_price
                    )
                    / product.price
                    * Decimal("100")
                )
                if product.price
                else Decimal("0")
            ),
            "stock": product.stock,
            "minimum_stock": product.minimum_stock,
            "active": product.active,
            "has_qr": product.id in qr_product_ids,
            "image_url": get_image_url(product.image_url),
            "tax_rate": product.tax_rate,
            "tax_type": product.tax_type,
        }
        for product in products
    ]


@app.post("/api/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    product = Product(**payload.model_dump())

    db.add(product)
    db.flush()

    if product.stock > 0:
        movement = InventoryMovement(
            product=product,
            movement_type="INITIAL_STOCK",
            quantity=product.stock,
            previous_stock=Decimal("0"),
            new_stock=product.stock,
            reference_type="PRODUCT",
            reference_id=product.id,
            notes=f"Stock inicial de {product.name}",
        )

        db.add(movement)

    try:
        write_system_audit(
            db=db,
            actor=_admin,
            action="PRODUCT_CREATE",
            entity_type="PRODUCT",
            entity_id=product.id,
            entity_name=product.name,
            description="Producto creado",
        )

        db.commit()
        db.refresh(product)

    except Exception:
        db.rollback()
        raise

    return product



@app.patch("/api/products/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    product = db.get(
        Product,
        product_id,
    )

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    data = payload.model_dump(
        exclude_unset=True
    )

    if not data:
        return {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "unit": product.unit,
            "price": product.price,
            "cost_price": product.cost_price,
            "margin": (
                product.price
                - product.cost_price
            ),
            "stock": product.stock,
            "minimum_stock": product.minimum_stock,
            "active": product.active,
        }

    # --------------------------------------------------------
    # NORMALIZACIÓN
    # --------------------------------------------------------

    if "name" in data:
        data["name"] = (
            data["name"] or ""
        ).strip()

        if len(data["name"]) < 2:
            raise HTTPException(
                status_code=422,
                detail="El nombre debe tener al menos 2 caracteres",
            )

    if "sku" in data:
        normalized_sku = (
            data["sku"] or ""
        ).strip()

        data["sku"] = (
            normalized_sku
            if normalized_sku
            else None
        )

    if "unit" in data:
        data["unit"] = (
            data["unit"] or ""
        ).strip()

        if not data["unit"]:
            raise HTTPException(
                status_code=422,
                detail="La unidad es obligatoria",
            )

    # --------------------------------------------------------
    # SKU ÚNICO
    # --------------------------------------------------------

    if data.get("sku"):
        duplicated = db.scalar(
            select(Product).where(
                Product.sku == data["sku"],
                Product.id != product.id,
            )
        )

        if duplicated:
            raise HTTPException(
                status_code=409,
                detail="Ya existe otro producto con ese SKU",
            )

    # --------------------------------------------------------
    # REGISTRAR CAMBIOS PARA AUDITORÍA
    # --------------------------------------------------------

    labels = {
        "name": "Nombre",
        "sku": "SKU",
        "unit": "Unidad",
        "price": "Precio",
        "minimum_stock": "Stock mínimo",
        "tax_rate": "Tasa de impuesto",
        "tax_type": "Tipo de impuesto",
    }

    changes = []

    for field, new_value in data.items():
        old_value = getattr(
            product,
            field,
        )

        if old_value == new_value:
            continue

        changes.append(
            f"{labels.get(field, field)}: "
            f"{old_value if old_value is not None else '—'}"
            f" -> "
            f"{new_value if new_value is not None else '—'}"
        )

        setattr(
            product,
            field,
            new_value,
        )

    if not changes:
        return {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "unit": product.unit,
            "price": product.price,
            "stock": product.stock,
            "minimum_stock": product.minimum_stock,
            "active": product.active,
        }

    write_system_audit(
        db=db,
        actor=_admin,
        action="PRODUCT_UPDATE",
        entity_type="PRODUCT",
        entity_id=product.id,
        entity_name=product.name,
        description=" | ".join(changes),
    )

    try:
        db.commit()
        db.refresh(product)

    except Exception:
        db.rollback()
        raise

    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "unit": product.unit,
        "price": product.price,
        "stock": product.stock,
        "minimum_stock": product.minimum_stock,
        "active": product.active,
    }


@app.delete("/api/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    product = db.get(Product, product_id)

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    product.active = False
    write_system_audit(
        db=db,
        actor=_admin,
        action="PRODUCT_DEACTIVATE",
        entity_type="PRODUCT",
        entity_id=product.id,
        entity_name=product.name,
        description="Producto desactivado",
    )


    db.commit()

    return {
        "ok": True,
        "product_id": product.id,
        "name": product.name,
        "active": product.active,
    }


@app.post("/api/products/{product_id}/qr")
def generate_product_qr(
    product_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    product = db.get(Product, product_id)

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    product_qr = db.scalar(
        select(ProductQR).where(
            ProductQR.product_id == product.id
        )
    )

    created = False

    if not product_qr:
        random_part = secrets.token_hex(5).upper()

        code = (
            f"LP-PROD-"
            f"{product.id:06d}-"
            f"{random_part}"
        )

        product_qr = ProductQR(
            product_id=product.id,
            code=code,
        )

        db.add(product_qr)
        write_system_audit(
            db=db,
            actor=_admin,
            action="QR_CREATE",
            entity_type="PRODUCT_QR",
            entity_id=product_qr.id,
            entity_name=product.name,
            description="Código QR generado",
        )

        db.commit()
        db.refresh(product_qr)

        created = True

    image = qrcode.make(
        product_qr.code
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    return {
        "id": product_qr.id,
        "product_id": product.id,
        "product_name": product.name,
        "sku": product.sku,
        "code": product_qr.code,
        "created": created,
        "created_at": product_qr.created_at,
        "image_data_url": (
            "data:image/png;base64,"
            + encoded
        ),
    }


@app.delete("/api/products/{product_id}/qr")
def delete_product_qr(
    product_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    product_qr = db.scalar(
        select(ProductQR).where(
            ProductQR.product_id == product_id
        )
    )

    if not product_qr:
        raise HTTPException(
            status_code=404,
            detail="Este producto no tiene QR",
        )

    db.delete(product_qr)
    write_system_audit(
        db=db,
        actor=_admin,
        action="QR_DELETE",
        entity_type="PRODUCT_QR",
        entity_id=product_qr.id,
        entity_name=(
            product_qr.product.name
            if product_qr.product
            else str(product_id)
        ),
        description="Código QR eliminado",
    )

    db.commit()

    return {
        "ok": True,
        "product_id": product_id,
    }


# ============================================================
# PRODUCT IMAGES
# ============================================================


@app.post(
    "/api/products/{product_id}/image",
    status_code=status.HTTP_200_OK,
)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    product = db.get(Product, product_id)

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    content = await file.read()

    error = validate_image(
        file.filename or "image.jpg",
        file.content_type,
        len(content),
    )

    if error:
        raise HTTPException(
            status_code=422,
            detail=error,
        )

    if product.image_url:
        delete_image(product.image_url)

    relative_path = save_image(
        content, file.filename or "image.jpg"
    )

    product.image_url = relative_path

    write_system_audit(
        db=db,
        actor=None,
        action="PRODUCT_IMAGE_UPLOAD",
        entity_type="PRODUCT",
        entity_id=product.id,
        entity_name=product.name,
        description="Imagen de producto actualizada",
    )

    try:
        db.commit()
        db.refresh(product)
    except Exception:
        db.rollback()
        raise

    return {
        "ok": True,
        "image_url": get_image_url(product.image_url),
    }


@app.delete(
    "/api/products/{product_id}/image",
)
def delete_product_image(
    product_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    product = db.get(Product, product_id)

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    if product.image_url:
        delete_image(product.image_url)
        product.image_url = None

        write_system_audit(
            db=db,
            actor=None,
            action="PRODUCT_IMAGE_DELETE",
            entity_type="PRODUCT",
            entity_id=product.id,
            entity_name=product.name,
            description="Imagen de producto eliminada",
        )

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {"ok": True}


@app.patch(
    "/api/products/{product_id}/tax",
)
def update_product_tax(
    product_id: int,
    payload: TaxConfigUpdate,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    product = db.get(Product, product_id)

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    product.tax_rate = payload.tax_rate
    product.tax_type = payload.tax_type.strip().upper()

    write_system_audit(
        db=db,
        actor=None,
        action="PRODUCT_TAX_UPDATE",
        entity_type="PRODUCT",
        entity_id=product.id,
        entity_name=product.name,
        description=(
            f"Impuesto actualizado: "
            f"{product.tax_rate}% {product.tax_type}"
        ),
    )

    try:
        db.commit()
        db.refresh(product)
    except Exception:
        db.rollback()
        raise

    return {
        "ok": True,
        "tax_rate": product.tax_rate,
        "tax_type": product.tax_type,
    }


# ============================================================
# QR RESOLVE
# ============================================================


@app.post("/api/qr/resolve")
def resolve_qr(
    payload: QRResolveRequest,
    db: Session = Depends(get_db),
):
    qr_value = payload.qr_value.strip()

    product_qr = db.scalar(
        select(ProductQR).where(
            ProductQR.code == qr_value
        )
    )

    if not product_qr:
        raise HTTPException(
            status_code=404,
            detail=(
                "Código QR no reconocido. "
                "Este código no corresponde a ningún "
                "producto registrado en el sistema."
            ),
        )

    product = db.get(
        Product, product_qr.product_id
    )

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail=(
                "No encontramos un producto asociado "
                "a este código."
            ),
        )

    qr_image = qrcode.make(product_qr.code)
    buffer = io.BytesIO()
    qr_image.save(buffer, format="PNG")
    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    return {
        "valid": True,
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "unit": product.unit,
            "price": product.price,
            "stock": product.stock,
            "image_url": get_image_url(
                product.image_url
            ),
            "tax_rate": product.tax_rate,
            "tax_type": product.tax_type,
        },
        "qr": {
            "code": product_qr.code,
            "created_at": product_qr.created_at,
            "image_data_url": (
                "data:image/png;base64," + encoded
            ),
        },
    }


# ============================================================
# COMPANY INFO (FISCAL DATA)
# ============================================================


@app.get("/api/company-info")
def get_company_info(
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    info = db.scalar(select(CompanyInfo).limit(1))

    if not info:
        return None

    return {
        "id": info.id,
        "company_name": info.company_name,
        "nit": info.nit,
        "dv": info.dv,
        "address": info.address,
        "municipality": info.municipality,
        "department": info.department,
        "country": info.country,
        "phone": info.phone,
        "email": info.email,
        "regime": info.regime,
        "responsibilities": info.responsibilities,
        "resolution_number": info.resolution_number,
        "resolution_prefix": info.resolution_prefix,
        "resolution_range_from": info.resolution_range_from,
        "resolution_range_to": info.resolution_range_to,
        "resolution_date": info.resolution_date,
        "software_id": info.software_id,
        "created_at": info.created_at,
        "updated_at": info.updated_at,
    }


@app.post(
    "/api/company-info",
    status_code=status.HTTP_201_CREATED,
)
def create_company_info(
    payload: CompanyInfoCreate,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    existing = db.scalar(select(CompanyInfo).limit(1))

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "Ya existe información de la empresa. "
                "Usa PUT para actualizar."
            ),
        )

    info = CompanyInfo(
        company_name=payload.company_name.strip(),
        nit=payload.nit.strip(),
        dv=payload.dv.strip() if payload.dv else None,
        address=payload.address.strip() if payload.address else None,
        municipality=payload.municipality.strip() if payload.municipality else None,
        department=payload.department.strip() if payload.department else None,
        country=payload.country,
        phone=payload.phone.strip() if payload.phone else None,
        email=payload.email.strip() if payload.email else None,
        regime=payload.regime.strip() if payload.regime else None,
        responsibilities=payload.responsibilities,
        resolution_number=payload.resolution_number,
        resolution_prefix=payload.resolution_prefix,
        resolution_range_from=payload.resolution_range_from,
        resolution_range_to=payload.resolution_range_to,
        resolution_date=payload.resolution_date,
        software_id=payload.software_id,
        software_secret=payload.software_secret,
        certificate_path=payload.certificate_path,
    )

    db.add(info)

    write_system_audit(
        db=db,
        actor=None,
        action="COMPANY_INFO_CREATE",
        entity_type="COMPANY_INFO",
        entity_id=info.id,
        entity_name=info.company_name,
        description="Información fiscal de la empresa configurada",
    )

    try:
        db.commit()
        db.refresh(info)
    except Exception:
        db.rollback()
        raise

    return {
        "ok": True,
        "id": info.id,
    }


@app.put("/api/company-info")
def update_company_info(
    payload: CompanyInfoUpdate,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin),
):
    info = db.scalar(select(CompanyInfo).limit(1))

    if not info:
        raise HTTPException(
            status_code=404,
            detail=(
                "No existe información de la empresa. "
                "Usa POST para crear."
            ),
        )

    data = payload.model_dump(exclude_unset=True)

    for field, value in data.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(info, field, value)

    info.updated_at = datetime.utcnow()

    write_system_audit(
        db=db,
        actor=None,
        action="COMPANY_INFO_UPDATE",
        entity_type="COMPANY_INFO",
        entity_id=info.id,
        entity_name=info.company_name,
        description="Información fiscal actualizada",
    )

    try:
        db.commit()
        db.refresh(info)
    except Exception:
        db.rollback()
        raise

    return {"ok": True}


# ============================================================
# ELECTRONIC INVOICES
# ============================================================


@app.get("/api/electronic-invoices")
def list_electronic_invoices(
    status_filter: str | None = None,
    customer_name: str | None = None,
    invoice_number: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(require_admin),
):
    limit = max(1, min(limit, 200))

    query = select(ElectronicInvoice).order_by(
        ElectronicInvoice.created_at.desc()
    )

    if status_filter:
        query = query.where(
            ElectronicInvoice.status == status_filter.upper()
        )

    if customer_name:
        query = query.where(
            ElectronicInvoice.customer_name.ilike(
                f"%{customer_name}%"
            )
        )

    if invoice_number:
        query = query.where(
            ElectronicInvoice.invoice_number.ilike(
                f"%{invoice_number}%"
            )
        )

    invoices = db.scalars(query.limit(limit)).all()

    return [
        {
            "id": inv.id,
            "sale_id": inv.sale_id,
            "invoice_number": inv.invoice_number,
            "prefix": inv.prefix,
            "status": inv.status,
            "provider": inv.provider,
            "cufe": inv.cufe,
            "customer_name": inv.customer_name,
            "subtotal": inv.subtotal,
            "tax_total": inv.tax_total,
            "total": inv.total,
            "environment": inv.environment,
            "issued_at": inv.issued_at,
            "created_at": inv.created_at,
            "error_message": inv.error_message,
        }
        for inv in invoices
    ]


@app.get("/api/electronic-invoices/{invoice_id}")
def get_electronic_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(require_admin),
):
    inv = db.get(ElectronicInvoice, invoice_id)

    if not inv:
        raise HTTPException(
            status_code=404,
            detail="Factura electrónica no encontrada",
        )

    sale = db.get(Sale, inv.sale_id)
    sale_items = []
    if sale:
        for item in sale.items:
            product = item.product
            tax_amount = Decimal("0")
            if product and product.tax_rate > 0:
                tax_amount = (
                    item.subtotal
                    * product.tax_rate
                    / Decimal("100")
                )
            sale_items.append({
                "product_name": (
                    product.name if product else "Producto"
                ),
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.quantity * item.unit_price,
                "tax_rate": (
                    product.tax_rate if product else Decimal("0")
                ),
                "tax_amount": tax_amount,
                "tax_type": (
                    product.tax_type if product else "IVA"
                ),
            })

    return {
        "id": inv.id,
        "sale_id": inv.sale_id,
        "invoice_number": inv.invoice_number,
        "prefix": inv.prefix,
        "status": inv.status,
        "provider": inv.provider,
        "provider_reference": inv.provider_reference,
        "cufe": inv.cufe,
        "qr_data": inv.qr_data,
        "xml_url": inv.xml_url,
        "pdf_url": inv.pdf_url,
        "dian_response": inv.dian_response,
        "error_message": inv.error_message,
        "customer_name": inv.customer_name,
        "customer_document_type": inv.customer_document_type,
        "customer_document_number": inv.customer_document_number,
        "customer_email": inv.customer_email,
        "customer_address": inv.customer_address,
        "customer_phone": inv.customer_phone,
        "subtotal": inv.subtotal,
        "tax_total": inv.tax_total,
        "total": inv.total,
        "environment": inv.environment,
        "issued_at": inv.issued_at,
        "created_at": inv.created_at,
        "updated_at": inv.updated_at,
        "items": sale_items,
    }


@app.post(
    "/api/electronic-invoices",
    status_code=status.HTTP_201_CREATED,
)
def create_electronic_invoice(
    payload: ElectronicInvoiceCreate,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(require_admin),
):
    sale = db.get(Sale, payload.sale_id)

    if not sale:
        raise HTTPException(
            status_code=404,
            detail="Venta no encontrada",
        )

    if str(sale.status).upper() in {"ANULADA", "CANCELLED"}:
        raise HTTPException(
            status_code=409,
            detail="No se puede facturar una venta anulada",
        )

    existing = db.scalar(
        select(ElectronicInvoice).where(
            ElectronicInvoice.sale_id == sale.id,
            ElectronicInvoice.status.in_(
                [
                    "DRAFT",
                    "GENERATED",
                    "SIGNED",
                    "SENDING",
                    "PENDING",
                    "SENT",
                    "ACCEPTED",
                ]
            ),
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Esta venta ya tiene una factura "
                f"electrónica: {existing.invoice_number} "
                f"(estado: {existing.status})"
            ),
        )

    company = db.scalar(select(CompanyInfo).limit(1))
    prefix = "FE"
    next_number = 1

    if company and company.resolution_prefix:
        prefix = company.resolution_prefix

    last_inv = db.scalar(
        select(ElectronicInvoice)
        .where(ElectronicInvoice.prefix == prefix)
        .order_by(ElectronicInvoice.id.desc())
    )

    if last_inv:
        try:
            last_num = int(
                last_inv.invoice_number.replace(
                    f"{prefix}", ""
                )
            )
            next_number = last_num + 1
        except ValueError:
            next_number = last_inv.id + 1

    invoice_number = f"{prefix}{next_number:06d}"

    subtotal = Decimal("0")
    tax_total = Decimal("0")
    items_data = []

    for sale_item in sale.items:
        product = sale_item.product
        item_subtotal = (
            sale_item.quantity * sale_item.unit_price
        )
        item_tax = Decimal("0")
        item_tax_rate = Decimal("0")
        item_tax_type = "IVA"

        if product:
            item_tax_rate = product.tax_rate or Decimal("0")
            item_tax_type = product.tax_type or "IVA"
            if item_tax_rate > 0:
                item_tax = (
                    item_subtotal
                    * item_tax_rate
                    / Decimal("100")
                )

        subtotal += item_subtotal
        tax_total += item_tax

        items_data.append(
            InvoiceItemData(
                product_name=(
                    product.name if product else "Producto"
                ),
                quantity=sale_item.quantity,
                unit_price=sale_item.unit_price,
                subtotal=item_subtotal,
                tax_rate=item_tax_rate,
                tax_amount=item_tax,
                tax_type=item_tax_type,
            )
        )

    total = subtotal + tax_total

    customer_name = (
        payload.customer_name
        or sale.customer_name
        or "Consumidor final"
    )

    env = os.getenv(
        "ELECTRONIC_INVOICE_ENV", "sandbox"
    ).strip()

    provider_name = invoice_provider_type

    inv = ElectronicInvoice(
        sale_id=sale.id,
        invoice_number=invoice_number,
        prefix=prefix,
        status="DRAFT",
        provider=provider_name,
        customer_name=customer_name,
        customer_document_type=payload.customer_document_type,
        customer_document_number=payload.customer_document_number,
        customer_email=payload.customer_email,
        customer_address=payload.customer_address,
        customer_phone=payload.customer_phone,
        subtotal=subtotal,
        tax_total=tax_total,
        total=total,
        environment=env,
    )

    db.add(inv)
    db.flush()

    write_system_audit(
        db=db,
        actor=_admin,
        action="ELECTRONIC_INVOICE_CREATE",
        entity_type="ELECTRONIC_INVOICE",
        entity_id=inv.id,
        entity_name=invoice_number,
        description=(
            f"Factura electrónica {invoice_number} "
            f"creada para venta {sale.number}"
        ),
    )

    try:
        result = invoice_provider.create_invoice(
            invoice_number=invoice_number,
            prefix=prefix,
            customer_name=customer_name,
            customer_document_type=payload.customer_document_type,
            customer_document_number=payload.customer_document_number,
            customer_email=payload.customer_email,
            customer_address=payload.customer_address,
            customer_phone=payload.customer_phone,
            items=items_data,
            subtotal=subtotal,
            tax_total=tax_total,
            total=total,
            environment=env,
        )

        if result.success:
            inv.status = result.status
            inv.provider_reference = result.provider_reference
            inv.cufe = result.cufe
            inv.qr_data = result.qr_data
            inv.xml_url = result.xml_url
            inv.pdf_url = result.pdf_url
            inv.dian_response = (
                str(result.dian_response)
                if result.dian_response
                else None
            )
            inv.issued_at = result.issued_at

            write_system_audit(
                db=db,
                actor=_admin,
                action="ELECTRONIC_INVOICE_SENT",
                entity_type="ELECTRONIC_INVOICE",
                entity_id=inv.id,
                entity_name=invoice_number,
                description=(
                    f"Factura {invoice_number} "
                    f"enviada. Estado: {result.status}"
                ),
            )
        else:
            inv.status = "ERROR"
            inv.error_message = result.error_message

            write_system_audit(
                db=db,
                actor=_admin,
                action="ELECTRONIC_INVOICE_ERROR",
                entity_type="ELECTRONIC_INVOICE",
                entity_id=inv.id,
                entity_name=invoice_number,
                description=(
                    f"Error en factura {invoice_number}: "
                    f"{result.error_message}"
                ),
            )

        db.commit()
        db.refresh(inv)

    except Exception as e:
        inv.status = "ERROR"
        inv.error_message = str(e)
        db.commit()
        db.refresh(inv)

    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "prefix": inv.prefix,
        "status": inv.status,
        "provider": inv.provider,
        "cufe": inv.cufe,
        "subtotal": inv.subtotal,
        "tax_total": inv.tax_total,
        "total": inv.total,
        "environment": inv.environment,
        "error_message": inv.error_message,
        "created_at": inv.created_at,
    }


@app.get(
    "/api/electronic-invoices/{invoice_id}/status"
)
def get_electronic_invoice_status(
    invoice_id: int,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(require_admin),
):
    inv = db.get(ElectronicInvoice, invoice_id)

    if not inv:
        raise HTTPException(
            status_code=404,
            detail="Factura electrónica no encontrada",
        )

    if (
        inv.provider_reference
        and inv.status not in {"ACCEPTED", "REJECTED"}
    ):
        try:
            result = invoice_provider.get_invoice_status(
                inv.provider_reference
            )
            inv.status = result.status
            inv.updated_at = datetime.utcnow()
            db.commit()
        except Exception:
            pass

    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "status": inv.status,
        "cufe": inv.cufe,
        "environment": inv.environment,
        "error_message": inv.error_message,
    }


@app.post(
    "/api/electronic-invoices/{invoice_id}/send",
    status_code=status.HTTP_200_OK,
)
def send_electronic_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(require_admin),
):
    inv = db.get(ElectronicInvoice, invoice_id)

    if not inv:
        raise HTTPException(
            status_code=404,
            detail="Factura electrónica no encontrada",
        )

    retryable = {"DRAFT", "GENERATED", "SIGNED", "ERROR"}

    if inv.status not in retryable:
        raise HTTPException(
            status_code=409,
            detail=(
                f"La factura {inv.invoice_number} está en estado "
                f"'{inv.status}' y no puede ser reenviada."
            ),
        )

    sale = db.get(Sale, inv.sale_id)
    if not sale or str(sale.status).upper() in {"ANULADA", "CANCELLED"}:
        raise HTTPException(
            status_code=409,
            detail="La venta asociada está anulada.",
        )

    items_data = []
    subtotal = Decimal("0")
    tax_total = Decimal("0")

    for sale_item in sale.items:
        product = sale_item.product
        item_subtotal = sale_item.quantity * sale_item.unit_price
        item_tax = Decimal("0")
        item_tax_rate = Decimal("0")
        item_tax_type = "IVA"

        if product:
            item_tax_rate = product.tax_rate or Decimal("0")
            item_tax_type = product.tax_type or "IVA"
            if item_tax_rate > 0:
                item_tax = item_subtotal * item_tax_rate / Decimal("100")

        subtotal += item_subtotal
        tax_total += item_tax

        items_data.append(
            InvoiceItemData(
                product_name=product.name if product else "Producto",
                quantity=sale_item.quantity,
                unit_price=sale_item.unit_price,
                subtotal=item_subtotal,
                tax_rate=item_tax_rate,
                tax_amount=item_tax,
                tax_type=item_tax_type,
            )
        )

    total = subtotal + tax_total
    env = inv.environment or "sandbox"
    provider_name = invoice_provider_type

    inv.status = "SENDING"
    inv.provider = provider_name
    inv.updated_at = datetime.utcnow()
    db.commit()

    write_system_audit(
        db=db,
        actor=_admin,
        action="ELECTRONIC_INVOICE_SEND_ATTEMPT",
        entity_type="ELECTRONIC_INVOICE",
        entity_id=inv.id,
        entity_name=inv.invoice_number,
        description=f"Reintento de envío de factura {inv.invoice_number}",
    )

    try:
        result = invoice_provider.create_invoice(
            invoice_number=inv.invoice_number,
            prefix=inv.prefix,
            customer_name=inv.customer_name,
            customer_document_type=inv.customer_document_type,
            customer_document_number=inv.customer_document_number,
            customer_email=inv.customer_email,
            customer_address=inv.customer_address,
            customer_phone=inv.customer_phone,
            items=items_data,
            subtotal=subtotal,
            tax_total=tax_total,
            total=total,
            environment=env,
        )

        if result.success:
            inv.status = result.status
            inv.provider_reference = result.provider_reference
            inv.cufe = result.cufe
            inv.qr_data = result.qr_data
            inv.xml_url = result.xml_url
            inv.pdf_url = result.pdf_url
            inv.dian_response = (
                str(result.dian_response)
                if result.dian_response
                else None
            )
            inv.issued_at = result.issued_at
            inv.error_message = None

            write_system_audit(
                db=db,
                actor=_admin,
                action="ELECTRONIC_INVOICE_SENT",
                entity_type="ELECTRONIC_INVOICE",
                entity_id=inv.id,
                entity_name=inv.invoice_number,
                description=f"Factura {inv.invoice_number} enviada. Estado: {result.status}",
            )
        else:
            inv.status = "ERROR"
            inv.error_message = result.error_message

            write_system_audit(
                db=db,
                actor=_admin,
                action="ELECTRONIC_INVOICE_ERROR",
                entity_type="ELECTRONIC_INVOICE",
                entity_id=inv.id,
                entity_name=inv.invoice_number,
                description=f"Error en factura {inv.invoice_number}: {result.error_message}",
            )

        db.commit()
        db.refresh(inv)

    except Exception as e:
        inv.status = "ERROR"
        inv.error_message = str(e)
        db.commit()
        db.refresh(inv)

    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "status": inv.status,
        "cufe": inv.cufe,
        "environment": inv.environment,
        "error_message": inv.error_message,
    }


@app.get(
    "/api/electronic-invoices/{invoice_id}/xml",
)
def get_electronic_invoice_xml(
    invoice_id: int,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(require_admin),
):
    inv = db.get(ElectronicInvoice, invoice_id)

    if not inv:
        raise HTTPException(
            status_code=404,
            detail="Factura electrónica no encontrada",
        )

    xml = invoice_provider.get_xml(inv.provider_reference or "")
    if not xml:
        raise HTTPException(
            status_code=404,
            detail="XML no disponible para esta factura.",
        )

    return Response(
        content=xml,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{inv.invoice_number}.xml"'
        },
    )


@app.post(
    "/api/sales/{sale_id}/electronic-invoice",
    status_code=status.HTTP_201_CREATED,
)
def generate_sale_electronic_invoice(
    sale_id: int,
    db: Session = Depends(get_db),
    _admin: User | None = Depends(require_admin),
):
    sale = db.get(Sale, sale_id)

    if not sale:
        raise HTTPException(
            status_code=404,
            detail="Venta no encontrada",
        )

    existing = db.scalar(
        select(ElectronicInvoice).where(
            ElectronicInvoice.sale_id == sale.id,
            ElectronicInvoice.status.in_(
                [
                    "DRAFT",
                    "GENERATED",
                    "SIGNED",
                    "SENDING",
                    "PENDING",
                    "SENT",
                    "ACCEPTED",
                ]
            ),
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Esta venta ya tiene factura electrónica: "
                f"{existing.invoice_number}"
            ),
        )

    invoice_payload = ElectronicInvoiceCreate(
        sale_id=sale.id,
        customer_name=sale.customer_name,
    )

    return create_electronic_invoice(
        invoice_payload, db, _admin
    )


@app.get("/api/sales")
def list_sales(db: Session = Depends(get_db)):
    return db.scalars(select(Sale).order_by(Sale.created_at.desc())).all()


@app.post(
    "/api/sales",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_roles(
                "ADMIN",
                "VENDEDOR",
            )
        )
    ],
)
def create_sale(
    payload: SaleCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
            "VENDEDOR",
        )
    ),
):
    product_ids = [item.product_id for item in payload.items]

    products = {
        product.id: product
        for product in db.scalars(
            select(Product).where(Product.id.in_(product_ids))
        ).all()
    }

    if len(products) != len(set(product_ids)):
        raise HTTPException(
            status_code=404,
            detail="Uno o más productos no existen",
        )

    total = Decimal("0")

    for item in payload.items:
        product = products[item.product_id]

        if product.stock < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Stock insuficiente para {product.name}",
            )

        total += product.price * item.quantity

    next_sale_id = (
        db.scalar(
            select(Sale.id).order_by(Sale.id.desc())
        ) or 0
    ) + 1

    sale = Sale(
        number=f"V-{next_sale_id:05d}",
        customer_name=payload.customer_name,
        payment_method=payload.payment_method,
        total=total,
        status="completada",
    )

    db.add(sale)
    db.flush()

    for item in payload.items:
        product = products[item.product_id]

        previous_stock = product.stock
        new_stock = previous_stock - item.quantity

        sale_item = SaleItem(
            sale=sale,
            product=product,
            quantity=item.quantity,
            unit_price=product.price,
        )

        movement = InventoryMovement(
            product=product,
            movement_type="SALE",
            quantity=-item.quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reference_type="SALE",
            reference_id=sale.id,
            notes=f"Venta {sale.number}",
        )

        product.stock = new_stock

        db.add(sale_item)
        db.add(movement)

    try:
        write_system_audit(
            db=db,
            actor=actor,
            action="SALE_CREATE",
            entity_type="SALE",
            entity_id=sale.id,
            entity_name=sale.number,
            description=(
                f"Venta registrada por {sale.total}"
            ),
        )

        db.commit()
        db.refresh(sale)

    except Exception:
        db.rollback()
        raise

    return {
        "id": sale.id,
        "number": sale.number,
        "total": sale.total,
        "status": sale.status,
    }


@app.post("/api/sales/{sale_id}/cancel")
def cancel_sale(
    sale_id: int,
    payload: SaleCancelCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
        )
    ),
):
    sale = db.get(
        Sale,
        sale_id,
    )

    if not sale:
        raise HTTPException(
            status_code=404,
            detail="Venta no encontrada",
        )

    if str(sale.status).upper() in {
        "ANULADA",
        "CANCELLED",
    }:
        raise HTTPException(
            status_code=409,
            detail="La venta ya fue anulada",
        )

    reason = payload.reason.strip()

    if len(reason) < 4:
        raise HTTPException(
            status_code=422,
            detail=(
                "Debes indicar un motivo "
                "de anulación válido"
            ),
        )

    if not sale.items:
        raise HTTPException(
            status_code=409,
            detail=(
                "La venta no tiene productos "
                "para restaurar"
            ),
        )

    # ========================================================
    # RESTAURAR INVENTARIO
    # ========================================================

    restored_items = []

    for item in sale.items:

        product = item.product

        if not product:
            raise HTTPException(
                status_code=409,
                detail=(
                    "No fue posible localizar "
                    "uno de los productos de la venta"
                ),
            )

        previous_stock = product.stock

        new_stock = (
            previous_stock
            + item.quantity
        )

        product.stock = new_stock

        movement = InventoryMovement(
            product=product,
            movement_type="SALE_CANCEL",
            quantity=item.quantity,
            previous_stock=previous_stock,
            new_stock=new_stock,
            reference_type="SALE",
            reference_id=sale.id,
            notes=(
                f"Restauración automática por "
                f"anulación de {sale.number}. "
                f"Motivo: {reason}"
            ),
        )

        db.add(
            movement
        )

        restored_items.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "quantity": item.quantity,
                "previous_stock": previous_stock,
                "new_stock": new_stock,
            }
        )

    # ========================================================
    # MARCAR VENTA COMO ANULADA
    # ========================================================

    sale.status = "ANULADA"

    sale.cancellation_reason = reason

    sale.cancelled_at = datetime.utcnow()

    sale.cancelled_by_name = (
        actor.full_name
        or actor.username
    )

    write_system_audit(
        db=db,
        actor=actor,
        action="SALE_CANCEL",
        entity_type="SALE",
        entity_id=sale.id,
        entity_name=sale.number,
        description=(
            f"Venta {sale.number} anulada. "
            f"Motivo: {reason}. "
            f"Inventario restaurado automáticamente."
        ),
    )

    try:
        db.commit()
        db.refresh(sale)

    except Exception:
        db.rollback()
        raise

    return {
        "ok": True,
        "id": sale.id,
        "number": sale.number,
        "status": sale.status,
        "cancellation_reason": (
            sale.cancellation_reason
        ),
        "cancelled_by": (
            sale.cancelled_by_name
        ),
        "cancelled_at": (
            sale.cancelled_at
        ),
        "restored_items": (
            restored_items
        ),
    }


@app.get("/api/sales")
def list_sales(db: Session = Depends(get_db)):
    return db.scalars(select(Sale).order_by(Sale.created_at.desc())).all()





@app.get("/api/sales/{sale_id}")
def get_sale_detail(
    sale_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
            "VENDEDOR",
        )
    ),
):
    sale = db.get(
        Sale,
        sale_id,
    )

    if not sale:
        raise HTTPException(
            status_code=404,
            detail="Venta no encontrada",
        )

    return {
        "id": sale.id,
        "number": sale.number,
        "customer_name": sale.customer_name,
        "payment_method": sale.payment_method,
        "total": sale.total,
        "status": sale.status,
        "created_at": sale.created_at,

        "cancellation_reason": getattr(
            sale,
            "cancellation_reason",
            None,
        ),

        "cancelled_at": getattr(
            sale,
            "cancelled_at",
            None,
        ),

        "cancelled_by_name": getattr(
            sale,
            "cancelled_by_name",
            None,
        ),

        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": (
                    item.product.name
                    if item.product
                    else "Producto"
                ),
                "sku": (
                    item.product.sku
                    if item.product
                    else None
                ),
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": (
                    item.quantity
                    * item.unit_price
                ),
            }
            for item in sale.items
        ],
    }


# ============================================================
# OPEN ACCOUNTS / TABLES / VIP
# ============================================================


def serialize_open_account(
    account: OpenAccount,
):
    return {
        "id": account.id,
        "number": account.number,
        "account_type": account.account_type,
        "label": account.label,
        "zone": account.zone,
        "customer_name": account.customer_name,
        "status": account.status,
        "total": account.total,
        "opened_by_user_id": account.opened_by_user_id,
        "opened_by_name": account.opened_by_name,
        "closed_by_user_id": account.closed_by_user_id,
        "closed_by_name": account.closed_by_name,
        "payment_method": account.payment_method,
        "created_at": account.created_at,
        "closed_at": account.closed_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": (
                    item.quantity
                    * item.unit_price
                ),
                "created_at": item.created_at,
            }
            for item in account.items
        ],
    }


@app.get("/api/open-accounts")
def list_open_accounts(
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
            "VENDEDOR",
        )
    ),
):
    accounts = db.scalars(
        select(OpenAccount)
        .order_by(
            OpenAccount.created_at.desc()
        )
    ).all()

    return [
        serialize_open_account(account)
        for account in accounts
    ]


@app.post(
    "/api/open-accounts",
    status_code=status.HTTP_201_CREATED,
)
def create_open_account(
    payload: OpenAccountCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
            "VENDEDOR",
        )
    ),
):
    account_type = (
        payload.account_type
        .upper()
        .strip()
    )

    allowed_types = {
        "MESA",
        "VIP",
        "BARRA",
        "OTRO",
    }

    if account_type not in allowed_types:
        raise HTTPException(
            status_code=422,
            detail=(
                "Tipo de cuenta inválido. "
                "Usa MESA, VIP, BARRA u OTRO."
            ),
        )

    label = payload.label.strip()

    existing = db.scalar(
        select(OpenAccount).where(
            OpenAccount.status == "OPEN",
            OpenAccount.account_type == account_type,
            OpenAccount.label == label,
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{account_type.title()} "
                f"{label} ya tiene una cuenta abierta"
            ),
        )

    next_id = (
        db.scalar(
            select(OpenAccount.id)
            .order_by(
                OpenAccount.id.desc()
            )
        )
        or 0
    ) + 1

    account = OpenAccount(
        number=f"C-{next_id:05d}",
        account_type=account_type,
        label=label,
        zone=(
            payload.zone.strip()
            if payload.zone
            else None
        ),
        customer_name=(
            payload.customer_name.strip()
            or "Consumidor final"
        ),
        status="OPEN",
        total=Decimal("0"),
        opened_by_user_id=actor.id,
        opened_by_name=(
            actor.full_name
            or actor.username
        ),
    )

    db.add(account)
    db.flush()

    write_system_audit(
        db=db,
        actor=actor,
        action="ACCOUNT_OPEN",
        entity_type="OPEN_ACCOUNT",
        entity_id=account.id,
        entity_name=(
            f"{account.account_type} "
            f"{account.label}"
        ),
        description=(
            f"Cuenta {account.number} abierta"
        ),
    )

    try:
        db.commit()
        db.refresh(account)

    except Exception:
        db.rollback()
        raise

    return serialize_open_account(
        account
    )


@app.post(
    "/api/open-accounts/{account_id}/items",
    status_code=status.HTTP_201_CREATED,
)
def add_open_account_item(
    account_id: int,
    payload: OpenAccountItemCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
            "VENDEDOR",
        )
    ),
):
    account = db.get(
        OpenAccount,
        account_id,
    )

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Cuenta no encontrada",
        )

    if account.status != "OPEN":
        raise HTTPException(
            status_code=409,
            detail="La cuenta ya está cerrada",
        )

    product = db.get(
        Product,
        payload.product_id,
    )

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    if product.stock < payload.quantity:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Stock insuficiente para "
                f"{product.name}"
            ),
        )

    previous_stock = product.stock

    new_stock = (
        previous_stock
        - payload.quantity
    )

    item = OpenAccountItem(
        account=account,
        product=product,
        quantity=payload.quantity,
        unit_price=product.price,
    )

    product.stock = new_stock

    account.total = (
        account.total
        + (
            product.price
            * payload.quantity
        )
    )

    movement = InventoryMovement(
        product=product,
        movement_type="ACCOUNT_CONSUMPTION",
        quantity=-payload.quantity,
        previous_stock=previous_stock,
        new_stock=new_stock,
        reference_type="ACCOUNT",
        reference_id=account.id,
        notes=(
            f"Consumo {account.number} · "
            f"{account.account_type} "
            f"{account.label}"
        ),
    )

    db.add(item)
    db.add(movement)
    db.flush()

    write_system_audit(
        db=db,
        actor=actor,
        action="ACCOUNT_ITEM_ADD",
        entity_type="OPEN_ACCOUNT",
        entity_id=account.id,
        entity_name=(
            f"{account.account_type} "
            f"{account.label}"
        ),
        description=(
            f"{product.name} x "
            f"{payload.quantity} agregado a "
            f"{account.number}"
        ),
    )

    try:
        db.commit()
        db.refresh(account)

    except Exception:
        db.rollback()
        raise

    return serialize_open_account(
        account
    )


@app.post(
    "/api/open-accounts/{account_id}/close",
)
def close_open_account(
    account_id: int,
    payload: OpenAccountCloseCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
            "VENDEDOR",
        )
    ),
):
    account = db.get(
        OpenAccount,
        account_id,
    )

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Cuenta no encontrada",
        )

    if account.status != "OPEN":
        raise HTTPException(
            status_code=409,
            detail="La cuenta ya está cerrada",
        )

    if not account.items:
        raise HTTPException(
            status_code=409,
            detail=(
                "No puedes cerrar una cuenta "
                "sin consumos"
            ),
        )

    next_sale_id = (
        db.scalar(
            select(Sale.id)
            .order_by(
                Sale.id.desc()
            )
        )
        or 0
    ) + 1

    sale = Sale(
        number=f"V-{next_sale_id:05d}",
        customer_name=(
            account.customer_name
            or "Consumidor final"
        ),
        payment_method=(
            payload.payment_method
            .strip()
            .lower()
        ),
        total=account.total,
        status="completada",
    )

    db.add(sale)
    db.flush()

    # IMPORTANTE:
    # El stock YA fue descontado cuando
    # se agregaron consumos a la cuenta.
    # Aquí solo copiamos los items a la venta.

    for account_item in account.items:

        sale_item = SaleItem(
            sale=sale,
            product_id=account_item.product_id,
            quantity=account_item.quantity,
            unit_price=account_item.unit_price,
        )

        db.add(sale_item)

    account.status = "CLOSED"

    account.payment_method = (
        payload.payment_method
        .strip()
        .lower()
    )

    account.closed_by_user_id = (
        actor.id
    )

    account.closed_by_name = (
        actor.full_name
        or actor.username
    )

    account.closed_at = datetime.utcnow()

    write_system_audit(
        db=db,
        actor=actor,
        action="ACCOUNT_CLOSE",
        entity_type="OPEN_ACCOUNT",
        entity_id=account.id,
        entity_name=(
            f"{account.account_type} "
            f"{account.label}"
        ),
        description=(
            f"Cuenta {account.number} cerrada "
            f"como venta {sale.number} "
            f"por {sale.total}"
        ),
    )

    write_system_audit(
        db=db,
        actor=actor,
        action="SALE_CREATE",
        entity_type="SALE",
        entity_id=sale.id,
        entity_name=sale.number,
        description=(
            f"Venta desde cuenta "
            f"{account.number} "
            f"por {sale.total}"
        ),
    )

    try:
        db.commit()
        db.refresh(sale)
        db.refresh(account)

    except Exception:
        db.rollback()
        raise

    return {
        "ok": True,
        "account": serialize_open_account(
            account
        ),
        "sale": {
            "id": sale.id,
            "number": sale.number,
            "total": sale.total,
            "status": sale.status,
            "payment_method": (
                sale.payment_method
            ),
        },
    }


@app.post(
    "/api/expenses",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_roles(
                "ADMIN",
            )
        )
    ],
)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
        )
    ),
):
    expense = Expense(**payload.model_dump())
    db.add(expense)
    write_system_audit(
        db=db,
        actor=actor,
        action="EXPENSE_CREATE",
        entity_type="EXPENSE",
        entity_id=expense.id,
        entity_name=expense.concept,
        description=(
            f"Gasto registrado por {expense.value}"
        ),
    )

    db.commit()
    db.refresh(expense)
    return expense


@app.get("/api/expenses")
def list_expenses(db: Session = Depends(get_db)):
    return db.scalars(select(Expense).order_by(Expense.created_at.desc())).all()



@app.get("/api/inventory/movements")
def list_inventory_movements(db: Session = Depends(get_db)):
    movements = db.scalars(
        select(InventoryMovement)
        .order_by(InventoryMovement.created_at.desc())
    ).all()

    return [
        {
            "id": movement.id,
            "product_id": movement.product_id,
            "product_name": movement.product.name,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "previous_stock": movement.previous_stock,
            "new_stock": movement.new_stock,
            "reference_type": movement.reference_type,
            "reference_id": movement.reference_id,
            "notes": movement.notes,
            "created_at": movement.created_at,
        }
        for movement in movements
    ]


@app.get("/api/inventory/history")
def list_inventory_history(
    product_id: int | None = None,
    period_from: str | None = None,
    period_to: str | None = None,
    source: str | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 2000))

    query = select(InventoryHistory)

    if product_id is not None:
        query = query.where(InventoryHistory.product_id == product_id)
    if period_from:
        query = query.where(InventoryHistory.period_date >= period_from)
    if period_to:
        query = query.where(InventoryHistory.period_date <= period_to)
    if source:
        query = query.where(InventoryHistory.source.contains(source))

    query = query.order_by(
        InventoryHistory.period_date.desc(),
        InventoryHistory.product_id,
    ).limit(limit)

    records = db.scalars(query).all()

    return [
        {
            "id": r.id,
            "product_id": r.product_id,
            "product_name": r.product.name,
            "period_date": r.period_date.isoformat() if r.period_date else None,
            "opening_stock": float(r.opening_stock),
            "incoming_stock": float(r.incoming_stock),
            "closing_stock": float(r.closing_stock),
            "units_sold": float(r.units_sold),
            "sale_price": float(r.sale_price),
            "total_sold": float(r.total_sold),
            "ideal_stock": float(r.ideal_stock) if r.ideal_stock is not None else None,
            "suggested_order": float(r.suggested_order) if r.suggested_order is not None else None,
            "source": r.source,
            "source_sheet": r.source_sheet,
        }
        for r in records
    ]



@app.post("/api/inventory/adjustments", status_code=status.HTTP_201_CREATED)
def create_inventory_adjustment(
    payload: InventoryAdjustmentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
        )
    ),
):
    allowed_types = {
        "PURCHASE",
        "ADJUSTMENT_IN",
        "ADJUSTMENT_OUT",
        "LOSS",
    }

    movement_type = payload.movement_type.upper().strip()

    if movement_type not in allowed_types:
        raise HTTPException(
            status_code=422,
            detail=(
                "Tipo de movimiento inválido. "
                "Usa PURCHASE, ADJUSTMENT_IN, ADJUSTMENT_OUT o LOSS."
            ),
        )

    product = db.get(Product, payload.product_id)

    if not product or not product.active:
        raise HTTPException(
            status_code=404,
            detail="Producto no encontrado",
        )

    previous_stock = product.stock

    if movement_type in {"PURCHASE", "ADJUSTMENT_IN"}:
        signed_quantity = payload.quantity
    else:
        signed_quantity = -payload.quantity

    new_stock = previous_stock + signed_quantity

    if new_stock < 0:
        raise HTTPException(
            status_code=409,
            detail=f"Stock insuficiente para {product.name}",
        )

    movement = InventoryMovement(
        product=product,
        movement_type=movement_type,
        quantity=signed_quantity,
        previous_stock=previous_stock,
        new_stock=new_stock,
        reference_type="MANUAL",
        reference_id=None,
        notes=payload.notes,
    )

    product.stock = new_stock

    db.add(movement)

    try:
        write_system_audit(
            db=db,
            actor=actor,
            action="INVENTORY_ADJUSTMENT",
            entity_type="INVENTORY",
            entity_id=movement.id,
            entity_name=product.name,
            description=(
                f"{movement.movement_type}: "
                f"{movement.quantity}"
            ),
        )

        db.commit()
        db.refresh(movement)

    except Exception:
        db.rollback()
        raise

    return {
        "id": movement.id,
        "product_id": product.id,
        "product_name": product.name,
        "movement_type": movement.movement_type,
        "quantity": movement.quantity,
        "previous_stock": movement.previous_stock,
        "new_stock": movement.new_stock,
        "notes": movement.notes,
        "created_at": movement.created_at,
    }


@app.post(
    "/api/cash-register/open",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_roles(
                "ADMIN",
                "VENDEDOR",
            )
        )
    ],
)
def open_cash_register(
    payload: CashRegisterOpenCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
            "VENDEDOR",
        )
    ),
):
    current = db.scalars(
        select(CashRegisterSession)
        .where(CashRegisterSession.status == "OPEN")
        .order_by(CashRegisterSession.opened_at.desc())
    ).first()

    if current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una caja abierta."
        )

    session = CashRegisterSession(
        opening_amount=payload.opening_amount,
        expected_amount=payload.opening_amount,
        status="OPEN",
    )

    db.add(session)

    try:
        write_system_audit(
            db=db,
            actor=actor,
            action="CASH_OPEN",
            entity_type="CASH_REGISTER",
            entity_id=session.id,
            entity_name="Caja",
            description=(
                f"Apertura por {session.opening_amount}"
            ),
        )

        db.commit()
        db.refresh(session)

    except Exception:
        db.rollback()
        raise

    return {
        "id": session.id,
        "opening_amount": session.opening_amount,
        "expected_amount": session.expected_amount,
        "status": session.status,
        "opened_at": session.opened_at,
    }


@app.get("/api/cash-register/current")
def get_current_cash_register(
    db: Session = Depends(get_db),
):
    session = db.scalars(
        select(CashRegisterSession)
        .where(CashRegisterSession.status == "OPEN")
        .order_by(CashRegisterSession.opened_at.desc())
    ).first()

    if not session:
        return {
            "status": "CLOSED",
            "session": None,
        }

    completed_sales = db.scalars(
        select(Sale).where(
            Sale.status == "completada",
            Sale.created_at >= session.opened_at,
        )
    ).all()

    cash_sales = [
        sale
        for sale in completed_sales
        if str(sale.payment_method).lower() == "efectivo"
    ]

    payment_totals = {}

    for sale in completed_sales:
        method = str(
            sale.payment_method or "otro"
        ).lower()

        payment_totals[method] = (
            payment_totals.get(
                method,
                Decimal("0")
            )
            + sale.total
        )

    sales_total = sum(
        (sale.total for sale in completed_sales),
        Decimal("0")
    )

    expenses = db.scalars(
        select(Expense).where(
            Expense.created_at >= session.opened_at,
            Expense.payment_method == "efectivo",
        )
    ).all()

    cash_sales_total = sum(
        (sale.total for sale in cash_sales),
        Decimal("0")
    )

    expenses_total = sum(
        (expense.value for expense in expenses),
        Decimal("0")
    )

    expected_amount = (
        session.opening_amount
        + cash_sales_total
        - expenses_total
    )

    return {
        "status": session.status,
        "session": {
            "id": session.id,
            "opening_amount": session.opening_amount,
            "opened_at": session.opened_at,
            "cash_sales_total": cash_sales_total,
            "sales_total": sales_total,
            "payment_totals": payment_totals,
            "expenses_total": expenses_total,
            "expected_amount": expected_amount,
        },
    }


@app.post(
    "/api/cash-register/close",
    dependencies=[
        Depends(
            require_roles(
                "ADMIN",
                "VENDEDOR",
            )
        )
    ],
)
def close_cash_register(
    payload: CashRegisterCloseCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(
        require_roles(
            "ADMIN",
            "VENDEDOR",
        )
    ),
):
    session = db.scalars(
        select(CashRegisterSession)
        .where(CashRegisterSession.status == "OPEN")
        .order_by(CashRegisterSession.opened_at.desc())
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay una caja abierta."
        )

    completed_sales = db.scalars(
        select(Sale).where(
            Sale.status == "completada",
            Sale.created_at >= session.opened_at,
        )
    ).all()

    cash_sales = [
        sale
        for sale in completed_sales
        if str(sale.payment_method).lower() == "efectivo"
    ]

    payment_totals = {}

    for sale in completed_sales:
        method = str(
            sale.payment_method or "otro"
        ).lower()

        payment_totals[method] = (
            payment_totals.get(
                method,
                Decimal("0")
            )
            + sale.total
        )

    sales_total = sum(
        (sale.total for sale in completed_sales),
        Decimal("0")
    )

    expenses = db.scalars(
        select(Expense).where(
            Expense.created_at >= session.opened_at,
            Expense.payment_method == "efectivo",
        )
    ).all()

    cash_sales_total = sum(
        (sale.total for sale in cash_sales),
        Decimal("0")
    )

    expenses_total = sum(
        (expense.value for expense in expenses),
        Decimal("0")
    )

    expected_amount = (
        session.opening_amount
        + cash_sales_total
        - expenses_total
    )

    difference = (
        payload.closing_amount
        - expected_amount
    )

    session.expected_amount = expected_amount
    session.closing_amount = payload.closing_amount
    session.difference = difference
    session.closing_notes = (
        payload.notes.strip()
        if payload.notes
        else None
    )
    session.status = "CLOSED"
    session.closed_at = datetime.utcnow()

    try:
        write_system_audit(
            db=db,
            actor=actor,
            action="CASH_CLOSE",
            entity_type="CASH_REGISTER",
            entity_id=session.id,
            entity_name="Caja",
            description=(
                f"Cierre por {payload.closing_amount}; "
                f"diferencia {difference}"
            ),
        )

        db.commit()
        db.refresh(session)

    except Exception:
        db.rollback()
        raise

    return {
        "id": session.id,
        "opening_amount": session.opening_amount,
        "cash_sales_total": cash_sales_total,
        "sales_total": sales_total,
        "payment_totals": payment_totals,
        "expenses_total": expenses_total,
        "expected_amount": session.expected_amount,
        "closing_amount": session.closing_amount,
        "difference": session.difference,
        "closing_notes": session.closing_notes,
        "status": session.status,
        "opened_at": session.opened_at,
        "closed_at": session.closed_at,
    }


