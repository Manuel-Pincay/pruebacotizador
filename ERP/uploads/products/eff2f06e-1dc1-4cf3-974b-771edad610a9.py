import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog

# ===== VARIABLES =====
drawing = False
ix, iy = -1, -1
fx, fy = -1, -1
scale = 1.0

# ===== SELECCIONAR IMAGEN =====
root = tk.Tk()
root.withdraw()

ruta = filedialog.askopenfilename(
    title="Selecciona una imagen",
    filetypes=[("Imágenes", "*.jpg *.jpeg *.png")]
)

if not ruta:
    print("❌ No seleccionaste imagen")
    exit()

# ===== CARGAR IMAGEN ORIGINAL =====
original = cv2.imread(ruta)

if original is None:
    print("❌ Error cargando imagen")
    exit()

# ===== REDIMENSIONAR PARA VISUAL =====
max_width = 900
h, w = original.theme[:2]

if w > max_width:
    scale = max_width / w
    display = cv2.resize(original, None, fx=scale, fy=scale)
else:
    display = original.copy()

img = display.copy()
img_copy = display.copy()

# ===== MOUSE =====
def draw_rectangle(event, x, y, flags, param):
    global ix, iy, fx, fy, drawing, img

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            img = img_copy.copy()
            cv2.rectangle(img, (ix, iy), (x, y), (0, 255, 0), 2)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        fx, fy = x, y
        cv2.rectangle(img, (ix, iy), (fx, fy), (0, 255, 0), 2)

# ===== VENTANA =====
cv2.namedWindow("Limpiar Marca")
cv2.setMouseCallback("Limpiar Marca", draw_rectangle)

print("🖱️ Dibuja un rectángulo sobre 'Sin editar'")
print("Presiona L = limpiar")
print("Presiona S = guardar")
print("Presiona Q = salir")

# ===== LOOP =====
while True:
    cv2.imshow("Limpiar Marca", img)
    key = cv2.waitKey(1) & 0xFF

    # ===== LIMPIAR =====
    if key == ord('l'):
        if ix == -1 or fx == -1:
            print("⚠️ Primero selecciona una zona")
            continue

        mask = np.zeros(original.theme[:2], np.uint8)

        # Convertir coordenadas a tamaño real
        x1 = int(min(ix, fx) / scale)
        x2 = int(max(ix, fx) / scale)
        y1 = int(min(iy, fy) / scale)
        y2 = int(max(iy, fy) / scale)

        # 🔥 AGRANDAR ZONA (MUY IMPORTANTE)
        padding = 30
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(original.theme[1], x2 + padding)
        y2 = min(original.theme[0], y2 + padding)

        mask[y1:y2, x1:x2] = 255

        # 🔥 SUAVIZAR BORDES
        mask = cv2.GaussianBlur(mask, (21, 21), 0)

        # 🔥 INPAINT MÁS FUERTE
        resultado = cv2.inpaint(original, mask, 10, cv2.INPAINT_TELEA)

        original[:] = resultado

        # Actualizar vista
        display = cv2.resize(original, None, fx=scale, fy=scale)
        img = display.copy()
        img_copy = display.copy()

        print("✅ Marca eliminada (o reducida)")

    # ===== GUARDAR =====
    elif key == ord('s'):
        salida = ruta.replace(".", "_limpia.")
        cv2.imwrite(salida, original)
        print(f"💾 Guardado en: {salida}")

    # ===== SALIR =====
    elif key == ord('q'):
        break

cv2.destroyAllWindows()