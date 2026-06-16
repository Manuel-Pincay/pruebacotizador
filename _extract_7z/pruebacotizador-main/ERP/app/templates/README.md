# Templates ERP

Estructura por módulo. Todas las vistas internas extienden `layouts/base.html`.

```
templates/
├── layouts/          # base.html
├── auth/             # login, admin_login
├── admin/            # config, storage
├── dashboard/        # index.html
├── clients/          # list, new, edit, history
├── products/         # list, new, edit, settings
├── quotations/       # list, new, detail, tracking
├── production/       # list, kanban, calendar, detail
├── shipments/        # list, new, label (sin layout)
├── inventory/        # list
├── users/            # list, form
├── imports/          # index
├── components/       # macros reutilizables
└── partials/
    ├── products/     # catalog_table
    ├── clients/      # catalog_table
    └── quotations/   # modales
```

Convención de nombres: `list.html` (listado), `new.html` / `form.html` (crear), `edit.html`, `detail.html`.
