import json
import shutil
import zipfile
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path

from flask import Blueprint, abort, render_template, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from app import db
from app.models import User, AuditLog, Motorcycle, ServiceEntry, TechnicalSpec, ServiceChecklist

auth_bp = Blueprint('auth', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Du hast keine Berechtigung für diese Seite.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if not current_app.config["MOTODB_ALLOW_REGISTRATION"]:
        abort(404)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if not all([username, email, password, password_confirm]):
            flash('Alle Felder sind erforderlich.', 'danger')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            flash('Passwort muss mindestens 8 Zeichen lang sein.', 'danger')
            return redirect(url_for('auth.register'))

        if password != password_confirm:
            flash('Passwörter stimmen nicht überein.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first():
            flash('Benutzername existiert bereits.', 'danger')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('Email existiert bereits.', 'danger')
            return redirect(url_for('auth.register'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'Willkommen, {username}! Bitte melde dich an.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_app.config["MOTODB_PUBLIC_HOSTING"] and not request.is_secure:
        return render_template('auth/login.html', https_required=True), 400

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email und Passwort erforderlich.', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Email oder Passwort falsch.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user)
        user.last_login = datetime.utcnow()
        db.session.commit()

        return redirect(url_for('main.index'))

    return render_template('auth/login.html', https_required=False)


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Du wurdest abgemeldet.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/account/password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if not all([current_password, password, password_confirm]):
            flash('Alle Felder sind erforderlich.', 'danger')
            return redirect(url_for('auth.change_password'))

        if not current_user.check_password(current_password):
            flash('Das aktuelle Passwort ist falsch.', 'danger')
            return redirect(url_for('auth.change_password'))

        if len(password) < 8:
            flash('Das neue Passwort muss mindestens 8 Zeichen lang sein.', 'danger')
            return redirect(url_for('auth.change_password'))

        if password != password_confirm:
            flash('Die neuen Passwörter stimmen nicht überein.', 'danger')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(password)
        db.session.commit()
        flash('Dein Passwort wurde geändert.', 'success')
        return redirect(url_for('main.index'))

    return render_template('auth/change_password.html')


@auth_bp.route('/consent', methods=['POST'])
@login_required
def accept_consent():
    current_user.consent_accepted_at = datetime.utcnow()
    db.session.commit()
    return redirect(request.referrer or url_for('main.index'))


@auth_bp.route('/user/export')
@login_required
def user_export():
    export_data = {
        'user': {
            'email': current_user.email,
            'username': current_user.username,
            'created_at': current_user.created_at.isoformat(),
        },
        'motorcycles': [],
        'services': [],
        'technical_specs': [],
        'checklists': [],
    }

    motorcycles = Motorcycle.query.filter_by(user_id=current_user.id).all()
    for m in motorcycles:
        export_data['motorcycles'].append({
            'id': m.id,
            'marke': m.marke,
            'modell': m.modell,
            'baujahr': m.baujahr,
            'kilometerstand': m.kilometerstand,
            'kaufpreis': m.kaufpreis,
            'hubraum': m.hubraum,
            'ps': m.ps,
            'farbe': m.farbe,
            'kaufdatum': m.kaufdatum.isoformat() if m.kaufdatum else None,
            'kennzeichen': m.kennzeichen,
            'vin': m.vin,
            'erstzulassung': m.erstzulassung.isoformat() if m.erstzulassung else None,
            'verkauft_am': m.verkauft_am.isoformat() if m.verkauft_am else None,
            'verkaufspreis': m.verkaufspreis,
            'aktiv': m.aktiv,
            'notizen': m.notizen,
            'created_at': m.created_at.isoformat(),
            'updated_at': m.updated_at.isoformat(),
        })

    services = ServiceEntry.query.filter_by(user_id=current_user.id).all()
    for s in services:
        export_data['services'].append({
            'id': s.id,
            'motorrad_id': s.motorrad_id,
            'titel': s.titel,
            'datum': s.datum.isoformat() if s.datum else None,
            'kilometerstand': s.kilometerstand,
            'beschreibung': s.beschreibung,
            'kosten': s.kosten,
            'kategorie': s.kategorie,
            'naechster_service_km': s.naechster_service_km,
            'naechster_service_datum': s.naechster_service_datum.isoformat() if s.naechster_service_datum else None,
            'created_at': s.created_at.isoformat(),
            'updated_at': s.updated_at.isoformat(),
        })

    specs = TechnicalSpec.query.filter_by(user_id=current_user.id).all()
    for spec in specs:
        export_data['technical_specs'].append({
            'id': spec.id,
            'motorrad_id': spec.motorrad_id,
            'name': spec.name,
            'wert': spec.wert,
            'einheit': spec.einheit,
            'kategorie': spec.kategorie,
            'quelle': spec.quelle,
            'created_at': spec.created_at.isoformat(),
            'updated_at': spec.updated_at.isoformat(),
        })

    checklists = ServiceChecklist.query.filter_by(user_id=current_user.id).all()
    for cl in checklists:
        export_data['checklists'].append({
            'id': cl.id,
            'motorrad_id': cl.motorrad_id,
            'titel': cl.titel,
            'intervall_km': cl.intervall_km,
            'intervall_monate': cl.intervall_monate,
            'datum': cl.datum.isoformat() if cl.datum else None,
            'kilometerstand': cl.kilometerstand,
            'anmerkungen': cl.anmerkungen,
            'is_template': cl.is_template,
            'completed_at': cl.completed_at.isoformat() if cl.completed_at else None,
            'created_at': cl.created_at.isoformat(),
            'updated_at': cl.updated_at.isoformat(),
        })

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('data.json', json.dumps(export_data, indent=2, ensure_ascii=False))

        upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
        for motorcycle in motorcycles:
            motorcycle_upload_folder = upload_folder / str(motorcycle.id)
            if motorcycle_upload_folder.exists():
                for file_path in motorcycle_upload_folder.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(upload_folder)
                        zf.write(file_path, arcname)

    zip_buffer.seek(0)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'motorad_export_{current_user.id}_{timestamp}.zip'
    )


@auth_bp.route('/user/delete', methods=['GET', 'POST'])
@login_required
def user_delete():
    if request.method == 'POST':
        confirmation = request.form.get('confirmation', '').lower()
        if confirmation != 'jaloeschen':
            flash('Bestätigung falsch. Konto wurde nicht gelöscht.', 'danger')
            return redirect(url_for('auth.user_delete'))

        user_id = current_user.id

        motorcycle_ids = [
            motorcycle_id
            for (motorcycle_id,) in Motorcycle.query.with_entities(Motorcycle.id)
            .filter_by(user_id=user_id)
            .all()
        ]

        Motorcycle.query.filter_by(user_id=user_id).delete()
        ServiceEntry.query.filter_by(user_id=user_id).delete()
        TechnicalSpec.query.filter_by(user_id=user_id).delete()
        ServiceChecklist.query.filter_by(user_id=user_id).delete()
        AuditLog.query.filter_by(user_id=user_id).delete()

        upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
        for motorcycle_id in motorcycle_ids:
            motorcycle_upload_folder = upload_folder / str(motorcycle_id)
            if motorcycle_upload_folder.exists():
                shutil.rmtree(motorcycle_upload_folder)

        db.session.delete(current_user)
        db.session.commit()

        logout_user()
        flash('Dein Konto und alle Daten wurden gelöscht.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/delete_account.html')


@auth_bp.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@auth_bp.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin(user_id):
    if user_id == current_user.id:
        flash('Du kannst deine eigenen Admin-Rechte nicht ändern.', 'danger')
        return redirect(url_for('auth.admin_users'))

    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()

    status = 'Admin' if user.is_admin else 'Nutzer'
    flash(f'{user.email} ist jetzt {status}.', 'success')
    return redirect(url_for('auth.admin_users'))
