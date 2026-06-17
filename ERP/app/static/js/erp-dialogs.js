/**
 * Diálogos modales del ERP (SweetAlert2).
 * API: ErpDialog.alert | .success | .warning | .error | .confirm | .prompt | .toast
 * Helpers: erpConfirmLink | erpConfirmForm
 */
(function (global) {
  "use strict";

  if (typeof Swal === "undefined") {
    console.warn("ErpDialog: SweetAlert2 no está cargado.");
    return;
  }

  function primaryColor() {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue("--primary")
      .trim();
    return value || "#7C3AED";
  }

  const baseOptions = {
    buttonsStyling: true,
    confirmButtonColor: primaryColor(),
    cancelButtonColor: "#6B7280",
    customClass: {
      popup: "rounded-2xl shadow-xl",
      title: "text-lg font-semibold text-slate-800",
      htmlContainer: "text-sm text-slate-600",
      confirmButton: "rounded-xl px-5 py-2.5 font-medium",
      cancelButton: "rounded-xl px-5 py-2.5 font-medium",
    },
  };

  function mergeOptions(options) {
    return {
      ...baseOptions,
      confirmButtonColor: primaryColor(),
      ...options,
      customClass: {
        ...baseOptions.customClass,
        ...(options.customClass || {}),
      },
    };
  }

  const ErpDialog = {
    alert(message, options = {}) {
      return Swal.fire(
        mergeOptions({
          icon: options.icon || "info",
          title: options.title || "Aviso",
          text: message,
          confirmButtonText: options.confirmText || "Aceptar",
        })
      );
    },

    success(message, title = "Listo") {
      return Swal.fire(
        mergeOptions({
          icon: "success",
          title,
          text: message,
          confirmButtonText: "Aceptar",
        })
      );
    },

    warning(message, title = "Atención") {
      return Swal.fire(
        mergeOptions({
          icon: "warning",
          title,
          text: message,
          confirmButtonText: "Entendido",
        })
      );
    },

    error(message, title = "Error") {
      return Swal.fire(
        mergeOptions({
          icon: "error",
          title,
          text: message,
          confirmButtonText: "Aceptar",
        })
      );
    },

    toast(message, icon = "success") {
      return Swal.fire(
        mergeOptions({
          toast: true,
          position: "top-end",
          icon,
          title: message,
          showConfirmButton: false,
          timer: 2800,
          timerProgressBar: true,
        })
      );
    },

    async confirm(message, options = {}) {
      const result = await Swal.fire(
        mergeOptions({
          icon: options.icon || "question",
          title: options.title || "¿Confirmar?",
          text: message,
          showCancelButton: true,
          confirmButtonText: options.confirmText || "Sí, continuar",
          cancelButtonText: options.cancelText || "Cancelar",
          reverseButtons: true,
          focusCancel: true,
        })
      );
      return result.isConfirmed;
    },

    async prompt(message, options = {}) {
      const result = await Swal.fire(
        mergeOptions({
          icon: options.icon || "question",
          title: options.title || message,
          text: options.text || "",
          input: options.input || "text",
          inputPlaceholder: options.placeholder || "",
          inputAttributes: options.inputAttributes || {},
          showCancelButton: true,
          confirmButtonText: options.confirmText || "Confirmar",
          cancelButtonText: options.cancelText || "Cancelar",
          reverseButtons: true,
          inputValidator: options.validator,
        })
      );
      if (!result.isConfirmed) {
        return null;
      }
      return result.value;
    },
  };

  function erpConfirmLink(event, message, options) {
    event.preventDefault();
    const link = event.currentTarget;
    ErpDialog.confirm(message, options).then(function (confirmed) {
      if (confirmed && link.href) {
        window.location.href = link.href;
      }
    });
    return false;
  }

  function erpConfirmForm(event, message, options) {
    event.preventDefault();
    const form = event.currentTarget;
    ErpDialog.confirm(message, options).then(function (confirmed) {
      if (confirmed) {
        form.submit();
      }
    });
    return false;
  }

  document.addEventListener("click", async function (event) {
    const trigger = event.target.closest("[data-erp-confirm]");
    if (!trigger) {
      return;
    }

    event.preventDefault();

    const message = trigger.getAttribute("data-erp-confirm") || "¿Confirmar acción?";
    const title = trigger.getAttribute("data-erp-confirm-title") || undefined;
    const confirmed = await ErpDialog.confirm(message, { title });

    if (!confirmed) {
      return;
    }

    const href = trigger.getAttribute("data-erp-href") || trigger.getAttribute("href");
    const formId = trigger.getAttribute("data-erp-form");

    if (formId) {
      document.getElementById(formId)?.submit();
      return;
    }

    if (href) {
      window.location.href = href;
      return;
    }

    const form = trigger.closest("form");
    if (form) {
      form.submit();
    }
  });

  global.ErpDialog = ErpDialog;
  global.erpConfirmLink = erpConfirmLink;
  global.erpConfirmForm = erpConfirmForm;
})(window);
