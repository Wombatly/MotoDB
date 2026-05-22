from app import create_app


app = create_app()


if __name__ == "__main__":
    print("Motorrad Service läuft gleich auf:")
    print("  http://127.0.0.1:5001")
    print("  http://192.168.178.59:5001")
    print("Im Browser bitte keine Datei aus app/templates öffnen.")
    app.run(host="0.0.0.0", port=5001, debug=True)
