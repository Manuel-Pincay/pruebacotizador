from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.auth_handler import login_required
from app.database import get_db
from app.models.notification import Notification
from app.utils.context import get_global_config
from app.utils.notifications import unread_count

router = APIRouter(prefix="/notifications", tags=["notifications"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config


@router.get("/", response_class=HTMLResponse)
async def notifications_page(request: Request, db: Session = Depends(get_db)):
    user = login_required(request)
    if isinstance(user, RedirectResponse):
        return user

    items = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(100)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="notifications/list.html",
        context={
            "user": user,
            "notifications": items,
            "unread": unread_count(db, user.id),
        },
    )


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int, request: Request, db: Session = Depends(get_db)
):
    user = login_required(request)
    if isinstance(user, RedirectResponse):
        return user

    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if n:
        n.is_read = True
        db.commit()
        if n.link:
            return RedirectResponse(url=n.link, status_code=302)

    return RedirectResponse(url="/notifications/", status_code=302)


@router.post("/read-all")
async def mark_all_read(request: Request, db: Session = Depends(get_db)):
    user = login_required(request)
    if isinstance(user, RedirectResponse):
        return user

    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.is_read.is_(False),
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return RedirectResponse(url="/notifications/", status_code=302)
