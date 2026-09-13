from app import create_app, env_bool


app = create_app()


if __name__ == "__main__":
    # Debug (Werkzeug-Debugger + Reloader) nur auf ausdruecklichen Wunsch:
    # FLASK_DEBUG=1 python run.py
    debug = env_bool("FLASK_DEBUG")
    print("Motorrad Service läuft gleich auf:")
    print("  http://127.0.0.1:5001")
    print("  im LAN: http://<IP-dieses-Rechners>:5001")
    if debug:
        print("  Debug-Modus aktiv (nur fuer die Entwicklung, nie im Netz erreichbar betreiben).")
    print("Im Browser bitte keine Datei aus app/templates öffnen.")
    app.run(host="0.0.0.0", port=5001, debug=debug)
