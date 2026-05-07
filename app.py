from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import threading
import uuid
import automation

app = Flask(__name__)
jobs: dict[str, dict] = {}


@app.route("/")
def index():
    now      = datetime.now()
    today    = now.strftime("%Y%m%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y%m%d")
    today_label    = now.strftime("%-m월 %-d일 (오늘)")
    tomorrow_label = (now + timedelta(days=1)).strftime("%-m월 %-d일 (내일)")
    return render_template("index.html",
                           today=today, tomorrow=tomorrow,
                           today_label=today_label, tomorrow_label=tomorrow_label)


@app.route("/api/start", methods=["POST"])
def start():
    data         = request.json
    dep          = data["dep"]
    arr          = data["arr"]
    date         = data["date"]           # YYYYMMDD
    time_val     = data["time_val"]       # 000000 | 020000 | ...
    max_time_val = data.get("max_time_val", "")  # '' = 제한없음
    seat_type    = data["seat_type"]      # 일반 | 특실
    auto_retry   = data["auto_retry"]     # bool
    adults       = int(data.get("adults", 1))
    headless     = bool(data.get("headless", False))

    job_id = str(uuid.uuid4())[:8]
    status = {"status": "running", "message": "시작 중...", "attempts": 0}
    jobs[job_id] = status

    def worker():
        automation.run(dep, arr, date, time_val, max_time_val, seat_type, auto_retry, adults, headless, status)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/job/<job_id>")
def job_status(job_id):
    return jsonify(jobs.get(job_id, {"status": "not_found"}))


@app.route("/api/job/<job_id>/stop", methods=["POST"])
def stop_job(job_id):
    if job_id in jobs:
        jobs[job_id]["status"] = "stopped"
        jobs[job_id]["message"] = "사용자가 중단"
        return jsonify({"ok": True})
    return jsonify({"ok": False})


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False, port=5050)
