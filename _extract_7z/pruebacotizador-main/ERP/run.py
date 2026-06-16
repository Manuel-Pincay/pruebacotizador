import uvicorn
import socket

if __name__ == "__main__":
    hostname = socket.gethostname()

    local_ip = socket.gethostbyname(
        hostname
    )

    print("\n")

    print("=" * 50)

    print(
        f"ERP disponible en:\n"
    )

    print(
        f"http://{local_ip}:8000"
    )

    print("=" * 50)

    print("\n")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )