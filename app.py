import sys
import uuid
import base64
from flask import Flask, render_template, request, redirect, session, flash, send_from_directory
import pandas as pd
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "GharDhundo@2026#Sachin123"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# ─── Upload folder setup ───────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ─── CSV Save Helper ───────────────────────────────────────────────────────────
def save_to_csv(data_dict, file_name):
    df_new = pd.DataFrame([data_dict])
    if os.path.exists(file_name):
        df_new.to_csv(file_name, mode="a", header=False, index=False)
    else:
        df_new.to_csv(file_name, index=False)

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "register":
            full_name = request.form["full_name"]
            mobile    = request.form["mobile"]
            email     = request.form["email"]
            password  = request.form["password"]

            save_to_csv({
                "Full Name": full_name,
                "Mobile": mobile,
                "Email": email,
                "Password": password,
                "Registered At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, "registrations.csv")

            session["user"]   = full_name
            session["mobile"] = mobile
            session["email"]  = email
            flash("Registration successful! Welcome " + full_name, "success")
            return redirect("/locality")

        elif action == "login":
            # Simple login – check registrations.csv
            email    = request.form.get("email", "")
            password = request.form.get("password", "")

            if os.path.exists("registrations.csv"):
                df = pd.read_csv("registrations.csv")
                match = df[(df["Email"] == email) & (df["Password"].astype(str) == password)]
                if not match.empty:
                    row = match.iloc[0]
                    session["user"]   = row["Full Name"]
                    session["mobile"] = str(row["Mobile"])
                    session["email"]  = row["Email"]
                    flash("Welcome back, " + row["Full Name"] + "!", "success")
                    return redirect("/locality")

            flash("Email ya Password galat hai. Register karo pehle.", "danger")
            return redirect("/login")

    return render_template("login.html")


@app.route("/locality")
def locality():
    if "user" not in session:
        return redirect("/login")

    # Count live listings per area
    listing_counts = {}
    if os.path.exists("listings.csv"):
        df = pd.read_csv("listings.csv")
        counts = df["locality"].value_counts()
        listing_counts = counts.to_dict()

    areas = [
        {"name": "Dombivli",       "type": "Suburban"},
        {"name": "Kalyan",         "type": "Suburban"},
        {"name": "Thane",          "type": "Urban"},
        {"name": "Kopar Khairane", "type": "Navi Mumbai"},
        {"name": "Ghatkopar",      "type": "Urban"},
        {"name": "Mulund",         "type": "Urban"},
        {"name": "Vashi",          "type": "Navi Mumbai"},
        {"name": "Panvel",         "type": "Navi Mumbai"},
        {"name": "Bhandup",        "type": "Urban"},
        {"name": "Bhiwandi",       "type": "Rural"},
        {"name": "Ambarnath",      "type": "Suburban"},
        {"name": "Badlapur",       "type": "Rural"},
    ]

    for a in areas:
        a["rooms"] = listing_counts.get(a["name"], 0)

    return render_template("locality.html", areas=areas, user=session["user"])


@app.route("/rooms/<locality_name>")
def rooms(locality_name):
    if "user" not in session:
        return redirect("/login")

    rooms_data = []
    if os.path.exists("listings.csv"):
        df = pd.read_csv("listings.csv")
        filtered = df[df["locality"].str.lower() == locality_name.lower()]
        rooms_data = filtered.to_dict("records")

        for room in rooms_data:
            # Amenities: comma-separated string → list
            if isinstance(room.get("amenities"), str):
                room["amenities"] = [a.strip() for a in room["amenities"].split(",") if a.strip()]
            else:
                room["amenities"] = []

            # Photos: pipe-separated string → list
            if isinstance(room.get("photos"), str) and room["photos"]:
                room["photo_list"] = [p.strip() for p in room["photos"].split("|") if p.strip()]
            else:
                room["photo_list"] = []

            # Blur owner mobile for non-registered leads
            if "owner_mobile" in room:
                mobile = str(room["owner_mobile"])
                room["blurred_mobile"] = mobile[:6] + "XXXX" if len(mobile) > 6 else mobile

    return render_template("rooms.html",
                           locality=locality_name,
                           rooms=rooms_data,
                           user=session["user"])


@app.route("/list-property", methods=["GET", "POST"])
def list_property():
    if "user" not in session:
        return redirect("/login")

    areas = [
        "Dombivli", "Kalyan", "Thane", "Kopar Khairane",
        "Ghatkopar", "Mulund", "Vashi", "Panvel",
        "Bhandup", "Bhiwandi", "Ambarnath", "Badlapur"
    ]

    if request.method == "POST":
        # ── Handle photo uploads ──────────────────────────────────────────────
        uploaded_photos = request.files.getlist("photos")
        photo_paths = []

        for photo in uploaded_photos:
            if photo and photo.filename and allowed_file(photo.filename):
                ext      = photo.filename.rsplit(".", 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                photo.save(save_path)
                # Store as URL path
                photo_paths.append("/static/uploads/" + filename)

        photos_str = "|".join(photo_paths)  # pipe-separated
        first_photo = photo_paths[0] if photo_paths else "https://via.placeholder.com/600x400?text=No+Photo"

        # ── Collect amenities (checkboxes) ───────────────────────────────────
        amenities_list = request.form.getlist("amenities")
        amenities_str  = ", ".join(amenities_list)

        # ── Build listing record ─────────────────────────────────────────────
        listing_data = {
            "id":           int(datetime.now().timestamp()),
            "title":        request.form["title"],
            "type":         request.form["type"],
            "listing_for":  request.form.get("listing_for", "Rent"),   # Rent / Sale
            "rent":         request.form["rent"],
            "deposit":      request.form.get("deposit", "0"),
            "floor":        request.form.get("floor", "Ground"),
            "area":         request.form.get("area_sqft", ""),
            "available":    request.form.get("available", "Immediately"),
            "amenities":    amenities_str,
            "photos":       photos_str,         # all photos
            "img":          first_photo,         # thumbnail (for cards)
            "owner_name":   session.get("user"),
            "owner_mobile": session.get("mobile", ""),
            "owner_email":  session.get("email", ""),
            "locality":     request.form["locality"],
            "address":      request.form.get("address", ""),
            "description":  request.form.get("description", ""),
            "listed_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        save_to_csv(listing_data, "listings.csv")
        flash("🎉 Property successfully listed! Log dekhenge aapki property.", "success")
        return redirect("/rooms/" + request.form["locality"])

    return render_template("list_property.html", areas=areas, user=session["user"])


@app.route("/enquiry", methods=["POST"])
def enquiry():
    if "user" not in session:
        return redirect("/login")

    enquiry_data = {
        "Name":          request.form.get("name", ""),
        "Mobile":        request.form.get("mobile", ""),
        "Email":         request.form.get("email", ""),
        "Locality":      request.form.get("locality", ""),
        "Property Type": request.form.get("property_type", ""),
        "Budget":        request.form.get("budget", ""),
        "Call Time":     request.form.get("call_time", ""),
        "Message":       request.form.get("message", ""),
        "Submitted At":  datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_to_csv(enquiry_data, "leads.csv")
    flash("✅ Enquiry submit ho gayi! Hum aapko call karenge.", "success")
    return redirect("/rooms/" + request.form.get("locality", ""))


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
