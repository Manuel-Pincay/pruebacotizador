from app.models.activity_log import ActivityLog


def log_activity(
    db,
    action,
    description
):

    try:

        activity = ActivityLog(

            action=action,

            description=description

        )

        db.add(activity)

        db.commit()

    except Exception:

        try:
            db.rollback()
        except Exception:
            pass
