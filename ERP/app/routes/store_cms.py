"""CMS tienda: carrusel y opciones de publicidad del home (admin)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.auth_handler import role_required
from app.database import get_db
from app.models.store_slide import StoreSlide
from app.services.store_catalog import store_category_options
from app.services.store_home_service import (
    get_or_create_home_settings,
    list_all_slides,
)
from app.utils.context import get_global_config
from app.utils.image_storage import (
    MAX_STORE_SLIDE_BYTES,
    UploadValidationError,
    delete_store_slide_image,
    product_image_url,
    read_upload_bytes,
    save_store_slide_image,
    store_slide_image_url,
    validate_upload_filename,
)
from app.utils.urls import ERP_PREFIX, erp_path

router = APIRouter(prefix="/store-cms", tags=["store-cms"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["erp_prefix"] = ERP_PREFIX
templates.env.globals["erp_url"] = erp_path
templates.env.globals["product_image_url"] = product_image_url
templates.env.globals["store_slide_image_url"] = store_slide_image_url


def _require_admin(request: Request):
    return role_required(request, ["admin"])


@router.get("/", response_class=HTMLResponse)
async def store_cms_home(request: Request, db: Session = Depends(get_db)):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    settings = get_or_create_home_settings(db)
    slides = list_all_slides(db)
    return templates.TemplateResponse(
        request=request,
        name="store_cms/index.html",
        context={
            "user": user,
            "settings": settings,
            "slides": slides,
            "categories": store_category_options(db),
            "flash": request.query_params.get("ok", ""),
            "error": request.query_params.get("error", ""),
        },
    )


@router.post("/settings")
async def store_cms_save_settings(
    request: Request,
    show_top_bar: str = Form("no"),
    top_bar_left: str = Form(""),
    top_bar_right: str = Form(""),
    accent_color: str = Form("#E8A0AC"),
    feature_1_title: str = Form(""),
    feature_1_text: str = Form(""),
    feature_2_title: str = Form(""),
    feature_2_text: str = Form(""),
    feature_3_title: str = Form(""),
    feature_3_text: str = Form(""),
    show_categories: str = Form("no"),
    featured_categories: str = Form(""),
    show_featured_products: str = Form("no"),
    featured_product_ids: str = Form(""),
    show_trust_bar: str = Form("no"),
    trust_1_title: str = Form(""),
    trust_1_text: str = Form(""),
    trust_2_title: str = Form(""),
    trust_2_text: str = Form(""),
    trust_3_title: str = Form(""),
    trust_3_text: str = Form(""),
    trust_4_title: str = Form(""),
    trust_4_text: str = Form(""),
    show_newsletter: str = Form("no"),
    newsletter_title: str = Form(""),
    footer_blurb: str = Form(""),
    contact_address: str = Form(""),
    contact_phone: str = Form(""),
    contact_email: str = Form(""),
    contact_hours: str = Form(""),
    contact_whatsapp: str = Form(""),
    social_instagram: str = Form(""),
    social_facebook: str = Form(""),
    social_tiktok: str = Form(""),
    nav_extra_links: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    s = get_or_create_home_settings(db)
    s.show_top_bar = show_top_bar == "yes"
    s.top_bar_left = top_bar_left.strip() or None
    s.top_bar_right = top_bar_right.strip() or None
    s.accent_color = (accent_color or "").strip() or "#E8A0AC"
    s.feature_1_title = feature_1_title.strip() or None
    s.feature_1_text = feature_1_text.strip() or None
    s.feature_2_title = feature_2_title.strip() or None
    s.feature_2_text = feature_2_text.strip() or None
    s.feature_3_title = feature_3_title.strip() or None
    s.feature_3_text = feature_3_text.strip() or None
    s.show_categories = show_categories == "yes"
    s.featured_categories = featured_categories.strip() or None
    s.show_featured_products = show_featured_products == "yes"
    s.featured_product_ids = featured_product_ids.strip() or None
    s.show_trust_bar = show_trust_bar == "yes"
    s.trust_1_title = trust_1_title.strip() or None
    s.trust_1_text = trust_1_text.strip() or None
    s.trust_2_title = trust_2_title.strip() or None
    s.trust_2_text = trust_2_text.strip() or None
    s.trust_3_title = trust_3_title.strip() or None
    s.trust_3_text = trust_3_text.strip() or None
    s.trust_4_title = trust_4_title.strip() or None
    s.trust_4_text = trust_4_text.strip() or None
    s.show_newsletter = show_newsletter == "yes"
    s.newsletter_title = newsletter_title.strip() or None
    s.footer_blurb = footer_blurb.strip() or None
    s.contact_address = contact_address.strip() or None
    s.contact_phone = contact_phone.strip() or None
    s.contact_email = contact_email.strip() or None
    s.contact_hours = contact_hours.strip() or None
    s.contact_whatsapp = contact_whatsapp.strip() or None
    s.social_instagram = social_instagram.strip() or None
    s.social_facebook = social_facebook.strip() or None
    s.social_tiktok = social_tiktok.strip() or None
    s.nav_extra_links = nav_extra_links.strip() or None
    s.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=erp_path("/store-cms/?ok=settings"), status_code=303)


@router.post("/slides")
async def store_cms_create_slide(
    request: Request,
    title: str = Form(...),
    subtitle: str = Form(""),
    cta_text: str = Form("Ver productos"),
    cta_url: str = Form("/tienda"),
    sort_order: int = Form(0),
    active: str = Form("yes"),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    image_name = None
    try:
        if image and image.filename:
            validate_upload_filename(image.filename)
            data = await read_upload_bytes(image, MAX_STORE_SLIDE_BYTES)
            image_name = save_store_slide_image(data)
    except UploadValidationError as exc:
        from urllib.parse import quote

        return RedirectResponse(
            url=erp_path(f"/store-cms/?error={quote(str(exc))}"),
            status_code=303,
        )

    slide = StoreSlide(
        title=(title or "").strip() or "Nuevo slide",
        subtitle=(subtitle or "").strip() or None,
        cta_text=(cta_text or "").strip() or "Ver productos",
        cta_url=(cta_url or "").strip() or "/tienda",
        image=image_name,
        sort_order=int(sort_order or 0),
        active=active == "yes",
    )
    db.add(slide)
    db.commit()
    return RedirectResponse(url=erp_path("/store-cms/?ok=slide"), status_code=303)


@router.post("/slides/{slide_id}")
async def store_cms_update_slide(
    slide_id: int,
    request: Request,
    title: str = Form(...),
    subtitle: str = Form(""),
    cta_text: str = Form("Ver productos"),
    cta_url: str = Form("/tienda"),
    sort_order: int = Form(0),
    active: str = Form("yes"),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    slide = db.query(StoreSlide).filter(StoreSlide.id == slide_id).first()
    if not slide:
        return RedirectResponse(url=erp_path("/store-cms/?error=slide"), status_code=303)

    try:
        if image and image.filename:
            validate_upload_filename(image.filename)
            data = await read_upload_bytes(image, MAX_STORE_SLIDE_BYTES)
            new_name = save_store_slide_image(data)
            delete_store_slide_image(slide.image)
            slide.image = new_name
    except UploadValidationError as exc:
        from urllib.parse import quote

        return RedirectResponse(
            url=erp_path(f"/store-cms/?error={quote(str(exc))}"),
            status_code=303,
        )

    slide.title = (title or "").strip() or slide.title
    slide.subtitle = (subtitle or "").strip() or None
    slide.cta_text = (cta_text or "").strip() or "Ver productos"
    slide.cta_url = (cta_url or "").strip() or "/tienda"
    slide.sort_order = int(sort_order or 0)
    slide.active = active == "yes"
    db.commit()
    return RedirectResponse(url=erp_path("/store-cms/?ok=slide"), status_code=303)


@router.post("/slides/{slide_id}/delete")
async def store_cms_delete_slide(
    slide_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    slide = db.query(StoreSlide).filter(StoreSlide.id == slide_id).first()
    if slide:
        delete_store_slide_image(slide.image)
        db.delete(slide)
        db.commit()
    return RedirectResponse(url=erp_path("/store-cms/?ok=deleted"), status_code=303)
