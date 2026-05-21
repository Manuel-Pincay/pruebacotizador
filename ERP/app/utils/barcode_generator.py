import barcode

from barcode.writer import ImageWriter


def generate_barcode(code: str):

    barcode_class = barcode.get_barcode_class(
        "code128"
    )

    barcode_instance = barcode_class(
        code,
        writer=ImageWriter()
    )

    filename = f"uploads/barcodes/{code}"

    barcode_instance.save(filename)

    return f"{code}.png"