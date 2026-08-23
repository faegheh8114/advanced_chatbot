from flask import render_template, request, jsonify


def register_error_handlers(app):
    def wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(401)
    def unauthorized(e):
        if wants_json():
            return jsonify({"error": "Authentication required."}), 401
        return render_template("errors/error.html", code=401,
                                message="Please log in to continue."), 401

    @app.errorhandler(403)
    def forbidden(e):
        if wants_json():
            return jsonify({"error": "You don't have permission to do that."}), 403
        return render_template("errors/error.html", code=403,
                                message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        if wants_json():
            return jsonify({"error": "Not found."}), 404
        return render_template("errors/error.html", code=404,
                                message="That page doesn't exist."), 404

    @app.errorhandler(413)
    def too_large(e):
        if wants_json():
            return jsonify({"error": "File too large."}), 413
        return render_template("errors/error.html", code=413,
                                message="That file is too large to upload."), 413

    @app.errorhandler(500)
    def server_error(e):
        if wants_json():
            return jsonify({"error": "Something went wrong."}), 500
        return render_template("errors/error.html", code=500,
                                message="Something went wrong on our end."), 500
